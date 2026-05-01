from __future__ import annotations

import base64
import re
import unittest

try:
    from test_support import OmniForumHarness
except ModuleNotFoundError:  # Allows `python3 -m unittest tests.test_browser_smoke -v`.
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
class BrowserSmokeTests(unittest.TestCase):
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
        fits = page.evaluate(
            "() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 2"
        )
        self.assertTrue(fits, "Page has horizontal overflow in the tested viewport.")

    def test_auth_posting_uploads_settings_and_mobile_layout(self) -> None:
        page = self.new_page()
        page.goto("/", wait_until="domcontentloaded")
        self.wait_for_app(page)

        self.register_via_ui(page, "owner_browser")
        expect(page.locator(".nav-menu-role")).to_contain_text("Owner")

        page.goto("/pages/section.html?section=s-general", wait_until="domcontentloaded")
        self.wait_for_app(page)
        expect(page.locator("#newThreadBtn")).to_have_text("+ New Thread", timeout=10000)
        page.locator("#newThreadBtn").click()
        page.locator("#newThreadTitle").fill("Browser Composer Thread")
        page.locator("#newThreadTags").fill("browser, automation")
        page.locator("#newThreadContent").fill("**Markdown** opening post with an uploaded image.")
        page.locator("#modal").get_by_role("button", name="Quote").click()
        page.locator("#modal").get_by_role("button", name="List").click()
        new_thread_value = page.locator("#newThreadContent").input_value()
        self.assertIn("\n> ", new_thread_value)
        self.assertIn("\n- ", new_thread_value)
        page.locator("#newThreadMedia").set_input_files(str(self.upload_path))
        expect(page.locator("#newThreadUploadPreview img")).to_be_visible(timeout=10000)
        page.locator("#upload-alt-0").fill("Browser upload alt text")
        page.locator("#modal").get_by_role("button", name="Post Thread").click()
        page.wait_for_url(re.compile(r".*/pages/thread\.html\?thread=\d+.*"), timeout=10000)
        expect(page.locator("#threadHeader")).to_contain_text("Browser Composer Thread", timeout=10000)
        expect(page.locator("#postContainer .inline-media-card img")).to_be_visible(timeout=10000)
        expect(page.locator("#postContainer .inline-media-card img").first).to_have_attribute(
            "src",
            re.compile(r"/media/thumbs/"),
            timeout=10000,
        )

        page.locator("#replyContent").fill("@own")
        expect(page.locator(".mention-suggestion").filter(has_text="owner_browser")).to_be_visible(timeout=10000)
        page.locator(".mention-suggestion").filter(has_text="owner_browser").first.click()
        page.locator("#replyContent").type(" reply from the browser suite.")
        page.locator("#replyArea").get_by_role("button", name="Quote").click()
        page.locator("#replyArea").get_by_role("button", name="List").click()
        reply_value = page.locator("#replyContent").input_value()
        self.assertIn("\n> ", reply_value)
        self.assertIn("\n- ", reply_value)
        page.locator("#replyMedia").set_input_files(str(self.upload_path))
        expect(page.locator("#replyUploadPreview img")).to_be_visible(timeout=10000)
        page.get_by_role("button", name="Post Reply").click()
        expect(page.locator("#postContainer .post").filter(has_text="reply from the browser suite")).to_be_visible(timeout=10000)

        page.goto("/pages/settings.html", wait_until="domcontentloaded")
        self.wait_for_app(page)
        expect(page.locator("#settingsUsername")).to_have_value("owner_browser", timeout=10000)
        page.locator("#settingsBio").fill("Browser test bio.")
        page.locator("#settingsStatusText").fill("Testing the browser suite")
        page.locator("#settingsSignature").fill("[b]Automated signature[/b]")
        page.locator("#settingsAvatarInput").set_input_files(str(self.upload_path))
        page.get_by_role("button", name="Save Profile").click()
        expect(page.locator(".toast.success").filter(has_text="Profile updated")).to_be_visible(timeout=10000)
        expect(page.locator("#settingsBio")).to_have_value("Browser test bio.", timeout=10000)

        page.set_viewport_size({"width": 390, "height": 844})
        page.goto("/", wait_until="domcontentloaded")
        self.wait_for_app(page)
        expect(page.locator(".nav-menu-trigger")).to_be_visible(timeout=10000)
        self.assert_no_horizontal_overflow(page)
        self.assert_no_browser_errors()

    def test_dms_reports_moderation_and_admin_tools(self) -> None:
        owner = self.harness.register("owner_staff", PASSWORD)["currentUser"]
        self.harness.logout()
        member = self.harness.register("member_staff", PASSWORD)["currentUser"]
        thread_data = self.harness.client.request(
            "POST",
            "/api/sections/s-general",
            payload={
                "title": "Reportable Browser Thread",
                "content": "Thread content created for report queue browser coverage.",
            },
        )
        thread_id = int(thread_data["thread"]["id"])
        self.harness.logout()

        page = self.new_page()
        self.login_via_ui(page, "member_staff")
        self.open_menu(page)
        expect(page.locator(".nav-menu-panel")).not_to_contain_text("Operations")
        expect(page.locator(".nav-menu-panel")).not_to_contain_text("Reports Queue")
        page.keyboard.press("Escape")

        page.goto(f"/pages/thread.html?thread={thread_id}", wait_until="domcontentloaded")
        self.wait_for_app(page)
        page.locator("#threadHeader").get_by_role("button", name="Report").click()
        page.locator("#reportDetails").fill("Browser report detail for staff review.")
        page.locator("#modal").get_by_role("button", name="Submit Report").click()
        expect(page.locator(".toast.success").filter(has_text="Report submitted")).to_be_visible(timeout=10000)

        page.goto("/pages/members.html", wait_until="domcontentloaded")
        self.wait_for_app(page)
        page.locator(".member-card").filter(has_text="owner_staff").click()
        expect(page.locator("#modal")).to_contain_text("owner_staff", timeout=10000)
        page.locator("#modal").get_by_role("button", name="Message").click()
        page.locator("#dmComposeBody").fill("Browser DM to owner.")
        page.locator("#modal").get_by_role("button", name="Send Message").click()
        expect(page.locator("#modal")).to_contain_text("Browser DM to owner.", timeout=10000)

        self.close_modal(page)
        self.logout_via_ui(page)
        self.login_via_ui(page, "owner_staff")
        self.open_menu(page)
        self.click_menu_item(page, "Alerts")
        expect(page.locator("#modal")).to_contain_text("Alerts", timeout=10000)
        expect(page.locator("#modal")).to_contain_text("DMs", timeout=10000)
        page.locator("#modal").get_by_role("button", name=re.compile(r"DMs")).click()
        expect(page.locator("#modal")).to_contain_text("Browser DM to owner.", timeout=10000)
        self.close_modal(page)
        self.open_menu(page)
        self.click_menu_item(page, "Messages")
        expect(page.locator("#modal")).to_contain_text("Browser DM to owner.", timeout=10000)
        page.locator("#dmReplyBody").fill("Owner reply from browser.")
        page.locator("#modal").get_by_role("button", name="Send Reply").click()
        expect(page.locator("#modal")).to_contain_text("Owner reply from browser.", timeout=10000)

        self.close_modal(page)
        self.open_menu(page)
        self.click_menu_item(page, "Reports Queue")
        expect(page.locator("#modal")).to_contain_text("Browser report detail for staff review.", timeout=10000)
        report_card = page.locator(".notice-card").filter(has_text="Browser report detail for staff review.").first
        report_card.get_by_role("button", name="Resolve").click()
        expect(page.locator("#modal")).to_contain_text("No open reports", timeout=10000)

        self.close_modal(page)
        page.goto("/pages/members.html", wait_until="domcontentloaded")
        self.wait_for_app(page)
        page.locator(".member-card").filter(has_text="member_staff").click()
        expect(page.locator("#modal")).to_contain_text("Moderation Actions", timeout=10000)
        page.locator("#moderationAction").select_option("warn")
        page.locator("#moderationReason").fill("Browser moderation warning.")
        page.locator("#moderationSubmitButton").click()
        expect(page.locator("#modal")).to_contain_text("Browser moderation warning.", timeout=10000)

        self.close_modal(page)
        self.open_menu(page)
        self.click_menu_item(page, "Operations")
        expect(page.locator("#modal")).to_contain_text("Operations", timeout=10000)
        expect(page.locator("#modal")).to_contain_text("Production Health", timeout=10000)
        expect(page.locator("#modal")).to_contain_text("Database Storage", timeout=10000)
        expect(page.locator("#modal")).to_contain_text("Media Usage", timeout=10000)
        expect(page.locator("#modal")).to_contain_text("Recovery Readiness", timeout=10000)
        expect(page.locator("#modal")).to_contain_text("Latest Errors", timeout=10000)
        page.locator("#modal").get_by_role("button", name="Setup Wizard").click()
        expect(page.locator("#modal")).to_contain_text("First-Run Setup Wizard", timeout=10000)
        expect(page.locator("#modal")).to_contain_text("Branding & Homepage", timeout=10000)
        page.locator("#modal").get_by_role("button", name="Back to Operations").click()
        expect(page.locator("#modal")).to_contain_text("Operations", timeout=10000)
        page.locator("#modal").get_by_role("button", name="Import / Export").click()
        expect(page.locator("#modal")).to_contain_text("Import / Export Tools", timeout=10000)
        page.locator("#modal").get_by_role("button", name="Back to Operations").click()
        expect(page.locator("#modal")).to_contain_text("Operations", timeout=10000)
        page.locator("#modal").get_by_role("button", name="Staff Workflows").click()
        expect(page.locator("#modal")).to_contain_text("Staff Workflow Tools", timeout=10000)
        expect(page.locator("#modal")).to_contain_text("saved moderation macros", timeout=10000)
        page.locator("#modal").get_by_role("button", name="Back to Operations").click()
        expect(page.locator("#modal")).to_contain_text("Operations", timeout=10000)
        page.locator("#modal").get_by_role("button", name="Audit Log").click()
        expect(page.locator("#modal")).to_contain_text("Audit Log", timeout=10000)
        expect(page.locator("#modal")).to_contain_text("Browser moderation warning.", timeout=10000)
        page.locator("#modal").get_by_role("button", name="Back to Operations").click()
        expect(page.locator("#modal")).to_contain_text("Operations", timeout=10000)
        page.locator("#modal").get_by_role("button", name="Signup Controls").click()
        expect(page.locator("#modal")).to_contain_text("Signup Controls", timeout=10000)
        expect(page.locator("#modal")).to_contain_text("Registration Settings", timeout=10000)
        page.locator("#modal").get_by_role("button", name="Back to Operations").click()
        expect(page.locator("#modal")).to_contain_text("Operations", timeout=10000)
        page.locator("#modal").get_by_role("button", name="Manage Plugins").click()
        expect(page.locator("#modal")).to_contain_text("Smoke Plugin", timeout=10000)

        self.close_modal(page)
        self.open_menu(page)
        self.click_menu_item(page, "Section Editor")
        expect(page.locator("#modal")).to_contain_text("Section Manager", timeout=10000)
        expect(page.locator("#modal")).to_contain_text("General Discussion", timeout=10000)

        self.assertEqual("owner_staff", owner["username"])
        self.assertEqual("member_staff", member["username"])
        self.assert_no_browser_errors()


if __name__ == "__main__":
    unittest.main()
