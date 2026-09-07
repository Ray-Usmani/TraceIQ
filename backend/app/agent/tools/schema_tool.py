"""Load and format the business semantic layer for LLM prompts."""

from __future__ import annotations

from collections.abc import Collection
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.config import get_settings

# Tables whose first listed field is treated as the primary key in prompts.
_PRIMARY_KEYS = {
    "website_sessions": "website_session_id",
    "website_pageviews": "website_pageview_id",
    "products": "product_id",
    "orders": "order_id",
    "order_items": "order_item_id",
    "order_item_refunds": "order_item_refund_id",
}


def resolve_config_dir() -> Path:
    """Return the directory containing data_dictionary.yaml and metrics.yaml."""
    settings = get_settings()
    candidates = [
        Path(settings.config_dir),
        Path("/config"),
        Path(__file__).resolve().parents[4] / "config",  # repo root /config
        Path(__file__).resolve().parents[3] / "config",
    ]
    for path in candidates:
        if (path / "data_dictionary.yaml").exists():
            return path
    return candidates[0]


@lru_cache
def _load_yaml(filename: str) -> dict[str, Any]:
    path = resolve_config_dir() / filename
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise TypeError(f"{filename} must contain a mapping at the top level")
    return data


def load_data_dictionary() -> dict[str, Any]:
    return _load_yaml("data_dictionary.yaml")


def load_metrics() -> dict[str, Any]:
    return _load_yaml("metrics.yaml")


def available_table_names() -> list[str]:
    """Return semantic-layer table names in their configured order."""
    return [
        name
        for name, info in load_data_dictionary().items()
        if name != "joins"
        and isinstance(info, dict)
        and ("purpose" in info or "grain" in info)
    ]


def available_metric_names() -> list[str]:
    """Return configured business metric names in their configured order."""
    return [name for name, info in load_metrics().items() if isinstance(info, dict)]


def load_schema_context(table_names: Collection[str] | None = None) -> str:
    """Format the data dictionary as LLM-readable plain text."""
    data = load_data_dictionary()
    selected = set(table_names) if table_names is not None else None
    lines: list[str] = ["## Tables", ""]

    joins = data.get("joins", [])
    for table_name, table_info in data.items():
        if table_name == "joins" or not isinstance(table_info, dict):
            continue
        if selected is not None and table_name not in selected:
            continue
        if "purpose" not in table_info and "grain" not in table_info:
            continue

        lines.append(f"### analytics.{table_name}")
        if purpose := table_info.get("purpose"):
            lines.append(f"Purpose: {purpose}")
        if grain := table_info.get("grain"):
            lines.append(f"Grain: {grain}")

        fields = table_info.get("important_fields") or {}
        if fields:
            lines.append("Columns:")
            pk = _PRIMARY_KEYS.get(table_name)
            for field_name, field_info in fields.items():
                desc = ""
                if isinstance(field_info, dict):
                    desc = field_info.get("description", "")
                elif isinstance(field_info, str):
                    desc = field_info
                pk_marker = " (PK)" if field_name == pk else ""
                lines.append(f"  - {field_name}: {desc}{pk_marker}")
        lines.append("")

    if joins:
        lines.append("## Joins")
        for join in joins:
            if not isinstance(join, dict):
                continue
            frm = join.get("from", "")
            to = join.get("to", "")
            if selected is not None:
                from_table = str(frm).split(".", maxsplit=1)[0]
                to_table = str(to).split(".", maxsplit=1)[0]
                if from_table not in selected or to_table not in selected:
                    continue
            jtype = join.get("type", "")
            note = join.get("note", "")
            line = f"  {frm} -> {to} ({jtype})"
            if note:
                line += f" — {note}"
            lines.append(line)
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def load_metrics_context(metric_names: Collection[str] | None = None) -> str:
    """Format the metrics dictionary as LLM-readable plain text."""
    data = load_metrics()
    selected = set(metric_names) if metric_names is not None else None
    lines: list[str] = ["## Business Metrics", ""]

    for name, info in data.items():
        if not isinstance(info, dict):
            continue
        if selected is not None and name not in selected:
            continue
        definition = info.get("definition", "")
        note = info.get("note", "")
        table = info.get("table", "")
        line = f"  {name}: {definition}"
        extras: list[str] = []
        if table:
            extras.append(f"table={table}")
        if note:
            extras.append(note)
        if extras:
            line += f" ({'; '.join(extras)})"
        lines.append(line)

    return "\n".join(lines).strip() + "\n"
