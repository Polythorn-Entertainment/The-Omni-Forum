from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class StructureTests(unittest.TestCase):
    def test_source_files_stay_below_large_file_ceiling(self) -> None:
        checked_roots = ("omniforum", "js", "css", "tests", "scripts")
        large_files: list[str] = []
        for root in checked_roots:
            for path in (ROOT / root).glob("*"):
                if path.suffix not in {".py", ".js", ".css"}:
                    continue
                line_count = len(path.read_text(encoding="utf-8").splitlines())
                if line_count > 750:
                    large_files.append(f"{path.relative_to(ROOT)} has {line_count} lines")
        self.assertEqual([], large_files)

    def test_schema_facade_reexports_focused_schema_helpers(self) -> None:
        from omniforum import schema
        from omniforum import schema_core
        from omniforum import schema_defaults
        from omniforum import schema_maintenance
        from omniforum import schema_search
        from omniforum import schema_seed

        self.assertIs(schema.init_db, schema_core.init_db)
        self.assertIs(schema.ensure_search_index_schema, schema_search.ensure_search_index_schema)
        self.assertIs(schema.ensure_column, schema_maintenance.ensure_column)
        self.assertIs(schema.ensure_database_schema, schema_maintenance.ensure_database_schema)
        self.assertIs(schema.ensure_registration_defaults, schema_defaults.ensure_registration_defaults)
        self.assertIs(schema.ensure_site_settings_defaults, schema_defaults.ensure_site_settings_defaults)
        self.assertIs(schema.ensure_moderation_macro_defaults, schema_defaults.ensure_moderation_macro_defaults)
        self.assertIs(schema.seed_sections, schema_seed.seed_sections)

    def test_media_facade_reexports_focused_media_helpers(self) -> None:
        from omniforum import media
        from omniforum import media_images
        from omniforum import media_paths
        from omniforum import media_posts
        from omniforum import media_quota
        from omniforum import media_store
        from omniforum.errors import APIError

        self.assertIs(media.detect_image_type, media_images.detect_image_type)
        self.assertIs(media.resolve_media_path, media_paths.resolve_media_path)
        self.assertIs(media.ensure_user_media_quota, media_quota.ensure_user_media_quota)
        self.assertIs(media.store_image_upload_paths, media_store.store_image_upload_paths)
        self.assertIs(media.cleanup_orphan_post_artifacts, media_posts.cleanup_orphan_post_artifacts)

        self.assertEqual(("image/png", "png"), media.detect_image_type(b"\x89PNG\r\n\x1a\npayload"))
        self.assertEqual(("image/jpeg", "jpg"), media.detect_image_type(b"\xff\xd8\xffpayload"))
        self.assertEqual(("image/gif", "gif"), media.detect_image_type(b"GIF89apayload"))
        self.assertEqual(("image/webp", "webp"), media.detect_image_type(b"RIFFxxxxWEBPpayload"))
        with self.assertRaises(APIError):
            media.detect_image_type(b"not an image")
        self.assertIsNone(media.resolve_media_path("../users.db"))
        self.assertIsNone(media.resolve_media_path("unknown/file.png"))
        self.assertIsNotNone(media.resolve_media_path("avatars/example.png"))

    def test_domain_facade_reexports_focused_helpers_without_peer_injection(self) -> None:
        from omniforum import domain

        facade_source = (ROOT / "omniforum" / "domain.py").read_text(encoding="utf-8")
        focused_sources = "\n".join(
            path.read_text(encoding="utf-8") for path in (ROOT / "omniforum").glob("domain_*.py")
        )

        self.assertIsNotNone(domain.serialize_user)
        self.assertIsNotNone(domain.get_live_snapshot)
        self.assertNotIn("_install_peer_globals", facade_source)
        self.assertNotIn("Peer domain helpers", focused_sources)
        self.assertNotIn("Injected names", focused_sources)

    def test_thread_domain_facade_reexports_focused_thread_helpers(self) -> None:
        from omniforum import domain_posts
        from omniforum import domain_sections
        from omniforum import domain_thread_lists
        from omniforum import domain_thread_membership
        from omniforum import domain_thread_records
        from omniforum import domain_threads

        self.assertIs(domain_threads.thread_first_post_id, domain_thread_membership.thread_first_post_id)
        self.assertIs(domain_threads.list_saved_threads, domain_thread_membership.list_saved_threads)
        self.assertIs(domain_threads.get_section_by_slug, domain_sections.get_section_by_slug)
        self.assertIs(domain_threads.serialize_thread, domain_thread_records.serialize_thread)
        self.assertIs(domain_threads.get_trending_threads, domain_thread_lists.get_trending_threads)
        self.assertIs(domain_threads.get_posts_for_thread, domain_posts.get_posts_for_thread)
        self.assertIs(domain_threads.list_post_edit_history, domain_posts.list_post_edit_history)

    def test_admin_api_facade_uses_focused_mixins(self) -> None:
        from omniforum.api_admin import AdminApiMixin
        from omniforum.api_admin_backups import BackupAdminApiMixin
        from omniforum.api_admin_data import DataAdminApiMixin
        from omniforum.api_admin_exporting import ExportAdminApiMixin
        from omniforum.api_admin_plugins import PluginAdminApiMixin
        from omniforum.api_admin_registration import RegistrationAdminApiMixin
        from omniforum.api_admin_settings import SettingsAdminApiMixin
        from omniforum.api_admin_status import StatusAdminApiMixin

        for mixin in (
            BackupAdminApiMixin,
            DataAdminApiMixin,
            ExportAdminApiMixin,
            PluginAdminApiMixin,
            RegistrationAdminApiMixin,
            SettingsAdminApiMixin,
            StatusAdminApiMixin,
        ):
            self.assertTrue(issubclass(AdminApiMixin, mixin))

    def test_thread_api_facade_uses_focused_mixins(self) -> None:
        from omniforum.api_content_thread_create import CreateThreadContentApiMixin
        from omniforum.api_content_thread_delete import DeleteThreadContentApiMixin
        from omniforum.api_content_thread_membership import MembershipThreadContentApiMixin
        from omniforum.api_content_thread_polls import PollThreadContentApiMixin
        from omniforum.api_content_thread_split import SplitThreadContentApiMixin
        from omniforum.api_content_thread_update import UpdateThreadContentApiMixin
        from omniforum.api_content_thread_view import ViewThreadContentApiMixin
        from omniforum.api_content_threads import ThreadContentApiMixin

        for mixin in (
            CreateThreadContentApiMixin,
            DeleteThreadContentApiMixin,
            MembershipThreadContentApiMixin,
            PollThreadContentApiMixin,
            SplitThreadContentApiMixin,
            UpdateThreadContentApiMixin,
            ViewThreadContentApiMixin,
        ):
            self.assertTrue(issubclass(ThreadContentApiMixin, mixin))

    def test_validation_facade_reexports_focused_validation_helpers(self) -> None:
        from omniforum import validation
        from omniforum import validation_content
        from omniforum import validation_limits
        from omniforum import validation_pagination
        from omniforum import validation_profile
        from omniforum import validation_registration
        from omniforum import validation_site
        from omniforum import validation_text

        self.assertIs(validation.clean_text, validation_text.clean_text)
        self.assertIs(validation.clean_username, validation_registration.clean_username)
        self.assertIs(validation.get_site_settings, validation_site.get_site_settings)
        self.assertIs(validation.clean_email, validation_profile.clean_email)
        self.assertIs(validation.clean_poll_payload, validation_content.clean_poll_payload)
        self.assertIs(validation.resolve_pagination, validation_pagination.resolve_pagination)
        self.assertIs(validation.count_links, validation_limits.count_links)

    def test_backend_facades_are_explicit(self) -> None:
        for relative_path in (
            "omniforum/api_admin.py",
            "omniforum/api_content_threads.py",
            "omniforum/domain.py",
            "omniforum/domain_threads.py",
            "omniforum/media.py",
            "omniforum/schema.py",
            "omniforum/validation.py",
        ):
            source = (ROOT / relative_path).read_text(encoding="utf-8")
            self.assertNotIn("import *", source)

    def test_frontend_bundle_order_is_explicit(self) -> None:
        index_html = (ROOT / "index.html").read_text(encoding="utf-8")
        settings_html = (ROOT / "pages" / "settings.html").read_text(encoding="utf-8")
        thread_html = (ROOT / "pages" / "thread.html").read_text(encoding="utf-8")
        css_bundle = (ROOT / "css" / "main.css").read_text(encoding="utf-8")

        self.assertLess(index_html.index("js/api-core.js"), index_html.index("js/api.js"))
        self.assertLess(index_html.index("js/data-core.js"), index_html.index("js/data.js"))
        self.assertLess(index_html.index("js/modal.js"), index_html.index("js/action-delegation.js"))
        self.assertLess(index_html.index("js/layout-feedback-ui.js"), index_html.index("js/layout-ui.js"))
        self.assertLess(index_html.index("js/admin-ops-components.js"), index_html.index("js/admin-ops-ui.js"))
        self.assertLess(index_html.index("js/profile-staff-ui.js"), index_html.index("js/profile-ui.js"))
        self.assertLess(index_html.index("js/admin-ops-ui.js"), index_html.index("js/admin-ui.js"))
        self.assertLess(
            thread_html.index("../js/page-thread-state.js"),
            thread_html.index("../js/page-thread.js"),
        )
        section_html = (ROOT / "pages" / "section.html").read_text(encoding="utf-8")
        self.assertLess(
            section_html.index("../js/page-section-state.js"),
            section_html.index("../js/page-section.js"),
        )
        self.assertLess(
            settings_html.index("../js/page-settings-helpers.js"),
            settings_html.index("../js/page-settings.js"),
        )
        self.assertLess(css_bundle.index("./base.css"), css_bundle.index("./responsive.css"))


if __name__ == "__main__":
    unittest.main()
