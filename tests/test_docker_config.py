from __future__ import annotations

import re
import unittest

try:
    from test_support import REPO_ROOT
except ModuleNotFoundError:  # Allows `python3 -m unittest tests.test_docker_config -v`.
    from tests.test_support import REPO_ROOT


class DockerConfigTests(unittest.TestCase):
    def test_dockerfile_copies_current_split_app_and_runs_as_non_root(self) -> None:
        dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
        for expected in (
            "COPY assets ./assets",
            "COPY css ./css",
            "COPY js ./js",
            "COPY omniforum ./omniforum",
            "COPY pages ./pages",
            "COPY scripts ./scripts",
        ):
            self.assertIn(expected, dockerfile)
        self.assertIn("USER omniforum", dockerfile)
        self.assertIn('VOLUME ["/app/data"]', dockerfile)
        self.assertIn("HEALTHCHECK", dockerfile)
        self.assertIn("python scripts/container_healthcheck.py", dockerfile)

    def test_compose_uses_persistent_volume_and_container_safe_port(self) -> None:
        compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        self.assertIn("OMNIFORUM_HOST: 0.0.0.0", compose)
        self.assertIn("OMNIFORUM_PORT: 8000", compose)
        self.assertIn("${OMNIFORUM_DOCKER_PORT:-8000}:8000", compose)
        self.assertIn("omniforum-data:/app/data", compose)
        self.assertIn('test: ["CMD", "python", "scripts/container_healthcheck.py"]', compose)
        self.assertRegex(compose, re.compile(r"^volumes:\n  omniforum-data:", re.MULTILINE))
        self.assertNotIn("env_file:", compose)

    def test_dockerignore_excludes_private_runtime_and_operator_state(self) -> None:
        dockerignore = (REPO_ROOT / ".dockerignore").read_text(encoding="utf-8")
        for expected in (
            ".env",
            "data/*.db",
            "data/logs/*",
            "data/exports/*",
            "data/uploads/avatars/*",
            "deploy/omniforum-healthcheck.env",
            "deploy/omniforum-offsite-backup.env",
            "deploy/omniforum-remote-deploy.env",
        ):
            self.assertIn(expected, dockerignore)


if __name__ == "__main__":
    unittest.main()
