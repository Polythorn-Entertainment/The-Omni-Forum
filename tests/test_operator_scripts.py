from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

try:
    from test_support import OmniForumHarness, REPO_ROOT
except ModuleNotFoundError:  # Allows `python3 -m unittest tests.test_operator_scripts -v`.
    from tests.test_support import OmniForumHarness, REPO_ROOT


class OperatorScriptTests(unittest.TestCase):
    def test_production_readiness_reports_local_state_without_failing(self) -> None:
        result = subprocess.run(
            [sys.executable, "scripts/production_readiness.py", "--json"],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=30,
        )
        self.assertEqual(0, result.returncode, result.stdout)
        payload = json.loads(result.stdout)
        self.assertIn(payload["status"], {"pass", "warn"})
        self.assertTrue(any(check["name"] == "runtime data" for check in payload["checks"]))
        self.assertFalse(any(check["status"] == "fail" for check in payload["checks"]), payload)

    def test_security_check_enforces_patched_pillow_floor(self) -> None:
        result = subprocess.run(
            [sys.executable, "scripts/security_check.py", "--json"],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=30,
        )
        self.assertEqual(0, result.returncode, result.stdout)
        payload = json.loads(result.stdout)
        dependency_checks = [check for check in payload["checks"] if check["name"] == "dependency floors"]
        self.assertEqual(1, len(dependency_checks), payload)
        self.assertEqual("pass", dependency_checks[0]["status"], payload)

    def test_healthcheck_and_migration_status_against_running_app(self) -> None:
        harness = OmniForumHarness()
        try:
            harness.start()
            health = subprocess.run(
                [sys.executable, "scripts/healthcheck.py", harness.base_url, "--json"],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
                timeout=30,
            )
            self.assertEqual(0, health.returncode, health.stdout)
            health_payload = json.loads(health.stdout)
            self.assertTrue(health_payload["ok"])
            self.assertEqual(["/api/health", "/api/home"], [check["path"] for check in health_payload["checks"]])

            migrations = subprocess.run(
                [
                    sys.executable,
                    "scripts/migration_status.py",
                    "--data-dir",
                    str(harness.workspace / "data"),
                    "--json",
                ],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
                timeout=30,
            )
            self.assertEqual(0, migrations.returncode, migrations.stdout)
            migration_payload = json.loads(migrations.stdout)
            self.assertTrue(migration_payload["allApplied"])
            self.assertTrue(migration_payload["checksumsOk"])

            load = subprocess.run(
                [
                    sys.executable,
                    "scripts/load_test.py",
                    harness.base_url,
                    "--requests",
                    "6",
                    "--concurrency",
                    "2",
                    "--json",
                ],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
                timeout=30,
            )
            self.assertEqual(0, load.returncode, load.stdout)
            load_payload = json.loads(load.stdout)
            self.assertTrue(load_payload["ok"])
        finally:
            harness.stop()

    def test_offsite_backup_local_target_and_restore_rehearsal(self) -> None:
        with tempfile.TemporaryDirectory(prefix="omniforum-offsite-") as temp_dir:
            env = os.environ.copy()
            env["OMNIFORUM_OFFSITE_BACKUP_TARGET"] = f"local:{temp_dir}"
            env["OMNIFORUM_BACKUP_ROTATION"] = "99"
            backup = subprocess.run(
                ["scripts/offsite_backup.sh", str(REPO_ROOT)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
                timeout=30,
            )
            self.assertEqual(0, backup.returncode, backup.stdout)
            artifacts = sorted(Path(temp_dir).glob("omniforum-manual-*.tar.gz"))
            self.assertTrue(artifacts, backup.stdout)
            self.assertTrue(Path(f"{artifacts[-1]}.sha256").is_file())

            restore = subprocess.run(
                ["scripts/verify_offsite_restore.sh", str(artifacts[-1]), str(REPO_ROOT)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
                timeout=45,
            )
            self.assertEqual(0, restore.returncode, restore.stdout)
            self.assertIn("Offsite restore verification passed", restore.stdout)

    def test_email_probe_stays_disabled_until_opted_in(self) -> None:
        env = os.environ.copy()
        env["OMNIFORUM_EMAIL_AUTH_ENABLED"] = "0"
        result = subprocess.run(
            [sys.executable, "scripts/probe_email_auth.py", "--to", "admin@example.com", "--dry-run"],
            cwd=REPO_ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=30,
        )
        self.assertEqual(2, result.returncode, result.stdout)
        self.assertIn("Email account features are disabled", result.stdout)

    def test_remote_deploy_requires_explicit_confirmation(self) -> None:
        env = os.environ.copy()
        env.pop("OMNIFORUM_DEPLOY_CONFIRM", None)
        env["OMNIFORUM_DEPLOY_HOST"] = "example.com"
        result = subprocess.run(
            ["scripts/deploy_remote.sh", str(REPO_ROOT)],
            cwd=REPO_ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=30,
        )
        self.assertEqual(2, result.returncode, result.stdout)
        self.assertIn("Refusing to deploy without OMNIFORUM_DEPLOY_CONFIRM=yes", result.stdout)


if __name__ == "__main__":
    unittest.main()
