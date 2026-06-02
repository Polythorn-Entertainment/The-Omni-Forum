from __future__ import annotations

import re

from tests.browser_base import BrowserSmokeBase, expect


class BrowserAccessibilityTests(BrowserSmokeBase):
    def test_accessibility_shell_and_modal_keyboard_flow(self) -> None:
        page = self.new_page()
        page.goto("/", wait_until="domcontentloaded")
        self.wait_for_app(page)

        expect(page.locator(".skip-link")).to_have_attribute("href", "#mainContent")
        expect(page.locator("main")).to_have_attribute("id", "mainContent")
        expect(page.locator("#toastContainer")).to_have_attribute("aria-live", "polite")
        expect(page.locator("#modalOverlay")).to_have_attribute("aria-hidden", "true")

        self.open_menu(page)
        self.click_menu_item(page, "Log In")
        expect(page.locator("#modal")).to_have_attribute("role", "dialog")
        expect(page.locator("#modal")).to_have_attribute("aria-modal", "true")
        expect(page.locator("#modal")).to_have_attribute("aria-label", re.compile(r"Log In"))
        expect(page.locator("#modal .modal-close")).to_have_attribute("aria-label", "Close dialog")
        expect(page.locator("#modalOverlay")).to_have_attribute("aria-hidden", "false")
        self.assertTrue(
            page.evaluate("() => document.getElementById('modal').contains(document.activeElement)"),
            "Modal did not move focus inside the dialog.",
        )
        for _ in range(4):
            page.keyboard.press("Tab")
            self.assertTrue(
                page.evaluate("() => document.getElementById('modal').contains(document.activeElement)"),
                "Tab escaped the open modal.",
            )
        page.keyboard.press("Escape")
        expect(page.locator("#modalOverlay")).to_have_attribute("aria-hidden", "true")
        expect(page.locator("#modalOverlay")).to_have_class(re.compile(r"\bhidden\b"))
        self.assert_no_browser_errors()
