from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit


class ConfigError(ValueError):
    """Local probe configuration is missing or unsafe."""


@dataclass(frozen=True)
class ProbeConfig:
    landing_url: str
    expected_origin: str
    profile_directory: Path


def _required_text(raw: Mapping[str, object], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{key} must be a non-empty string")
    return value.strip()


def validate_config(
    raw: Mapping[str, object],
    *,
    repository_root: Path,
    allowed_profile_root: Path | None = None,
) -> ProbeConfig:
    landing_url = _required_text(raw, "landing_url")
    parsed = urlsplit(landing_url)

    try:
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise ConfigError("landing_url has an invalid host or port") from exc

    if parsed.scheme != "https" or not hostname:
        raise ConfigError("landing_url must be an HTTPS URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ConfigError(
            "landing_url must not contain credentials, query, or fragment"
        )

    profile_text = _required_text(raw, "profile_directory")
    profile_candidate = Path(profile_text).expanduser()
    if not profile_candidate.is_absolute():
        raise ConfigError("profile_directory must be an absolute path")
    profile_directory = profile_candidate.resolve()
    resolved_repository = repository_root.resolve()
    if (
        profile_directory == resolved_repository
        or resolved_repository in profile_directory.parents
    ):
        raise ConfigError("profile_directory must be outside the repository")

    if allowed_profile_root is None:
        local_app_data = os.environ.get("LOCALAPPDATA")
        if not local_app_data:
            raise ConfigError("local application-data directory is unavailable")
        allowed_profile_root = Path(local_app_data)
    resolved_profile_root = allowed_profile_root.expanduser().resolve()
    if (
        profile_directory == resolved_profile_root
        or resolved_profile_root not in profile_directory.parents
    ):
        raise ConfigError(
            "profile_directory must be beneath the local application-data directory"
        )

    host_and_port = hostname if port is None else f"{hostname}:{port}"
    return ProbeConfig(
        landing_url=landing_url,
        expected_origin=f"https://{host_and_port}",
        profile_directory=profile_directory,
    )


def load_config(
    path: Path,
    *,
    repository_root: Path,
    allowed_profile_root: Path | None = None,
) -> ProbeConfig:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigError("configuration file could not be read") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError("configuration file is not valid JSON") from exc

    if not isinstance(raw, dict):
        raise ConfigError("configuration must contain a JSON object")
    return validate_config(
        raw,
        repository_root=repository_root,
        allowed_profile_root=allowed_profile_root,
    )
