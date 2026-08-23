from __future__ import annotations

from unittest.mock import patch

from lvms_stat.portal import main


def test_portal_entry_point_launches_app_without_cli_arguments() -> None:
    with patch("lvms_stat.portal.cli_main", return_value=7) as cli_main:
        assert main() == 7

    cli_main.assert_called_once_with(["app"])
