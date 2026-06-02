from __future__ import annotations

import re

from tests.browser_base import BrowserSmokeBase, PASSWORD, expect


class BrowserAdminFlowTests(BrowserSmokeBase):
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
        self.assert_visual_not_blank(page, "operations modal")
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
        expect(page.locator("#modal")).to_contain_text("Saved macros are available", timeout=10000)
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
