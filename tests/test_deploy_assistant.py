from __future__ import annotations

import unittest

try:
    from test_support import REPO_ROOT
except ModuleNotFoundError:  # Allows `python3 -m unittest tests.test_deploy_assistant -v`.
    from tests.test_support import REPO_ROOT


class DeployAssistantTests(unittest.TestCase):
    def test_runtime_env_defaults_keep_email_disabled_until_enabled(self) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location("deploy_assistant", REPO_ROOT / "scripts" / "deploy_assistant.py")
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)

        content = module.build_env_content(
            "runtime",
            {
                "publicUrl": "https://forum.example.com",
                "secureCookies": True,
                "emailAuthEnabled": False,
            },
        )
        self.assertIn("OMNIFORUM_PUBLIC_URL=https://forum.example.com", content)
        self.assertIn("OMNIFORUM_SECURE_COOKIES=1", content)
        self.assertIn("OMNIFORUM_EMAIL_AUTH_ENABLED=0", content)

    def test_remote_env_and_deploy_command_are_generated(self) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location("deploy_assistant", REPO_ROOT / "scripts" / "deploy_assistant.py")
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)

        content = module.build_env_content(
            "remote",
            {
                "deployHost": "staging.example.com",
                "deployUser": "deploy",
                "deployPath": "/srv/omniforum",
                "deployPublicUrl": "https://staging.example.com",
            },
        )
        self.assertIn("OMNIFORUM_DEPLOY_HOST=staging.example.com", content)
        self.assertIn("OMNIFORUM_DEPLOY_PATH=/srv/omniforum", content)
        self.assertIn("OMNIFORUM_DEPLOY_PUBLIC_URL=https://staging.example.com", content)
        self.assertIn("OMNIFORUM_DEPLOY_CONFIRM=yes scripts/deploy_remote.sh", module.deploy_command())

    def test_scrub_action_requires_confirmation(self) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location("deploy_assistant", REPO_ROOT / "scripts" / "deploy_assistant.py")
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)

        result = module.run_action("scrub", {"confirm": "nope"})
        self.assertFalse(result["ok"])
        self.assertIn("Type SCRUB", result["output"])

    def test_release_safety_patterns_are_shared(self) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location("deploy_assistant", REPO_ROOT / "scripts" / "deploy_assistant.py")
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)

        self.assertEqual(module.runtime_private_files(), module.scan_runtime_private_files(REPO_ROOT))

    def test_deployment_assistant_serves_split_assets_safely(self) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location("deploy_assistant", REPO_ROOT / "scripts" / "deploy_assistant.py")
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)

        self.assertIn(b"Deployment Assistant", module.read_assistant_asset("index.html"))
        self.assertIn(b"refreshStatus", module.read_assistant_asset("app.js"))
        with self.assertRaises(FileNotFoundError):
            module.read_assistant_asset("../README.md")


if __name__ == "__main__":
    unittest.main()
