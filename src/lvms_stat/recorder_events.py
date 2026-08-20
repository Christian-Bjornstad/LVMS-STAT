from __future__ import annotations

from collections.abc import Mapping

from lvms_stat.workflow import ControlIdentity, StepKind, WorkflowStep


class RecorderEventError(ValueError):
    """A browser action batch crossed the recorder safety boundary."""


EVENT_FIELDS = frozenset({"nonce", "kind", "control"})
CONTROL_FIELDS = frozenset({"tag", "type", "id", "name", "role", "label", "locator"})
FORBIDDEN_FIELDS = frozenset(
    {
        "value", "href", "src", "url", "cookie", "token", "authorization",
        "textcontent", "innertext", "filename", "path",
    }
)
ALLOWED_TAGS = frozenset({"A", "BUTTON", "INPUT", "SELECT", "TEXTAREA"})
ALLOWED_KINDS = {str(kind): kind for kind in StepKind}


RECORDER_INSTALL_SCRIPT_TEMPLATE = r"""
(() => {
  const nonce = __NONCE_JSON__;
  const root = window;
  const existing = root.__lvmsStatSafeRecorder;
  if (existing && existing.nonce === nonce) return existing.marker;
  const state = {nonce, marker: Math.random().toString(36).slice(2), queue: []};
  root.__lvmsStatSafeRecorder = state;
  const clean = (text) => String(text || "").replace(/\s+/g, " ").trim().slice(0, 120);
  const excluded = (el) => Boolean(el.closest(
    "table,[role='grid'],[role='treegrid'],[contenteditable='true']," +
    "[id*='patient' i],[class*='patient' i],[id*='sample' i],[class*='sample' i]," +
    "[id*='result' i],[class*='result' i]"
  ));
  const visible = (el) => {
    const style = el.ownerDocument.defaultView.getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
  };
  const label = (el) => {
    const aria = el.getAttribute("aria-label");
    if (aria) return clean(aria);
    if (el.labels && el.labels.length) {
      return clean(Array.from(el.labels).map((item) => item.textContent).join(" "));
    }
    if (el.tagName === "BUTTON" || el.tagName === "A") return clean(el.textContent);
    return "";
  };
  const locator = (el) => {
    const parts = [];
    let node = el;
    while (node && node.nodeType === 1 && parts.length < 12) {
      let part = clean(node.tagName).toLowerCase();
      const id = clean(node.getAttribute("id"));
      const name = clean(node.getAttribute("name"));
      if (id) part += "#" + id;
      else if (name) part += "[name=" + name + "]";
      else if (node.parentElement) part += ":nth-child(" + (Array.from(node.parentElement.children).indexOf(node) + 1) + ")";
      parts.unshift(part);
      if (id) break;
      node = node.parentElement;
    }
    return parts;
  };
  const candidate = (kind, el) => {
    if (!el || excluded(el) || !visible(el)) return;
    const type = clean(el.getAttribute("type")).toLowerCase();
    if (type === "password" || type === "hidden") return;
    if (!['A','BUTTON','INPUT','SELECT','TEXTAREA'].includes(el.tagName)) return;
    if (state.queue.length >= 100) return;
    state.queue.push({nonce, kind, control: {
      tag: clean(el.tagName), type, id: clean(el.getAttribute("id")),
      name: clean(el.getAttribute("name")), role: clean(el.getAttribute("role")),
      label: label(el), locator: locator(el)
    }});
  };
  const install = (doc) => {
    doc.addEventListener("click", (event) => {
      const el = event.target && event.target.closest("a,button,input,[role='button'],[role='menuitem']");
      if (el) candidate("activate", el);
    }, true);
    doc.addEventListener("change", (event) => {
      const el = event.target;
      if (el && el.tagName === "SELECT") candidate("select", el);
      else if (el && el.tagName === "INPUT" && ["checkbox", "radio"].includes(clean(el.getAttribute("type")).toLowerCase())) candidate("activate", el);
    }, true);
    doc.addEventListener("blur", (event) => {
      const el = event.target;
      if (el && ["INPUT", "TEXTAREA"].includes(el.tagName)) candidate("field_edited", el);
    }, true);
    for (const frame of doc.querySelectorAll("iframe,frame")) {
      try { if (frame.contentDocument) install(frame.contentDocument); } catch (_) {}
    }
  };
  install(document);
  return state.marker;
})()
""".strip()


RECORDER_DRAIN_SCRIPT_TEMPLATE = r"""
(() => {
  const state = window.__lvmsStatSafeRecorder;
  if (!state || state.nonce !== __NONCE_JSON__) return null;
  const batch = state.queue.slice(0, 100);
  state.queue.splice(0, batch.length);
  return {marker: state.marker, events: batch};
})()
""".strip()


def _contains_forbidden(value: object) -> bool:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key).lower() in FORBIDDEN_FIELDS or _contains_forbidden(child):
                return True
    elif isinstance(value, list):
        return any(_contains_forbidden(child) for child in value)
    return False


def _text(value: object) -> str:
    if not isinstance(value, str):
        raise RecorderEventError("browser action has an invalid string")
    return value.strip()[:120]


def sanitize_event_batch(
    raw: object, *, start_step_id: int, expected_nonce: str
) -> tuple[WorkflowStep, ...]:
    if not isinstance(raw, list) or len(raw) > 100 or start_step_id < 1:
        raise RecorderEventError("browser action batch is invalid")
    steps: list[WorkflowStep] = []
    for offset, item in enumerate(raw):
        if _contains_forbidden(item) or not isinstance(item, Mapping) or set(item) != EVENT_FIELDS:
            raise RecorderEventError("browser action contains unsafe fields")
        if item["nonce"] != expected_nonce or item["kind"] not in ALLOWED_KINDS:
            raise RecorderEventError("browser action identity is invalid")
        control = item["control"]
        if not isinstance(control, Mapping) or set(control) != CONTROL_FIELDS:
            raise RecorderEventError("browser control identity is invalid")
        tag = _text(control["tag"]).upper()
        control_type = _text(control["type"]).lower()
        locator = control["locator"]
        if tag not in ALLOWED_TAGS or control_type in {"password", "hidden"}:
            raise RecorderEventError("browser control is excluded")
        if not isinstance(locator, list) or len(locator) > 12:
            raise RecorderEventError("browser control locator is invalid")
        safe_locator = tuple(_text(part) for part in locator)
        identity = ControlIdentity(
            tag=tag,
            control_type=control_type,
            element_id=_text(control["id"]),
            name=_text(control["name"]),
            role=_text(control["role"]),
            label=_text(control["label"]),
            locator=safe_locator,
        )
        steps.append(
            WorkflowStep(
                step_id=start_step_id + offset,
                kind=ALLOWED_KINDS[str(item["kind"])],
                control=identity,
            )
        )
    return tuple(steps)
