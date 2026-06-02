from __future__ import annotations

import json
import sqlite3
import unittest

from test_support import OmniForumHarness


class ApiAbuseAndProtectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.harness = OmniForumHarness()
        self.harness.start()

    def tearDown(self) -> None:
        self.harness.stop()

    def test_signup_abuse_controls(self) -> None:
        owner = self.harness.register("signup_owner", "password123")
        self.assertEqual(owner["currentUser"]["role"], "owner")

        controls = self.harness.client.request("GET", "/api/admin/registration")
        self.assertEqual(controls["controls"]["settings"]["mode"], "Open")

        updated = self.harness.client.request(
            "PATCH",
            "/api/admin/registration/settings",
            payload={
                "publicRegistrationEnabled": True,
                "inviteRequired": False,
                "approvalRequired": True,
                "blockedUsernamePatterns": "blocked*\n*reserved*",
            },
        )
        self.assertEqual(updated["controls"]["settings"]["mode"], "Approval queue")

        self.harness.logout()
        pending = self.harness.register(
            "pending_user",
            "password123",
            expect_status=202,
            headers={"X-Forwarded-For": "10.40.0.2"},
        )
        self.assertTrue(pending["pendingApproval"])
        self.harness.client.request(
            "POST",
            "/api/login",
            payload={"username": "pending_user", "password": "password123"},
            expect_status=403,
        )
        self.harness.register(
            "blocked_name",
            "password123",
            expect_status=403,
            headers={"X-Forwarded-For": "10.40.0.3"},
        )

        self.harness.login("signup_owner", "password123")
        controls = self.harness.client.request("GET", "/api/admin/registration")
        self.assertEqual(controls["controls"]["pendingCount"], 1)
        pending_id = controls["controls"]["pending"][0]["id"]
        reviewed = self.harness.client.request(
            "POST",
            f"/api/admin/registrations/{pending_id}/review",
            payload={"action": "approve", "note": "Looks legitimate."},
        )
        self.assertEqual(reviewed["controls"]["pendingCount"], 0)

        self.harness.logout()
        approved = self.harness.login("pending_user", "password123")
        self.assertEqual(approved["currentUser"]["username"], "pending_user")

        self.harness.logout()
        self.harness.login("signup_owner", "password123")
        self.harness.client.request(
            "PATCH",
            "/api/admin/registration/settings",
            payload={
                "publicRegistrationEnabled": False,
                "inviteRequired": True,
                "approvalRequired": False,
                "blockedUsernamePatterns": "blocked*\n*reserved*",
            },
        )
        invite = self.harness.client.request(
            "POST",
            "/api/admin/invites",
            payload={"code": "INVITE123", "maxUses": 1, "note": "Smoke test invite"},
        )
        self.assertEqual(invite["invite"]["code"], "INVITE123")

        self.harness.logout()
        self.harness.register(
            "no_invite_user",
            "password123",
            expect_status=400,
            headers={"X-Forwarded-For": "10.40.0.4"},
        )
        invited = self.harness.register(
            "invited_user",
            "password123",
            invite_code="INVITE123",
            headers={"X-Forwarded-For": "10.40.0.5"},
        )
        self.assertEqual(invited["currentUser"]["username"], "invited_user")
        self.harness.logout()
        self.harness.register(
            "second_invited",
            "password123",
            invite_code="INVITE123",
            expect_status=403,
            headers={"X-Forwarded-For": "10.40.0.6"},
        )

    def test_mutating_api_rejects_bad_csrf_token(self) -> None:
        self.harness.register("csrf_owner", "password123")
        self.harness.client.request(
            "POST",
            "/api/sections/s-general",
            payload={"title": "Rejected CSRF Thread", "content": "This should not be created."},
            headers={"X-CSRF-Token": "definitely-wrong"},
            expect_status=403,
        )

        home = self.harness.client.request("GET", "/api/home")
        general = next(
            section
            for category in home["categories"]
            for section in category["sections"]
            if section["id"] == "s-general"
        )
        self.assertEqual(0, general["threads"])

    def test_persistent_rate_limits_survive_restart(self) -> None:
        headers = {"X-Forwarded-For": "10.51.0.8"}
        for index in range(12):
            self.harness.client.request(
                "POST",
                "/api/login",
                payload={"username": f"missing_user_{index}", "password": "wrong-password"},
                headers=headers,
                expect_status=401,
            )

        with sqlite3.connect(self.harness.workspace / "data" / "audit.db") as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM rate_limit_events WHERE action = 'login' AND identity = 'ip:10.51.0.8'"
            ).fetchone()[0]
        self.assertEqual(12, count)

        self.harness.restart()
        self.harness.client.request(
            "POST",
            "/api/login",
            payload={"username": "still_missing", "password": "wrong-password"},
            headers=headers,
            expect_status=429,
        )


if __name__ == "__main__":
    unittest.main()
