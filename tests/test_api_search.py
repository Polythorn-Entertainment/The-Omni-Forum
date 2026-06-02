from __future__ import annotations

import json
import sqlite3
import unittest

from test_support import OmniForumHarness


class ApiSearchIndexTests(unittest.TestCase):
    def setUp(self) -> None:
        self.harness = OmniForumHarness()
        self.harness.start()

    def tearDown(self) -> None:
        self.harness.stop()

    def test_incremental_search_index_updates_content_changes(self) -> None:
        self.harness.register("search_owner", "password123")
        thread_data = self.harness.client.request(
            "POST",
            "/api/sections/s-general",
            payload={"title": "Alpha Quartzneedle", "content": "Opening body with oldthreadtoken."},
        )
        thread_id = int(thread_data["thread"]["id"])

        search = self.harness.client.request("GET", "/api/search?q=quartzneedle")
        self.assertTrue(any(item["id"] == thread_id for item in search["threads"]))

        self.harness.client.request(
            "PATCH",
            f"/api/threads/{thread_id}",
            payload={"title": "Beta Zirconneedle", "tags": "zirconneedle"},
        )
        updated_search = self.harness.client.request("GET", "/api/search?q=zirconneedle")
        self.assertTrue(any(item["id"] == thread_id for item in updated_search["threads"]))
        old_search = self.harness.client.request("GET", "/api/search?q=quartzneedle")
        self.assertFalse(any(item["id"] == thread_id for item in old_search["threads"]))

        reply_data = self.harness.client.request(
            "POST",
            f"/api/threads/{thread_id}/posts",
            payload={"content": "Reply body with amberposttoken."},
        )
        post_id = int(reply_data["post"]["id"])
        post_search = self.harness.client.request("GET", "/api/search?q=amberposttoken")
        self.assertTrue(any(item["id"] == post_id for item in post_search["posts"]))

        self.harness.client.request(
            "PATCH",
            f"/api/posts/{post_id}",
            payload={"content": "Reply body with sapphireposttoken."},
        )
        new_post_search = self.harness.client.request("GET", "/api/search?q=sapphireposttoken")
        self.assertTrue(any(item["id"] == post_id for item in new_post_search["posts"]))
        old_post_search = self.harness.client.request("GET", "/api/search?q=amberposttoken")
        self.assertFalse(any(item["id"] == post_id for item in old_post_search["posts"]))

        self.harness.client.request("DELETE", f"/api/posts/{post_id}")
        deleted_post_search = self.harness.client.request("GET", "/api/search?q=sapphireposttoken")
        self.assertFalse(any(item["id"] == post_id for item in deleted_post_search["posts"]))


if __name__ == "__main__":
    unittest.main()
