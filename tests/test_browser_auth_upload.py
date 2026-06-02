from __future__ import annotations

import re

try:
    from browser_base import BrowserSmokeBase, expect
except ModuleNotFoundError:  # Allows pytest to import tests as a package.
    from tests.browser_base import BrowserSmokeBase, expect


class BrowserAuthUploadTests(BrowserSmokeBase):
    def test_auth_posting_uploads_settings_and_mobile_layout(self) -> None:
        page = self.new_page()
        page.goto("/", wait_until="domcontentloaded")
        self.wait_for_app(page)
        self.assert_visual_not_blank(page, "home desktop")

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
        self.assert_visual_not_blank(page, "thread with uploaded media")
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
        expect(page.locator("#postContainer .post").filter(has_text="reply from the browser suite")).to_be_visible(
            timeout=10000
        )

        page.goto("/pages/settings.html", wait_until="domcontentloaded")
        self.wait_for_app(page)
        expect(page.locator("#settingsUsername")).to_have_value("owner_browser", timeout=10000)
        self.assert_visual_not_blank(page, "settings page")
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
        self.assert_visual_not_blank(page, "home mobile")
        self.assert_no_horizontal_overflow(page)
        self.assert_no_browser_errors()
