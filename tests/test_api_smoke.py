from __future__ import annotations

import json
import sqlite3
import unittest

from test_support import OmniForumHarness


class ApiSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.harness = OmniForumHarness()
        self.harness.start()

    def tearDown(self) -> None:
        self.harness.stop()

    def test_api_live_plugins_backup_and_moderation(self) -> None:
        owner = self.harness.register("owner_user", "password123")
        self.assertEqual(owner["currentUser"]["role"], "owner")

        settings = self.harness.client.request(
            "PATCH",
            "/api/me",
            payload={"bio": "Automated test owner bio.", "recoveryDiscordUsername": "owner.smoke"},
        )
        self.assertEqual(settings["currentUser"]["bio"], "Automated test owner bio.")
        self.assertEqual(settings["currentUser"]["recovery"]["discordUsername"], "owner.smoke")

        recovery = self.harness.client.request(
            "POST",
            "/api/me/recovery-codes",
            payload={"currentPassword": "password123"},
        )
        self.assertEqual(8, len(recovery["codes"]))
        self.assertGreaterEqual(recovery["summary"]["active"], 8)

        plugins = self.harness.client.request("GET", "/api/plugins?includeAll=1")
        self.assertTrue(any(plugin["id"] == "smoke-plugin" for plugin in plugins["plugins"]))

        asset_text = self.harness.client.request(
            "GET",
            "/plugins/smoke-plugin/client/smoke.txt",
            parse_json=False,
            expect_status=200,
        )
        self.assertIn("plugin asset", asset_text)

        disabled = self.harness.client.request(
            "PATCH",
            "/api/plugins/smoke-plugin",
            payload={"enabled": False},
        )
        self.assertFalse(disabled["plugin"]["enabled"])
        self.harness.client.request(
            "GET",
            "/plugins/smoke-plugin/client/smoke.txt",
            parse_json=False,
            expect_status=404,
        )
        self.harness.client.request(
            "PATCH",
            "/api/plugins/smoke-plugin",
            payload={"enabled": True},
        )

        home = self.harness.client.request("GET", "/api/home")
        general = next(section for category in home["categories"] for section in category["sections"] if section["id"] == "s-general")
        self.assertEqual(general["id"], "s-general")

        thread_data = self.harness.client.request(
            "POST",
            "/api/sections/s-general",
            payload={"title": "Smoke Thread", "content": "Opening thread body for tests."},
        )
        thread_id = int(thread_data["thread"]["id"])

        reply_data = self.harness.client.request(
            "POST",
            f"/api/threads/{thread_id}/posts",
            payload={"content": "Automated reply body."},
        )
        reply_post_id = int(reply_data["post"]["id"])
        self.assertTrue(reply_post_id)

        stream_text = self.harness.client.request(
            "GET",
            f"/api/live/stream?threadId={thread_id}&once=1",
            parse_json=False,
            expect_status=200,
            headers={"Accept": "text/event-stream"},
        )
        self.assertIn("event: snapshot", stream_text)
        snapshot_line = next(line for line in stream_text.splitlines() if line.startswith("data: "))
        snapshot = json.loads(snapshot_line[6:])
        self.assertEqual(snapshot["thread"]["id"], thread_id)

        thread_update = self.harness.client.request(
            "PATCH",
            f"/api/threads/{thread_id}",
            payload={
                "title": "Smoke Thread",
                "tags": "smoke, api",
                "featured": True,
                "staffNote": "Staff note created by the API smoke test.",
            },
        )
        self.assertTrue(thread_update["thread"]["featured"])
        self.assertTrue(thread_update["thread"]["staffNotes"])

        split = self.harness.client.request(
            "POST",
            f"/api/threads/{thread_id}/split",
            payload={
                "postId": reply_post_id,
                "title": "Smoke Split Thread",
                "sectionId": "s-general",
                "tags": "smoke, split",
            },
        )
        split_thread_id = int(split["thread"]["id"])
        self.assertNotEqual(thread_id, split_thread_id)
        self.assertEqual(split["thread"]["title"], "Smoke Split Thread")

        search = self.harness.client.request(
            "GET",
            "/api/search?section=s-general&replies=unanswered&media=all&date=year",
        )
        self.assertTrue(any(item["id"] == thread_id for item in search["threads"]))

        report = self.harness.client.request(
            "POST",
            "/api/reports",
            payload={
                "targetType": "thread",
                "targetId": thread_id,
                "reason": "Smoke triage",
                "details": "Report created to test internal notes and SLA workflow.",
            },
        )
        self.assertTrue(report["submitted"])
        reports = self.harness.client.request("GET", "/api/reports")
        report_id = int(reports["items"][0]["id"])
        macro = self.harness.client.request(
            "POST",
            "/api/reports/macros",
            payload={"title": "Smoke Macro", "category": "triage", "body": "Macro body for smoke testing."},
        )
        self.assertTrue(any(item["title"] == "Smoke Macro" for item in macro["macros"]))
        note = self.harness.client.request(
            "POST",
            f"/api/reports/{report_id}/notes",
            payload={"note": "Internal staff discussion note from smoke test."},
        )
        self.assertTrue(any(item["id"] == report_id for item in note["items"]))
        report_update = self.harness.client.request(
            "PATCH",
            f"/api/reports/{report_id}",
            payload={
                "status": "open",
                "adminNote": "Macro body for smoke testing.",
                "priority": "urgent",
                "category": "abuse",
                "assignedTo": owner["currentUser"]["id"],
                "resolutionCode": "triage-open",
                "slaHours": 24,
                "escalated": True,
                "escalationNote": "Needs owner review.",
            },
        )
        updated_report = next(item for item in report_update["items"] if item["id"] == report_id)
        self.assertEqual("urgent", updated_report["priority"])
        self.assertTrue(updated_report["internalNotes"])
        self.assertIsNotNone(updated_report["slaDueAt"])
        self.assertIsNotNone(updated_report["escalatedAt"])

        backup = self.harness.client.request("POST", "/api/admin/backup")
        self.assertIn("filename", backup)
        guide = self.harness.client.request("GET", f"/api/admin/backups/guide?file={backup['filename']}")
        self.assertEqual(guide["guide"]["filename"], backup["filename"])
        self.assertTrue(guide["guide"]["restore"]["command"].endswith(str(self.harness.workspace)))

        self.harness.logout()
        member = self.harness.register("member_user", "password123")
        member_id = int(member["currentUser"]["id"])
        self.harness.logout()
        self.harness.login("owner_user", "password123")
        moderation = self.harness.client.request(
            "POST",
            f"/api/users/{member_id}/moderation",
            payload={"action": "warn", "reason": "Automated moderation smoke test warning."},
        )
        self.assertEqual(moderation["message"], "Warning logged.")

        health = self.harness.client.request("GET", "/api/admin/health")
        health_payload = health["health"]
        self.assertEqual("OmniForum", health_payload["runtime"]["site"]["siteName"])
        self.assertGreaterEqual(health_payload["storage"]["backupCount"], 1)
        self.assertGreaterEqual(health_payload["storage"]["databaseTotalBytes"], 1)
        self.assertIn("users.db", health_payload["storage"]["databases"])
        self.assertIn("mediaUsage", health_payload["storage"])
        self.assertIn("backupStatus", health_payload["storage"])
        self.assertEqual("ok", health_payload["storage"]["backupStatus"]["check"]["status"])
        self.assertIn("recovery", health_payload)
        self.assertTrue(health_payload["recovery"]["restoreScript"]["exists"])
        self.assertIn("logs", health_payload)
        self.assertIn("latestErrors", health_payload["logs"])
        self.assertGreaterEqual(health_payload["queues"]["totalOpen"], 0)
        self.assertGreaterEqual(health_payload["pluginStatus"]["total"], 1)
        self.assertIn("onboarding", health_payload)
        self.assertIn("installChecks", health_payload)
        self.assertGreaterEqual(health_payload["onboarding"]["total"], 1)
        self.assertGreaterEqual(health_payload["installChecks"]["total"], 1)
        self.assertIn("topSearchTerms30d", health_payload["analytics"])
        self.assertTrue(any(item["query"] == "(filtered browse)" for item in health_payload["analytics"]["topSearchTerms30d"]))
        audit = self.harness.client.request("GET", "/api/admin/audit?limit=100")
        audit_actions = {item["action"] for item in audit["audit"]["items"]}
        self.assertIn("backup_create", audit_actions)
        self.assertIn("restore_guide_view", audit_actions)
        self.assertIn("plugin_update", audit_actions)
        self.assertIn("warn", audit_actions)
        self.assertIn("thread_split", audit_actions)
        self.assertIn("thread_note_create", audit_actions)
        self.assertGreaterEqual(audit["audit"]["summary"]["total"], 4)
        backup_audit = self.harness.client.request("GET", "/api/admin/audit?q=backup&category=operations")
        self.assertTrue(any(item["action"] == "backup_create" for item in backup_audit["audit"]["items"]))

        site_update = self.harness.client.request(
            "PATCH",
            "/api/admin/site-settings",
            payload={
                "siteName": "Smoke Forum",
                "logoText": "Smoke Forum",
                "heroTitle": "Smoke Forum",
                "defaultTheme": "seaglass",
                "supportDiscord": "smoke.admin",
                "footerLinks": [{"label": "Rules", "url": "/pages/rules.html"}],
            },
        )
        self.assertEqual("Smoke Forum", site_update["site"]["siteName"])
        self.assertEqual("seaglass", site_update["site"]["defaultTheme"])
        public_site = self.harness.client.request("GET", "/api/site")
        self.assertEqual("Smoke Forum", public_site["site"]["siteName"])
        export = self.harness.client.request("GET", "/api/admin/export?type=settings&format=json")
        self.assertIn("Smoke Forum", export["export"]["content"])
        csv_export = self.harness.client.request("GET", "/api/admin/export?type=users&format=csv")
        self.assertIn("owner_user", csv_export["export"]["content"])
        preview = self.harness.client.request(
            "POST",
            "/api/admin/import-preview",
            payload={"content": export["export"]["content"]},
        )
        self.assertTrue(preview["preview"]["valid"])

        self.harness.logout()
        recovered = self.harness.client.request(
            "POST",
            "/api/login",
            payload={"username": "owner_user", "password": "", "recoveryCode": recovery["codes"][0]},
        )
        self.assertTrue(recovered["currentUser"]["mustResetPassword"])
        self.harness.client.request(
            "PATCH",
            "/api/me/password",
            payload={"newPassword": "password456"},
        )

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
