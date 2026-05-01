from __future__ import annotations

import unittest

from test_support import OmniForumHarness


class PageSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.harness = OmniForumHarness()
        self.harness.start()
        self.harness.register("owner_user", "password123")
        thread_data = self.harness.client.request(
            "POST",
            "/api/sections/s-general",
            payload={"title": "Indexable Thread", "content": "Thread body for sitemap smoke tests."},
        )
        self.thread_id = int(thread_data["thread"]["id"])

    def tearDown(self) -> None:
        self.harness.stop()

    def test_pages_robots_and_sitemap(self) -> None:
        index_html = self.harness.client.request("GET", "/", parse_json=False, expect_status=200)
        self.assertIn('meta name="description"', index_html)
        self.assertIn('property="og:title"', index_html)

        thread_html = self.harness.client.request(
            "GET",
            f"/pages/thread.html?thread={self.thread_id}",
            parse_json=False,
            expect_status=200,
        )
        self.assertIn('link rel="canonical"', thread_html)
        self.assertIn("OmniForum — Thread", thread_html)

        settings_html = self.harness.client.request(
            "GET",
            "/pages/settings.html",
            parse_json=False,
            expect_status=200,
        )
        self.assertIn('meta name="robots" content="noindex, nofollow"', settings_html)

        robots = self.harness.client.request("GET", "/robots.txt", parse_json=False, expect_status=200)
        self.assertIn("Sitemap:", robots)
        self.assertIn("Disallow: /api/", robots)

        sitemap = self.harness.client.request("GET", "/sitemap.xml", parse_json=False, expect_status=200)
        self.assertIn("/pages/section.html?section=s-general", sitemap)
        self.assertIn(f"/pages/thread.html?thread={self.thread_id}", sitemap)


if __name__ == "__main__":
    unittest.main()
