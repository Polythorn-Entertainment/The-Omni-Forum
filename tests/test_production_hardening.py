from __future__ import annotations

import sys
import tempfile
import unittest
import urllib.request
from pathlib import Path
import re

from test_support import OmniForumHarness

ROOT = Path(__file__).resolve().parents[1]


class ProductionHardeningTests(unittest.TestCase):
    def test_csp_blocks_inline_script_handlers_and_request_id_is_returned(self) -> None:
        harness = OmniForumHarness()
        harness.start()
        try:
            request = urllib.request.Request(
                f"{harness.base_url}/api/health",
                headers={"X-Request-ID": "test-request-1234"},
            )
            with urllib.request.urlopen(request, timeout=20) as response:
                csp = response.headers.get("Content-Security-Policy", "")
                request_id = response.headers.get("X-Request-ID")
                body = response.read().decode("utf-8")
            self.assertEqual("test-request-1234", request_id)
            self.assertIn('"requestId": "test-request-1234"', body)
            self.assertIn("script-src 'self'", csp)
            self.assertIn("script-src-attr 'none'", csp)
            self.assertIn("style-src 'self'", csp)
            self.assertNotIn("script-src 'self' 'unsafe-inline'", csp)
            self.assertNotIn("style-src 'self' 'unsafe-inline'", csp)
        finally:
            harness.stop()

    def test_inline_event_attributes_have_delegated_csp_bridge_coverage(self) -> None:
        supported_attributes = {"onclick", "oninput", "onchange", "onsubmit"}
        bridge_source = (ROOT / "js" / "action-delegation.js").read_text(encoding="utf-8")
        for attribute in supported_attributes:
            self.assertIn(f'delegatedInlineAction(event, "{attribute}")', bridge_source)

        discovered_attributes: set[str] = set()
        for folder in ("js", "pages"):
            for path in (ROOT / folder).glob("*.*"):
                if path.suffix not in {".js", ".html"}:
                    continue
                discovered_attributes.update(
                    match.group(1) for match in re.finditer(r"\s(on[a-z]+)=", path.read_text(encoding="utf-8"))
                )
        index_html = (ROOT / "index.html").read_text(encoding="utf-8")
        discovered_attributes.update(match.group(1) for match in re.finditer(r"\s(on[a-z]+)=", index_html))

        self.assertLessEqual(discovered_attributes, supported_attributes)

    def test_source_does_not_reintroduce_inline_style_attributes(self) -> None:
        offenders: list[str] = []
        for relative_root in ("js", "pages"):
            for path in (ROOT / relative_root).glob("*.*"):
                if path.suffix not in {".js", ".html"}:
                    continue
                source = path.read_text(encoding="utf-8")
                source = source.replace("root.style.setProperty", "")
                if 'style="' in source or ".style." in source:
                    offenders.append(str(path.relative_to(ROOT)))
        self.assertEqual([], offenders)

    def test_media_scan_hook_success_failure_and_required_mode(self) -> None:
        import omniforum.media_scan as media_scan
        from omniforum.errors import APIError

        old_command = media_scan.MEDIA_SCAN_COMMAND
        old_required = media_scan.MEDIA_SCAN_REQUIRED
        old_timeout = media_scan.MEDIA_SCAN_TIMEOUT_SECONDS
        try:
            with tempfile.TemporaryDirectory(prefix="omniforum-scan-test-") as temp_dir:
                root = Path(temp_dir)
                upload = root / "upload.png"
                upload.write_bytes(b"image")
                clean_scanner = root / "clean.py"
                clean_scanner.write_text("raise SystemExit(0)\n", encoding="utf-8")
                reject_scanner = root / "reject.py"
                reject_scanner.write_text("raise SystemExit(7)\n", encoding="utf-8")

                media_scan.MEDIA_SCAN_COMMAND = f"{sys.executable} {clean_scanner}"
                media_scan.MEDIA_SCAN_REQUIRED = True
                media_scan.MEDIA_SCAN_TIMEOUT_SECONDS = 5
                self.assertEqual(
                    "clean",
                    media_scan.scan_media_file(upload, storage_path="posts/upload.png")["status"],
                )

                media_scan.MEDIA_SCAN_COMMAND = f"{sys.executable} {reject_scanner}"
                with self.assertRaises(APIError):
                    media_scan.scan_media_file(upload, storage_path="posts/upload.png")

                media_scan.MEDIA_SCAN_COMMAND = ""
                with self.assertRaises(APIError):
                    media_scan.scan_media_file(upload, storage_path="posts/upload.png")
        finally:
            media_scan.MEDIA_SCAN_COMMAND = old_command
            media_scan.MEDIA_SCAN_REQUIRED = old_required
            media_scan.MEDIA_SCAN_TIMEOUT_SECONDS = old_timeout

    def test_email_account_features_are_disabled_and_hidden_by_default(self) -> None:
        harness = OmniForumHarness()
        harness.start()
        try:
            home = harness.client.request("GET", "/api/home")
            self.assertFalse(home["authFeatures"]["email"]["enabled"])
            self.assertFalse(home["authFeatures"]["email"]["passwordReset"])
            self.assertNotIn("email", home.get("currentUser") or {})

            rejected = harness.client.request(
                "POST",
                "/api/register",
                payload={"username": "email_disabled", "password": "password123", "email": "user@example.com"},
                expect_status=400,
            )
            self.assertIn("not enabled", rejected["error"])

            reset = harness.client.request(
                "POST",
                "/api/auth/email-reset",
                payload={"identifier": "email_disabled"},
                expect_status=400,
            )
            self.assertIn("not enabled", reset["error"])
        finally:
            harness.stop()


if __name__ == "__main__":
    unittest.main()
