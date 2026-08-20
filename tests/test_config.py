from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from lvms_stat.config import ConfigError, load_config, validate_config


class ConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.temp_root = Path(self.temporary_directory.name)
        self.repo_root = self.temp_root / "repository"
        self.repo_root.mkdir()

    def test_accepts_https_landing_url_and_external_profile(self) -> None:
        profile_directory = self.temp_root / "profile"

        config = validate_config(
            {
                "landing_url": "https://lvms.example.invalid/clims/",
                "profile_directory": str(profile_directory),
            },
            repository_root=self.repo_root,
        )

        self.assertEqual(config.landing_url, "https://lvms.example.invalid/clims/")
        self.assertEqual(config.expected_origin, "https://lvms.example.invalid")
        self.assertEqual(config.profile_directory, profile_directory.resolve())

    def test_rejects_insecure_or_sensitive_landing_urls(self) -> None:
        invalid_urls = (
            "http://lvms.example.invalid/",
            "https://user:pass@lvms.example.invalid/",
            "https://lvms.example.invalid/?token=x",
            "https://lvms.example.invalid/#patient",
        )

        for landing_url in invalid_urls:
            with self.subTest(landing_url=landing_url):
                with self.assertRaises(ConfigError):
                    validate_config(
                        {
                            "landing_url": landing_url,
                            "profile_directory": str(self.temp_root / "profile"),
                        },
                        repository_root=self.repo_root,
                    )

    def test_rejects_profile_inside_repository(self) -> None:
        with self.assertRaisesRegex(ConfigError, "outside the repository"):
            validate_config(
                {
                    "landing_url": "https://lvms.example.invalid/",
                    "profile_directory": str(self.repo_root / "edge-profile"),
                },
                repository_root=self.repo_root,
            )

    def test_load_config_rejects_non_object_json(self) -> None:
        config_path = self.temp_root / "config.json"
        config_path.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")

        with self.assertRaisesRegex(ConfigError, "JSON object"):
            load_config(config_path, repository_root=self.repo_root)


if __name__ == "__main__":
    unittest.main()
