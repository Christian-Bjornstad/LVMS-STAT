from __future__ import annotations

import json
import os
import secrets
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, fields
from pathlib import Path

from lvms_stat.workflow import ControlIdentity


class ReportContractError(ValueError):
    """The defined-report control contract is incomplete or unsafe."""


CONTRACT_ROLES = frozenset(
    {
        "report_type",
        "category",
        "report_id",
        "analysis_codes",
        "created_from",
        "created_to",
        "export",
    }
)
CONTROL_FIELDS = frozenset({"tag", "type", "id", "name", "role", "label", "locator"})
ALLOWED_TAGS = frozenset({"A", "BUTTON", "INPUT", "SELECT", "TEXTAREA"})


CONTRACT_DISCOVERY_SCRIPT = r"""
(() => {
  const aliases = {
    report_type: ["report type", "rapporttype"],
    category: ["category", "kategori"],
    report_id: ["report id", "rapport id"],
    analysis_codes: ["analyses", "angi analyse(r)"],
    created_from: ["created from", "analyse opprettet fom:"],
    created_to: ["created to", "analyse opprettet tom:"],
    export: ["export", "eksportere"]
  };
  const clean = (text) => String(text || "").replace(/\s+/g, " ").trim().toLowerCase();
  const excluded = (el) => Boolean(el.closest(
    "[contenteditable='true'],[id*='patient' i],[class*='patient' i]," +
    "[id*='sample' i],[class*='sample' i],[id*='result' i],[class*='result' i]"
  ));
  const visible = (el) => {
    const style = el.ownerDocument.defaultView.getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style.display !== "none" && style.visibility !== "hidden" &&
      rect.width > 0 && rect.height > 0 && !el.disabled;
  };
  const locator = (el) => {
    const parts = [];
    let node = el;
    while (node && node.nodeType === 1 && parts.length < 12) {
      let part = clean(node.tagName);
      const id = String(node.getAttribute("id") || "").trim();
      const name = String(node.getAttribute("name") || "").trim();
      if (id) part += "#" + id;
      else if (name) part += "[name=" + name + "]";
      else if (node.parentElement) part += ":nth-child(" +
        (Array.from(node.parentElement.children).indexOf(node) + 1) + ")";
      parts.unshift(part.slice(0, 120));
      if (id) break;
      node = node.parentElement;
    }
    return parts;
  };
  const labelText = (el) => {
    const aria = el.getAttribute("aria-label");
    if (aria) return clean(aria);
    if (el.labels && el.labels.length) {
      return clean(Array.from(el.labels).map((item) => item.textContent).join(" "));
    }
    const row = el.closest("tr,[role='row']");
    return row ? clean(row.textContent) : "";
  };
  const identity = (el) => ({
    tag: String(el.tagName || "").slice(0, 120),
    type: String(el.getAttribute("type") || "").trim().toLowerCase().slice(0, 120),
    id: String(el.getAttribute("id") || "").trim().slice(0, 120),
    name: String(el.getAttribute("name") || "").trim().slice(0, 120),
    role: String(el.getAttribute("role") || "").trim().slice(0, 120),
    label: labelText(el).slice(0, 120),
    locator: locator(el)
  });
  const controls = Array.from(document.querySelectorAll(
    "input,select,textarea,button,a,[role='button']"
  )).filter((el) => {
    const type = clean(el.getAttribute("type"));
    return !excluded(el) && visible(el) && type !== "password" && type !== "hidden";
  });
  const output = {};
  for (const [role, names] of Object.entries(aliases)) {
    const candidates = controls.filter((el) => {
      const text = role === "export" ? clean(el.textContent || el.getAttribute("aria-label")) : labelText(el);
      return names.some((name) => text === name || text.startsWith(name + " "));
    });
    output[role] = candidates.length === 1 ? identity(candidates[0]) : null;
  }
  return output;
})()
""".strip()


@dataclass(frozen=True)
class ReportContract:
    report_type: ControlIdentity
    category: ControlIdentity
    report_id: ControlIdentity
    analysis_codes: ControlIdentity
    created_from: ControlIdentity
    created_to: ControlIdentity
    export: ControlIdentity


def _text(value: object) -> str:
    if not isinstance(value, str) or len(value.strip()) > 120:
        raise ReportContractError("report control text is invalid")
    return value.strip()


def _control(raw: object) -> ControlIdentity:
    if not isinstance(raw, Mapping) or set(raw) != CONTROL_FIELDS:
        raise ReportContractError("report control fields are invalid")
    tag = _text(raw["tag"]).upper()
    control_type = _text(raw["type"]).lower()
    locator = raw["locator"]
    if (
        tag not in ALLOWED_TAGS
        or control_type in {"password", "hidden"}
        or not isinstance(locator, list)
        or not 1 <= len(locator) <= 12
    ):
        raise ReportContractError("report control identity is invalid")
    safe_locator = tuple(_text(part) for part in locator)
    if any(not part for part in safe_locator):
        raise ReportContractError("report control locator is invalid")
    return ControlIdentity(
        tag=tag,
        control_type=control_type,
        element_id=_text(raw["id"]),
        name=_text(raw["name"]),
        role=_text(raw["role"]),
        label=_text(raw["label"]),
        locator=safe_locator,
    )


def sanitize_report_contract(raw: object) -> ReportContract:
    if not isinstance(raw, Mapping) or set(raw) != CONTRACT_ROLES:
        raise ReportContractError("report contract roles are invalid")
    controls = {role: _control(raw[role]) for role in CONTRACT_ROLES}
    identities = [
        (item.tag, item.element_id, item.name, item.locator)
        for item in controls.values()
    ]
    if len(set(identities)) != len(identities):
        raise ReportContractError("report controls are not unique")
    return ReportContract(**controls)


def discover_report_contract(page: object, expected_origin: str) -> ReportContract:
    if page.current_origin() != expected_origin:  # type: ignore[attr-defined]
        raise ReportContractError("report contract origin is invalid")
    raw = page.evaluate_safe(CONTRACT_DISCOVERY_SCRIPT, timeout_seconds=10)  # type: ignore[attr-defined]
    return sanitize_report_contract(raw)


def _encode(contract: ReportContract) -> dict[str, object]:
    roles: dict[str, object] = {}
    for item in fields(contract):
        control = getattr(contract, item.name)
        roles[item.name] = {
            "tag": control.tag,
            "control_type": control.control_type,
            "element_id": control.element_id,
            "name": control.name,
            "role": control.role,
            "label": control.label,
            "locator": list(control.locator),
        }
    return {"schema_version": 1, "roles": roles}


def _decode(raw: object) -> ReportContract:
    if not isinstance(raw, dict) or set(raw) != {"schema_version", "roles"}:
        raise ReportContractError("report contract file is invalid")
    if raw["schema_version"] != 1 or not isinstance(raw["roles"], dict):
        raise ReportContractError("report contract version is invalid")
    converted: dict[str, object] = {}
    stored_fields = {
        "tag", "control_type", "element_id", "name", "role", "label", "locator"
    }
    for role, control in raw["roles"].items():
        if not isinstance(control, dict) or set(control) != stored_fields:
            raise ReportContractError("report contract control is invalid")
        converted[role] = {
            "tag": control.get("tag"),
            "type": control.get("control_type"),
            "id": control.get("element_id"),
            "name": control.get("name"),
            "role": control.get("role"),
            "label": control.get("label"),
            "locator": control.get("locator"),
        }
    return sanitize_report_contract(converted)


def save_contract(contract: ReportContract, directory: Path) -> Path:
    if not directory.is_absolute():
        raise ReportContractError("contract directory must be absolute")
    root = directory.resolve()
    root.mkdir(parents=True, exist_ok=True)
    destination = root / f"{secrets.token_hex(16)}.json"
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", delete=False, dir=root, suffix=".tmp"
        ) as stream:
            temporary = Path(stream.name)
            json.dump(_encode(contract), stream, ensure_ascii=False, separators=(",", ":"))
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(destination)
        return destination
    except OSError as exc:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise ReportContractError("report contract could not be saved") from exc


def load_contract(path: Path, directory: Path) -> ReportContract:
    if not directory.is_absolute():
        raise ReportContractError("contract directory must be absolute")
    root = directory.resolve()
    resolved = path.resolve()
    if root not in resolved.parents:
        raise ReportContractError("contract file is outside its directory")
    try:
        return _decode(json.loads(resolved.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReportContractError("report contract could not be read") from exc
