from __future__ import annotations

from collections.abc import Mapping


class InspectionError(ValueError):
    """Browser control metadata is malformed or unsafe to display."""


SAFE_CONTROL_FIELDS = (
    "tag",
    "id",
    "name",
    "type",
    "role",
    "label",
    "text",
    "frame",
)

FORBIDDEN_CONTROL_FIELDS = frozenset(
    {"value", "href", "src", "cookie", "token", "authorization"}
)


CONTROL_INSPECTION_SCRIPT = r"""
(() => {
  const selector = [
    "button",
    "a",
    "input",
    "select",
    "textarea",
    "[role='button']",
    "[role='menuitem']",
    "[role='tab']"
  ].join(",");

  const visible = (element) => {
    const style = element.ownerDocument.defaultView.getComputedStyle(element);
    const rectangle = element.getBoundingClientRect();
    return style.display !== "none" &&
      style.visibility !== "hidden" &&
      rectangle.width > 0 &&
      rectangle.height > 0;
  };

  const cleanText = (text) => String(text || "").replace(/\s+/g, " ").trim();

  const labelFor = (element) => {
    const ariaLabel = element.getAttribute("aria-label");
    if (ariaLabel) return cleanText(ariaLabel);
    if (element.labels && element.labels.length) {
      return cleanText(Array.from(element.labels).map((label) => label.textContent).join(" "));
    }
    return "";
  };

  const frameName = (frameElement, fallback) => {
    if (!frameElement) return fallback;
    return cleanText(
      frameElement.getAttribute("id") ||
      frameElement.getAttribute("name") ||
      frameElement.getAttribute("title") ||
      fallback
    );
  };

  const inspectDocument = (doc, frame, output) => {
    for (const element of doc.querySelectorAll(selector)) {
      const type = cleanText(element.getAttribute("type")).toLowerCase();
      if (type === "password" || type === "hidden") continue;
      if (element.closest("table, [role='grid']")) continue;
      if (!visible(element)) continue;
      output.push({
        tag: cleanText(element.tagName),
        id: cleanText(element.getAttribute("id")),
        name: cleanText(element.getAttribute("name")),
        type,
        role: cleanText(element.getAttribute("role")),
        label: labelFor(element),
        text: cleanText(element.innerText),
        frame
      });
      if (output.length >= 200) return;
    }

    for (const childFrame of doc.querySelectorAll("iframe, frame")) {
      if (output.length >= 200) return;
      try {
        if (childFrame.contentDocument) {
          inspectDocument(
            childFrame.contentDocument,
            frameName(childFrame, "child-frame"),
            output
          );
        }
      } catch (_) {
        // Cross-origin frames are intentionally inaccessible and skipped.
      }
    }
  };

  const controls = [];
  inspectDocument(document, "top", controls);
  return controls;
})()
""".strip()


def sanitize_controls(
    raw: object,
    *,
    max_controls: int = 200,
    max_text_length: int = 120,
) -> list[dict[str, str]]:
    if not isinstance(max_controls, int) or max_controls <= 0:
        raise InspectionError("max_controls must be a positive integer")
    if not isinstance(max_text_length, int) or max_text_length <= 0:
        raise InspectionError("max_text_length must be a positive integer")
    if not isinstance(raw, list):
        raise InspectionError("inspector result must be a list")

    safe_controls: list[dict[str, str]] = []
    for item in raw[:max_controls]:
        if not isinstance(item, Mapping):
            continue

        item_fields = {str(field).lower() for field in item}
        if item_fields & FORBIDDEN_CONTROL_FIELDS:
            raise InspectionError("inspector result contains a forbidden field")

        control_type = item.get("type")
        if isinstance(control_type, str) and control_type.strip().lower() in {
            "password",
            "hidden",
        }:
            continue

        safe_control: dict[str, str] = {}
        for field in SAFE_CONTROL_FIELDS:
            value = item.get(field)
            if isinstance(value, str) and value.strip():
                safe_control[field] = value.strip()[:max_text_length]
        if safe_control:
            safe_controls.append(safe_control)

    return safe_controls
