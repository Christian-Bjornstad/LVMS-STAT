from __future__ import annotations

from typing import Any

from lvms_stat.config import AppConfig


def close_owned(connection: Any | None, edge: Any | None) -> bool:
    failed = False
    for resource in (connection, edge):
        if resource is None:
            continue
        try:
            resource.close()
        except Exception:
            failed = True
    return failed


def open_page(config: AppConfig, dependencies: Any) -> tuple[Any, Any, Any]:
    opened = dependencies.browser_open(config.profile_directory)
    connection: Any | None = None
    try:
        connection = dependencies.connection_open(opened.target)
        page = dependencies.page_factory(connection)
        page.navigate(config.landing_url, config.expected_origin, timeout_seconds=120)
        return opened.edge, connection, page
    except Exception:
        close_owned(connection, opened.edge)
        raise
