from __future__ import annotations

import json
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO

from lvms_stat.cdp import (
    BrowserPage,
    CdpConnection,
    CdpProtocolError,
    CdpTimeout,
    PageTarget,
    UnexpectedOriginError,
    discover_page,
)
from lvms_stat.config import ConfigError, load_config
from lvms_stat.edge import EdgeLaunchError, EdgeProcess


@dataclass(frozen=True)
class ProbeDependencies:
    edge_start: Callable[[Path], Any]
    target_wait: Callable[[int], PageTarget]
    connection_open: Callable[[PageTarget], Any]
    page_factory: Callable[[Any], Any]


def _wait_for_target(
    port: int,
    *,
    timeout_seconds: float = 20,
    discover: Callable[[int], PageTarget] = discover_page,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> PageTarget:
    deadline = clock() + timeout_seconds
    while clock() < deadline:
        try:
            return discover(port)
        except CdpTimeout:
            sleep(0.2)
    raise CdpTimeout("Edge connection timed out")


def _default_dependencies() -> ProbeDependencies:
    return ProbeDependencies(
        edge_start=EdgeProcess.start,
        target_wait=_wait_for_target,
        connection_open=CdpConnection.open,
        page_factory=BrowserPage,
    )


def run_probe(
    config_path: Path,
    *,
    inspect: bool = False,
    dependencies: ProbeDependencies | None = None,
    output: TextIO | None = None,
    input_func: Callable[[str], str] = input,
    repository_root: Path | None = None,
    allowed_profile_root: Path | None = None,
) -> int:
    active_dependencies = dependencies or _default_dependencies()
    active_output = output or sys.stdout
    active_repository = repository_root or Path(__file__).resolve().parents[2]
    edge: Any | None = None
    connection: Any | None = None
    exit_code = 2

    try:
        config = load_config(
            config_path,
            repository_root=active_repository,
            allowed_profile_root=allowed_profile_root,
        )
        edge = active_dependencies.edge_start(config.profile_directory)
        target = active_dependencies.target_wait(edge.port)
        connection = active_dependencies.connection_open(target)
        page = active_dependencies.page_factory(connection)
        identity = page.navigate(config.landing_url, config.expected_origin)

        suffix = f" — {identity.title}" if identity.title else ""
        active_output.write(f"Connected: {identity.origin}{suffix}\n")
        exit_code = 0

        if inspect:
            active_output.write(
                "Navigate Edge to a page without patient or sample tables. "
                "Inspection reads fixed controls only.\n"
            )
            confirmation = input_func("Type INSPECT to continue: ")
            if confirmation != "INSPECT":
                active_output.write("Inspection cancelled.\n")
                exit_code = 130
            else:
                controls = page.inspect_controls(config.expected_origin)
                if not controls:
                    active_output.write("No safe controls found.\n")
                for control in controls:
                    active_output.write(
                        json.dumps(control, ensure_ascii=False, sort_keys=True) + "\n"
                    )
    except ConfigError:
        active_output.write("Probe failed: configuration is invalid.\n")
    except EdgeLaunchError:
        active_output.write("Probe failed: managed Edge is unavailable.\n")
    except CdpTimeout:
        active_output.write("Probe failed: Edge connection timed out.\n")
    except UnexpectedOriginError:
        active_output.write("Probe failed: Edge reached an unexpected origin.\n")
    except CdpProtocolError:
        active_output.write("Probe failed: Edge returned an invalid response.\n")
    except KeyboardInterrupt:
        active_output.write("Probe cancelled.\n")
        exit_code = 130
    finally:
        cleanup_failed = False
        if connection is not None:
            try:
                connection.close()
            except Exception:
                cleanup_failed = True
        if edge is not None:
            try:
                edge.close()
            except Exception:
                cleanup_failed = True
        if cleanup_failed:
            active_output.write("Probe failed: browser cleanup did not complete.\n")
            exit_code = 2

    return exit_code
