from __future__ import annotations

import base64
from io import BytesIO
import re
import unittest

from PIL import Image, ImageStat

try:
    from test_support import OmniForumHarness
except ModuleNotFoundError:  # Allows `python3 -m unittest tests.test_browser_* -v`.
    from tests.test_support import OmniForumHarness

try:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import expect, sync_playwright

    HAS_PLAYWRIGHT = True
except Exception:  # pragma: no cover - exercised when dev dependency is missing.
    PlaywrightError = Exception
    expect = None
    sync_playwright = None
    HAS_PLAYWRIGHT = False


PASSWORD = "password123"
PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


@unittest.skipUnless(
    HAS_PLAYWRIGHT,
    "Install browser test dependencies with `python3 -m pip install -r requirements-dev.txt`.",
)
class BrowserSmokeBase(unittest.TestCase):
    def setUp(self) -> None:
        self.harness = OmniForumHarness()
        self.harness.start()
        self.upload_path = self.harness.workspace / "tests" / "fixtures" / "browser-upload.png"
        self.upload_path.parent.mkdir(parents=True, exist_ok=True)
        self.upload_path.write_bytes(PNG_BYTES)
        self.contexts = []
        self.page_errors: list[str] = []

        self.playwright = sync_playwright().start()
        try:
            self.browser = self.playwright.chromium.launch(headless=True)
        except PlaywrightError as exc:
            self.playwright.stop()
            self.harness.stop()
            raise unittest.SkipTest(
                "Install the Chromium browser with `python3 -m playwright install chromium`."
            ) from exc

    def tearDown(self) -> None:
        for context in getattr(self, "contexts", []):
            context.close()
        if getattr(self, "browser", None):
            self.browser.close()
        if getattr(self, "playwright", None):
            self.playwright.stop()
        self.harness.stop()

    def new_page(self, width: int = 1280, height: int = 900):
        context = self.browser.new_context(
            base_url=self.harness.base_url,
            viewport={"width": width, "height": height},
            reduced_motion="reduce",
        )
        self.contexts.append(context)
        page = context.new_page()
        page.on("pageerror", lambda error: self.page_errors.append(str(error)))
        return page

    def wait_for_app(self, page) -> None:
        page.wait_for_selector("#app[data-js-ready='true']", timeout=10000)

    def open_menu(self, page) -> None:
        page.locator(".nav-menu-trigger").click()
        page.locator(".nav-menu-panel").wait_for(state="visible", timeout=5000)

    def click_menu_item(self, page, label: str) -> None:
        item = page.locator(".nav-menu-panel .nav-menu-item").filter(has_text=label).first
        last_error = None
        for _ in range(5):
            try:
                item.wait_for(state="visible", timeout=3000)
                item.evaluate("(node) => node.click()")
                return
            except PlaywrightError as exc:
                last_error = exc
                page.wait_for_timeout(150)
        if last_error:
            raise last_error

    def register_via_ui(self, page, username: str, password: str = PASSWORD) -> None:
        self.open_menu(page)
        self.click_menu_item(page, "Sign Up")
        page.locator("#regUsername").fill(username)
        page.locator("#regPassword").fill(password)
        page.locator("#regConfirm").fill(password)
        page.locator("#modal").get_by_role("button", name="Create Account").click()
        expect(page.locator(".nav-menu-username")).to_have_text(username, timeout=10000)

    def login_via_ui(self, page, username: str, password: str = PASSWORD) -> None:
        page.goto("/", wait_until="domcontentloaded")
        self.wait_for_app(page)
        self.open_menu(page)
        self.click_menu_item(page, "Log In")
        page.locator("#loginUsername").fill(username)
        page.locator("#loginPassword").fill(password)
        page.locator("#modal").get_by_role("button", name="Log In").click()
        expect(page.locator(".nav-menu-username")).to_have_text(username, timeout=10000)

    def logout_via_ui(self, page) -> None:
        self.open_menu(page)
        self.click_menu_item(page, "Log Out")
        expect(page.locator(".nav-menu-username")).to_have_text("Menu", timeout=10000)

    def close_modal(self, page) -> None:
        close_button = page.locator("#modal .modal-close")
        if close_button.count():
            close_button.first.click()
        expect(page.locator("#modalOverlay")).to_have_class(re.compile(r"\bhidden\b"), timeout=5000)

    def assert_no_browser_errors(self) -> None:
        self.assertEqual([], self.page_errors)

    def assert_no_horizontal_overflow(self, page) -> None:
        fits = page.evaluate("() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 2")
        self.assertTrue(fits, "Page has horizontal overflow in the tested viewport.")

    def assert_visual_not_blank(self, page, label: str) -> None:
        image = Image.open(BytesIO(page.screenshot(full_page=False))).convert("RGB")
        extrema = image.getextrema()
        stddev = sum(ImageStat.Stat(image).stddev)
        self.assertTrue(any(low != high for low, high in extrema), f"{label} screenshot is flat.")
        self.assertGreater(stddev, 1.0, f"{label} screenshot has too little visual variance.")
