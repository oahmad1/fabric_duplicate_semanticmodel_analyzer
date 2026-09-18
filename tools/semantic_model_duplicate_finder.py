#!/usr/bin/env python3
"""Export and compare Power BI semantic model metadata for duplicate detection."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import html as html_lib
import itertools
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


PBI_API = "https://api.powerbi.com/v1.0/myorg"
PBI_RESOURCE = "https://analysis.windows.net/powerbi/api"

DAX_METADATA_QUERIES = {
    "tables": """
EVALUATE
SELECTCOLUMNS(
    INFO.VIEW.TABLES(),
    "Name", [Name],
    "IsHidden", [IsHidden]
)
ORDER BY [Name]
""".strip(),
    "columns": """
EVALUATE
SELECTCOLUMNS(
    INFO.VIEW.COLUMNS(),
    "Table", [Table],
    "Name", [Name],
    "DataType", [DataType],
    "IsHidden", [IsHidden]
)
ORDER BY [Table], [Name]
""".strip(),
    "measures": """
EVALUATE
SELECTCOLUMNS(
    INFO.VIEW.MEASURES(),
    "Table", [Table],
    "Name", [Name],
    "Expression", [Expression],
    "FormatString", [FormatString],
    "IsHidden", [IsHidden]
)
ORDER BY [Table], [Name]
""".strip(),
    "relationships": """
EVALUATE
SELECTCOLUMNS(
    INFO.VIEW.RELATIONSHIPS(),
    "FromTable", [FromTable],
    "FromColumn", [FromColumn],
    "ToTable", [ToTable],
    "ToColumn", [ToColumn],
    "Cardinality", [Cardinality],
    "CrossFilteringBehavior", [CrossFilteringBehavior],
    "IsActive", [IsActive]
)
""".strip(),
}

DIMENSIONS = (
    ("tables", 0.20),
    ("columns", 0.25),
    ("measure_names", 0.10),
    ("measure_expressions", 0.15),
    ("relationships", 0.15),
    ("data_sources", 0.15),
)

SENSITIVE_KEY_RE = re.compile(r"(password|secret|token|credential|key|sas|connectionstring)", re.I)


class ApiError(RuntimeError):
    def __init__(self, method: str, url: str, status: int | None, body: str):
        self.method = method
        self.url = url
        self.status = status
        self.body = body.strip()
        message = f"{method} {url} failed"
        if status is not None:
            message += f" with HTTP {status}"
        if self.body:
            message += f": {self.body[:500]}"
        super().__init__(message)

    def brief(self) -> str:
        if self.status is None:
            return self.body or str(self)
        if self.body:
            return f"HTTP {self.status}: {self.body[:300]}"
        return f"HTTP {self.status}"


@dataclass(frozen=True)
class ModelSignature:
    workspace_id: str
    workspace_name: str
    model_id: str
    model_name: str
    tables: frozenset[str]
    columns: frozenset[str]
    measure_names: frozenset[str]
    measure_expressions: frozenset[str]
    relationships: frozenset[str]
    data_sources: frozenset[str]
    warnings: tuple[str, ...]

    def object_count(self) -> int:
        return (
            len(self.tables)
            + len(self.columns)
            + len(self.measure_names)
            + len(self.measure_expressions)
            + len(self.relationships)
        )


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clean_key(key: Any) -> str:
    text = str(key).strip()
    if text.startswith("[") and text.endswith("]"):
        return text[1:-1]
    return text


def normalize_text(value: Any) -> str:
    text = "" if value is None else str(value)
    return re.sub(r"\s+", " ", text.strip()).casefold()


def normalize_identifier(value: Any) -> str:
    text = normalize_text(value)
    text = text.strip("'\"[]")
    return re.sub(r"\s+", " ", text)


def normalize_dax(expression: Any) -> str:
    text = "" if expression is None else str(expression)
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    text = re.sub(r"//.*?$", " ", text, flags=re.M)
    text = re.sub(r"\s+", " ", text.strip()).casefold()
    text = re.sub(r"\s*([,=+\-*/(){}\[\]:<>])\s*", r"\1", text)
    return text


def get_value(row: Any, *names: str) -> Any:
    if isinstance(row, str):
        return row
    if not isinstance(row, Mapping):
        return None
    indexed = {clean_key(key).casefold(): value for key, value in row.items()}
    for name in names:
        value = indexed.get(clean_key(name).casefold())
        if value not in (None, ""):
            return value
    return None


def list_value(model: Mapping[str, Any], *names: str) -> list[Any]:
    indexed = {clean_key(key).casefold(): value for key, value in model.items()}
    for name in names:
        value = indexed.get(clean_key(name).casefold())
        if value is None:
            continue
        if isinstance(value, list):
            return value
        return [value]
    return []


def table_signature(row: Any) -> str | None:
    name = get_value(row, "Name", "Table", "TableName", "tableName")
    normalized = normalize_identifier(name)
    return normalized or None


def column_signature(row: Any) -> str | None:
    if isinstance(row, str):
        return normalize_identifier(row) or None
    table = normalize_identifier(get_value(row, "Table", "TableName", "tableName"))
    name = normalize_identifier(get_value(row, "Name", "Column", "ColumnName", "columnName"))
    data_type = normalize_identifier(get_value(row, "DataType", "Type", "dataType"))
    if not name:
        return None
    return f"{table}[{name}]|{data_type}" if table else f"{name}|{data_type}"


def measure_name_signature(row: Any) -> str | None:
    if isinstance(row, str):
        return normalize_identifier(row) or None
    table = normalize_identifier(get_value(row, "Table", "TableName", "tableName"))
    name = normalize_identifier(get_value(row, "Name", "Measure", "MeasureName", "measureName"))
    if not name:
        return None
    return f"{table}[{name}]" if table else name


def measure_expression_signature(row: Any) -> str | None:
    expression = normalize_dax(get_value(row, "Expression", "Dax", "DAX", "formula"))
    return expression or None


def relationship_signature(row: Any) -> str | None:
    if isinstance(row, str):
        return normalize_identifier(row) or None
    left_table = normalize_identifier(get_value(row, "FromTable", "From Table", "fromTable"))
    left_column = normalize_identifier(get_value(row, "FromColumn", "From Column", "fromColumn"))
    right_table = normalize_identifier(get_value(row, "ToTable", "To Table", "toTable"))
    right_column = normalize_identifier(get_value(row, "ToColumn", "To Column", "toColumn"))
    if not (left_table and left_column and right_table and right_column):
        return None
    left = f"{left_table}[{left_column}]"
    right = f"{right_table}[{right_column}]"
    endpoints = sorted((left, right))
    cardinality = normalize_identifier(get_value(row, "Cardinality", "RelationshipCardinality"))
    active = normalize_identifier(get_value(row, "IsActive", "Active"))
    return f"{endpoints[0]}--{endpoints[1]}|{cardinality}|{active}"


def data_source_signature(row: Any) -> str | None:
    if isinstance(row, str):
        return normalize_text(row) or None
    if not isinstance(row, Mapping):
        return None

    parts: list[str] = []
    for key in ("datasourceType", "type", "kind"):
        value = get_value(row, key)
        if value:
            parts.append(f"{key}={normalize_text(value)}")

    details = get_value(row, "connectionDetails", "ConnectionDetails")
    if isinstance(details, str):
        try:
            details = json.loads(details)
        except json.JSONDecodeError:
            details = {}

    if isinstance(details, Mapping):
        for key in ("server", "database", "url", "path", "account", "domain", "workspaceId", "lakehouseId"):
            value = get_value(details, key)
            if value:
                parts.append(f"{key}={normalize_text(value)}")

    for key in ("server", "database", "url", "path"):
        if SENSITIVE_KEY_RE.search(key):
            continue
        value = get_value(row, key)
        if value:
            parts.append(f"{key}={normalize_text(value)}")

    return "|".join(sorted(set(parts))) or None


def signatures(rows: Iterable[Any], converter) -> frozenset[str]:
    values = {converted for row in rows if (converted := converter(row))}
    return frozenset(values)


def model_warnings(model: Mapping[str, Any], global_warnings: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    model_id = normalize_text(get_value(model, "id", "modelId", "datasetId"))
    local = [str(warning) for warning in list_value(model, "warnings")]
    matched = []
    for warning in global_warnings:
        warning_model_id = normalize_text(get_value(warning, "modelId", "datasetId", "id"))
        if warning_model_id and warning_model_id == model_id:
            stage = get_value(warning, "stage") or "metadata"
            message = get_value(warning, "message") or warning
            matched.append(f"{stage}: {message}")
    return tuple(local + matched)


def build_signature(model: Mapping[str, Any], global_warnings: Sequence[Mapping[str, Any]] = ()) -> ModelSignature:
    model_id = str(get_value(model, "id", "modelId", "datasetId", "artifactId") or "")
    model_name = str(get_value(model, "name", "displayName", "datasetName") or model_id)
    workspace_id = str(get_value(model, "workspaceId", "groupId") or "")
    workspace_name = str(get_value(model, "workspaceName", "groupName") or workspace_id)

    measures = list_value(model, "measures", "Measures")
    return ModelSignature(
        workspace_id=workspace_id,
        workspace_name=workspace_name,
        model_id=model_id,
        model_name=model_name,
        tables=signatures(list_value(model, "tables", "Tables"), table_signature),
        columns=signatures(list_value(model, "columns", "Columns"), column_signature),
        measure_names=signatures(measures, measure_name_signature),
        measure_expressions=signatures(measures, measure_expression_signature),
        relationships=signatures(list_value(model, "relationships", "Relationships"), relationship_signature),
        data_sources=signatures(list_value(model, "dataSources", "datasources", "DataSources"), data_source_signature),
        warnings=model_warnings(model, global_warnings),
    )


def jaccard(left: frozenset[str], right: frozenset[str]) -> float | None:
    if not left and not right:
        return None
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def containment(left: frozenset[str], right: frozenset[str]) -> float | None:
    if not left and not right:
        return None
    if not left or not right:
        return 0.0
    return len(left & right) / min(len(left), len(right))


def weighted_score(dimensions: Mapping[str, Mapping[str, float | int | None]], metric: str) -> float:
    numerator = 0.0
    denominator = 0.0
    for name, weight in DIMENSIONS:
        value = dimensions[name][metric]
        if value is None:
            continue
        numerator += weight * float(value)
        denominator += weight
    return numerator / denominator if denominator else 0.0


def round_score(value: float | None) -> float | None:
    return None if value is None else round(value, 4)


def limit_values(values: Iterable[str], limit: int) -> tuple[list[str], int]:
    sorted_values = sorted(values)
    if limit <= 0:
        return sorted_values, 0
    return sorted_values[:limit], max(0, len(sorted_values) - limit)


def display_column(value: str) -> str:
    column, separator, data_type = value.partition("|")
    if separator and data_type:
        return f"{column} ({data_type})"
    return column


def limited_common(values: Iterable[str], limit: int, formatter=str) -> dict[str, Any]:
    limited, omitted = limit_values(values, limit)
    return {
        "items": [formatter(value) for value in limited],
        "omitted": omitted,
    }


def common_objects(left: ModelSignature, right: ModelSignature, limit: int) -> dict[str, dict[str, Any]]:
    return {
        "tables": limited_common(left.tables & right.tables, limit),
        "columns": limited_common(left.columns & right.columns, limit, display_column),
        "measures": limited_common(left.measure_names & right.measure_names, limit),
        "measureExpressions": limited_common(left.measure_expressions & right.measure_expressions, limit),
        "relationships": limited_common(left.relationships & right.relationships, limit),
        "dataSources": limited_common(left.data_sources & right.data_sources, limit),
    }


def shared_samples(left: ModelSignature, right: ModelSignature, limit: int = 25) -> dict[str, list[str]]:
    common = common_objects(left, right, limit)
    return {
        "tables": common["tables"]["items"],
        "columns": common["columns"]["items"],
        "measureNames": common["measures"]["items"],
        "measureExpressions": common["measureExpressions"]["items"],
        "relationships": common["relationships"]["items"],
        "dataSources": common["dataSources"]["items"],
    }


def confidence(left: ModelSignature, right: ModelSignature, dimensions: Mapping[str, Mapping[str, float | int | None]]) -> str:
    known_dimensions = sum(1 for name, _ in DIMENSIONS if dimensions[name]["jaccard"] is not None)
    minimum_objects = min(left.object_count(), right.object_count())
    has_warnings = bool(left.warnings or right.warnings)
    if known_dimensions >= 5 and minimum_objects >= 10 and not has_warnings:
        return "high"
    if known_dimensions >= 3 and minimum_objects >= 5:
        return "medium"
    return "low"


def model_ref(model: ModelSignature) -> dict[str, str]:
    return {
        "workspaceName": model.workspace_name,
        "workspaceId": model.workspace_id,
        "modelName": model.model_name,
        "modelId": model.model_id,
    }


def compare_pair(
    left: ModelSignature,
    right: ModelSignature,
    duplicate_threshold: float,
    overlap_threshold: float,
    common_limit: int = 25,
) -> dict[str, Any]:
    dimension_sets = {
        "tables": (left.tables, right.tables),
        "columns": (left.columns, right.columns),
        "measure_names": (left.measure_names, right.measure_names),
        "measure_expressions": (left.measure_expressions, right.measure_expressions),
        "relationships": (left.relationships, right.relationships),
        "data_sources": (left.data_sources, right.data_sources),
    }
    dimensions: dict[str, dict[str, float | int | None]] = {}
    for name, (left_set, right_set) in dimension_sets.items():
        dimensions[name] = {
            "jaccard": round_score(jaccard(left_set, right_set)),
            "containment": round_score(containment(left_set, right_set)),
            "shared": len(left_set & right_set),
            "left": len(left_set),
            "right": len(right_set),
        }

    duplicate_score = weighted_score(dimensions, "jaccard")
    containment_score = weighted_score(dimensions, "containment")
    overlap_score = max(duplicate_score, containment_score * 0.95)

    if duplicate_score >= duplicate_threshold:
        classification = "likely_duplicate"
    elif duplicate_score >= overlap_threshold or overlap_score >= overlap_threshold:
        classification = "high_overlap"
    else:
        classification = "partial_overlap"

    common = common_objects(left, right, common_limit)
    return {
        "left": model_ref(left),
        "right": model_ref(right),
        "classification": classification,
        "confidence": confidence(left, right, dimensions),
        "duplicateScore": round(duplicate_score, 4),
        "overlapScore": round(overlap_score, 4),
        "dimensions": dimensions,
        "commonObjects": common,
        "sharedSamples": {
            "tables": common["tables"]["items"],
            "columns": common["columns"]["items"],
            "measureNames": common["measures"]["items"],
            "measureExpressions": common["measureExpressions"]["items"],
            "relationships": common["relationships"]["items"],
            "dataSources": common["dataSources"]["items"],
        },
        "warnings": list(left.warnings + right.warnings),
    }


def load_inventory(path: Path) -> tuple[list[Mapping[str, Any]], list[Mapping[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload, []
    if not isinstance(payload, Mapping):
        raise ValueError("Input must be a JSON object with a 'models' array or a JSON array of models.")
    models = payload.get("models")
    if not isinstance(models, list):
        raise ValueError("Input JSON object must include a 'models' array.")
    warnings = payload.get("warnings") if isinstance(payload.get("warnings"), list) else []
    return models, warnings


def find_matches(
    models: Sequence[ModelSignature],
    min_score: float,
    duplicate_threshold: float,
    overlap_threshold: float,
    top: int,
    common_limit: int = 25,
) -> list[dict[str, Any]]:
    matches = []
    for left, right in itertools.combinations(models, 2):
        result = compare_pair(left, right, duplicate_threshold, overlap_threshold, common_limit)
        if max(result["duplicateScore"], result["overlapScore"]) >= min_score:
            matches.append(result)
    matches.sort(key=lambda item: (item["classification"] != "likely_duplicate", -item["duplicateScore"], -item["overlapScore"]))
    return matches if top <= 0 else matches[:top]


def render_csv(matches: Sequence[Mapping[str, Any]]) -> str:
    output = []
    fieldnames = [
        "classification",
        "confidence",
        "duplicateScore",
        "overlapScore",
        "leftWorkspace",
        "leftModel",
        "leftModelId",
        "rightWorkspace",
        "rightModel",
        "rightModelId",
        "sharedTables",
        "sharedColumns",
        "sharedMeasureNames",
        "sharedDataSources",
        "commonTables",
        "commonColumns",
        "commonMeasures",
        "warnings",
    ]

    class ListWriter:
        def write(self, value: str) -> None:
            output.append(value)

    writer = csv.DictWriter(ListWriter(), fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for match in matches:
        dimensions = match["dimensions"]
        common = match["commonObjects"]
        writer.writerow(
            {
                "classification": match["classification"],
                "confidence": match["confidence"],
                "duplicateScore": match["duplicateScore"],
                "overlapScore": match["overlapScore"],
                "leftWorkspace": match["left"]["workspaceName"],
                "leftModel": match["left"]["modelName"],
                "leftModelId": match["left"]["modelId"],
                "rightWorkspace": match["right"]["workspaceName"],
                "rightModel": match["right"]["modelName"],
                "rightModelId": match["right"]["modelId"],
                "sharedTables": dimensions["tables"]["shared"],
                "sharedColumns": dimensions["columns"]["shared"],
                "sharedMeasureNames": dimensions["measure_names"]["shared"],
                "sharedDataSources": dimensions["data_sources"]["shared"],
                "commonTables": format_common_for_csv(common["tables"]),
                "commonColumns": format_common_for_csv(common["columns"]),
                "commonMeasures": format_common_for_csv(common["measures"]),
                "warnings": " | ".join(match.get("warnings", [])),
            }
        )
    return "".join(output)


def md_escape(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def format_common_for_csv(common: Mapping[str, Any]) -> str:
    values = list(common.get("items", []))
    omitted = int(common.get("omitted", 0) or 0)
    if omitted:
        values.append(f"+{omitted} more")
    return "; ".join(values)


def format_common_for_markdown(common: Mapping[str, Any]) -> str:
    values = [f"`{md_escape(value)}`" for value in common.get("items", [])]
    omitted = int(common.get("omitted", 0) or 0)
    if omitted:
        values.append(f"**+{omitted} more**")
    return ", ".join(values) if values else "_None_"


def html_escape(value: Any) -> str:
    return html_lib.escape(str(value), quote=True)


def format_common_for_html(common: Mapping[str, Any]) -> str:
    values = list(common.get("items", []))
    omitted = int(common.get("omitted", 0) or 0)
    if not values and not omitted:
        return '<p class="muted">None</p>'
    items = [f"<li><code>{html_escape(value)}</code></li>" for value in values]
    if omitted:
        items.append(f'<li class="muted">+{omitted} more</li>')
    return "<ul>" + "".join(items) + "</ul>"


def match_label(match: Mapping[str, Any]) -> str:
    left = f"{match['left']['workspaceName']} / {match['left']['modelName']}"
    right = f"{match['right']['workspaceName']} / {match['right']['modelName']}"
    return f"{left} <-> {right}"


def render_markdown(matches: Sequence[Mapping[str, Any]]) -> str:
    lines = [
        "| Classification | Confidence | Duplicate | Overlap | Left model | Right model | Shared tables | Shared columns | Shared measures |",
        "|---|---|---:|---:|---|---|---:|---:|---:|",
    ]
    for match in matches:
        dimensions = match["dimensions"]
        left = f"{match['left']['workspaceName']} / {match['left']['modelName']}"
        right = f"{match['right']['workspaceName']} / {match['right']['modelName']}"
        lines.append(
            "| {classification} | {confidence} | {duplicate:.4f} | {overlap:.4f} | {left} | {right} | {tables} | {columns} | {measures} |".format(
                classification=md_escape(match["classification"]),
                confidence=md_escape(match["confidence"]),
                duplicate=match["duplicateScore"],
                overlap=match["overlapScore"],
                left=md_escape(left),
                right=md_escape(right),
                tables=dimensions["tables"]["shared"],
                columns=dimensions["columns"]["shared"],
                measures=dimensions["measure_names"]["shared"],
            )
        )
    if matches:
        lines.append("")
        lines.append("## Common objects")
        for index, match in enumerate(matches, start=1):
            common = match["commonObjects"]
            lines.extend(
                [
                    "",
                    f"### {index}. {md_escape(match_label(match))}",
                    "",
                    f"- **Tables:** {format_common_for_markdown(common['tables'])}",
                    f"- **Columns:** {format_common_for_markdown(common['columns'])}",
                    f"- **Measures:** {format_common_for_markdown(common['measures'])}",
                ]
            )
    return "\n".join(lines) + "\n"


def render_html(matches: Sequence[Mapping[str, Any]]) -> str:
    table_rows = []
    detail_sections = []
    for index, match in enumerate(matches, start=1):
        dimensions = match["dimensions"]
        label = match_label(match)
        common = match["commonObjects"]
        table_rows.append(
            "".join(
                [
                    "<tr>",
                    f"<td><span class=\"pill {html_escape(match['classification'])}\">{html_escape(match['classification'])}</span></td>",
                    f"<td>{html_escape(match['confidence'])}</td>",
                    f"<td class=\"number\">{match['duplicateScore']:.4f}</td>",
                    f"<td class=\"number\">{match['overlapScore']:.4f}</td>",
                    f"<td>{html_escape(match['left']['workspaceName'])}<br><strong>{html_escape(match['left']['modelName'])}</strong></td>",
                    f"<td>{html_escape(match['right']['workspaceName'])}<br><strong>{html_escape(match['right']['modelName'])}</strong></td>",
                    f"<td class=\"number\">{dimensions['tables']['shared']}</td>",
                    f"<td class=\"number\">{dimensions['columns']['shared']}</td>",
                    f"<td class=\"number\">{dimensions['measure_names']['shared']}</td>",
                    f"<td><a href=\"#finding-{index}\">View common objects</a></td>",
                    "</tr>",
                ]
            )
        )
        warnings = match.get("warnings", [])
        warning_html = ""
        if warnings:
            warning_items = "".join(f"<li>{html_escape(warning)}</li>" for warning in warnings)
            warning_html = f"<h4>Warnings</h4><ul>{warning_items}</ul>"
        detail_sections.append(
            "".join(
                [
                    f'<section class="card" id="finding-{index}">',
                    f"<h2>{index}. {html_escape(label)}</h2>",
                    '<div class="common-grid">',
                    "<div><h3>Common tables</h3>",
                    format_common_for_html(common["tables"]),
                    "</div>",
                    "<div><h3>Common columns</h3>",
                    format_common_for_html(common["columns"]),
                    "</div>",
                    "<div><h3>Common measures</h3>",
                    format_common_for_html(common["measures"]),
                    "</div>",
                    "</div>",
                    warning_html,
                    "</section>",
                ]
            )
        )

    rows = "\n".join(table_rows) or '<tr><td colspan="10" class="muted">No duplicate or overlap findings met the threshold.</td></tr>'
    details = "\n".join(detail_sections)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Semantic Model Duplicate Finder Report</title>
  <style>
    body {{ margin: 0; font-family: Segoe UI, Arial, sans-serif; color: #1f2937; background: #f6f8fb; }}
    header {{ padding: 28px 36px; background: #243a5e; color: #fff; }}
    main {{ padding: 28px 36px; }}
    h1 {{ margin: 0 0 8px; font-size: 28px; }}
    h2 {{ margin-top: 0; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; box-shadow: 0 1px 4px rgba(0,0,0,.08); }}
    th, td {{ padding: 10px 12px; border-bottom: 1px solid #e5e7eb; text-align: left; vertical-align: top; }}
    th {{ background: #eef2f7; font-weight: 600; }}
    code {{ background: #eef2f7; border-radius: 4px; padding: 1px 4px; }}
    a {{ color: #0f5bd8; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .number {{ text-align: right; font-variant-numeric: tabular-nums; }}
    .card {{ margin-top: 24px; padding: 20px; background: #fff; border: 1px solid #e5e7eb; border-radius: 10px; box-shadow: 0 1px 4px rgba(0,0,0,.06); }}
    .common-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 20px; }}
    .common-grid ul {{ margin-top: 8px; padding-left: 20px; }}
    .common-grid li {{ margin: 4px 0; overflow-wrap: anywhere; }}
    .muted {{ color: #6b7280; }}
    .pill {{ display: inline-block; padding: 3px 8px; border-radius: 999px; font-size: 12px; font-weight: 600; background: #e5e7eb; }}
    .likely_duplicate {{ color: #064e3b; background: #d1fae5; }}
    .high_overlap {{ color: #7c2d12; background: #ffedd5; }}
    .partial_overlap {{ color: #1e3a8a; background: #dbeafe; }}
    @media (max-width: 900px) {{ .common-grid {{ grid-template-columns: 1fr; }} main {{ padding: 18px; }} header {{ padding: 22px 18px; }} }}
  </style>
</head>
<body>
  <header>
    <h1>Semantic Model Duplicate Finder Report</h1>
    <div>{len(matches)} finding(s) met the configured threshold.</div>
  </header>
  <main>
    <table>
      <thead>
        <tr>
          <th>Classification</th>
          <th>Confidence</th>
          <th>Duplicate</th>
          <th>Overlap</th>
          <th>Left model</th>
          <th>Right model</th>
          <th>Shared tables</th>
          <th>Shared columns</th>
          <th>Shared measures</th>
          <th>Details</th>
        </tr>
      </thead>
      <tbody>
{rows}
      </tbody>
    </table>
{details}
  </main>
</body>
</html>
"""


def write_text(text: str, output_path: str | None) -> None:
    if output_path:
        Path(output_path).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)


def compare_command(args: argparse.Namespace) -> int:
    raw_models, warnings = load_inventory(Path(args.input))
    signatures_to_compare = [build_signature(model, warnings) for model in raw_models]
    matches = find_matches(
        signatures_to_compare,
        min_score=args.min_score,
        duplicate_threshold=args.duplicate_threshold,
        overlap_threshold=args.overlap_threshold,
        top=args.top,
        common_limit=args.common_limit,
    )

    payload = {
        "generatedAt": utc_now(),
        "modelCount": len(signatures_to_compare),
        "findingCount": len(matches),
        "matches": matches,
    }

    if args.format == "json":
        text = json.dumps(payload, indent=2, sort_keys=False) + "\n"
    elif args.format == "csv":
        text = render_csv(matches)
    elif args.format == "md":
        text = render_markdown(matches)
    elif args.format == "html":
        text = render_html(matches)
    else:
        raise ValueError(f"Unsupported format: {args.format}")

    write_text(text, args.output)
    if args.fail_on_duplicates and any(match["classification"] == "likely_duplicate" for match in matches):
        return 2
    return 0


def get_access_token(resource: str) -> str:
    command = [
        "az",
        "account",
        "get-access-token",
        "--resource",
        resource,
        "--query",
        "accessToken",
        "--output",
        "tsv",
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError("Azure CLI was not found. Install Azure CLI and run 'az login'.") from exc
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() or exc.stdout.strip()
        raise RuntimeError(f"Could not acquire Azure CLI token for {resource}: {detail}") from exc
    token = result.stdout.strip()
    if not token:
        raise RuntimeError(f"Azure CLI returned an empty access token for {resource}.")
    return token


def api_request(method: str, url: str, token: str, body: Mapping[str, Any] | None = None) -> Any:
    data = None
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            response_body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        response_body = exc.read().decode("utf-8", errors="replace")
        raise ApiError(method, url, exc.code, response_body) from exc
    except urllib.error.URLError as exc:
        raise ApiError(method, url, None, str(exc.reason)) from exc
    if not response_body:
        return {}
    return json.loads(response_body)


def collection(url: str, token: str) -> list[Mapping[str, Any]]:
    values: list[Mapping[str, Any]] = []
    next_url: str | None = url
    while next_url:
        payload = api_request("GET", next_url, token)
        if not isinstance(payload, Mapping):
            raise ApiError("GET", next_url, None, "Collection response was not a JSON object.")
        page = payload.get("value", [])
        if not isinstance(page, list):
            raise ApiError("GET", next_url, None, "Collection response did not contain a value array.")
        values.extend(page)
        next_url = payload.get("@odata.nextLink")
    return values


def quote_path(value: str) -> str:
    return urllib.parse.quote(value, safe="")


def normalize_response_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [{clean_key(key): value for key, value in row.items()} for row in rows]


def execute_dax(token: str, workspace_id: str, dataset_id: str, query: str) -> list[dict[str, Any]]:
    url = f"{PBI_API}/groups/{quote_path(workspace_id)}/datasets/{quote_path(dataset_id)}/executeQueries"
    payload = {
        "queries": [{"query": query}],
        "serializerSettings": {"includeNulls": True},
    }
    response = api_request("POST", url, token, payload)
    results = response.get("results", []) if isinstance(response, Mapping) else []
    if not results:
        return []
    tables = results[0].get("tables", [])
    if not tables:
        return []
    rows = tables[0].get("rows", [])
    return normalize_response_rows(rows)


def workspace_matches(workspace: Mapping[str, Any], names: Sequence[str]) -> bool:
    if not names:
        return True
    display_name = normalize_text(get_value(workspace, "name", "displayName"))
    return any(display_name == normalize_text(name) for name in names)


def model_matches(dataset: Mapping[str, Any], names: Sequence[str]) -> bool:
    if not names:
        return True
    display_name = normalize_text(get_value(dataset, "name", "displayName"))
    return any(display_name == normalize_text(name) for name in names)


def resolve_workspaces(token: str, workspace_ids: Sequence[str], workspace_names: Sequence[str]) -> list[Mapping[str, Any]]:
    if workspace_ids:
        resolved = []
        for workspace_id in workspace_ids:
            url = f"{PBI_API}/groups/{quote_path(workspace_id)}"
            try:
                workspace = api_request("GET", url, token)
            except ApiError:
                workspace = {"id": workspace_id, "name": workspace_id}
            resolved.append(workspace)
        return resolved
    workspaces = collection(f"{PBI_API}/groups?$top=5000", token)
    return [workspace for workspace in workspaces if workspace_matches(workspace, workspace_names)]


def warning_entry(workspace: Mapping[str, Any], dataset: Mapping[str, Any] | None, stage: str, message: str) -> dict[str, str]:
    return {
        "workspaceId": str(get_value(workspace, "id") or ""),
        "workspaceName": str(get_value(workspace, "name", "displayName") or ""),
        "modelId": str(get_value(dataset, "id", "datasetId") or "") if dataset else "",
        "modelName": str(get_value(dataset, "name", "displayName") or "") if dataset else "",
        "stage": stage,
        "message": message,
    }


def export_command(args: argparse.Namespace) -> int:
    token = get_access_token(PBI_RESOURCE)
    workspaces = resolve_workspaces(token, args.workspace_id or [], args.workspace_name or [])
    if not workspaces:
        raise RuntimeError("No matching workspaces were found.")

    models: list[dict[str, Any]] = []
    warnings: list[dict[str, str]] = []

    for workspace in workspaces:
        workspace_id = str(get_value(workspace, "id") or "")
        workspace_name = str(get_value(workspace, "name", "displayName") or workspace_id)
        try:
            datasets = collection(f"{PBI_API}/groups/{quote_path(workspace_id)}/datasets", token)
        except ApiError as exc:
            warnings.append(warning_entry(workspace, None, "datasets", exc.brief()))
            if args.strict:
                raise
            continue

        for dataset in datasets:
            if not model_matches(dataset, args.model_name or []):
                continue
            model = {
                "workspaceId": workspace_id,
                "workspaceName": workspace_name,
                "id": str(get_value(dataset, "id", "datasetId") or ""),
                "name": str(get_value(dataset, "name", "displayName") or ""),
                "dataset": dataset,
                "tables": [],
                "columns": [],
                "measures": [],
                "relationships": [],
                "dataSources": [],
            }

            for section, dax in DAX_METADATA_QUERIES.items():
                try:
                    model[section] = execute_dax(token, workspace_id, model["id"], dax)
                except ApiError as exc:
                    warnings.append(warning_entry(workspace, dataset, f"dax:{section}", exc.brief()))
                    if args.strict:
                        raise

            try:
                data_sources = api_request(
                    "GET",
                    f"{PBI_API}/groups/{quote_path(workspace_id)}/datasets/{quote_path(model['id'])}/datasources",
                    token,
                )
                if isinstance(data_sources, Mapping) and isinstance(data_sources.get("value"), list):
                    model["dataSources"] = data_sources["value"]
            except ApiError as exc:
                warnings.append(warning_entry(workspace, dataset, "datasources", exc.brief()))
                if args.strict:
                    raise

            models.append(model)
            if args.delay > 0:
                time.sleep(args.delay)

    payload = {
        "generatedAt": utc_now(),
        "workspaceCount": len(workspaces),
        "modelCount": len(models),
        "models": models,
        "warnings": warnings,
    }
    write_text(json.dumps(payload, indent=2) + "\n", args.output)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Find duplicate or overlapping Power BI semantic models.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    export_parser = subparsers.add_parser("export", help="Export semantic model metadata from accessible workspaces.")
    export_parser.add_argument("--workspace-id", action="append", help="Workspace ID to scan. Repeat for multiple workspaces.")
    export_parser.add_argument("--workspace-name", action="append", help="Exact workspace name to scan. Repeat for multiple workspaces.")
    export_parser.add_argument("--model-name", action="append", help="Exact semantic model name to include. Repeat for multiple models.")
    export_parser.add_argument("--output", required=True, help="Path to write inventory JSON.")
    export_parser.add_argument("--delay", type=float, default=0.0, help="Seconds to pause between models to reduce throttling risk.")
    export_parser.add_argument("--strict", action="store_true", help="Fail on the first inaccessible metadata endpoint.")
    export_parser.set_defaults(func=export_command)

    compare_parser = subparsers.add_parser("compare", help="Compare models in an exported inventory JSON file.")
    compare_parser.add_argument("--input", required=True, help="Inventory JSON path.")
    compare_parser.add_argument("--output", help="Output path. Defaults to stdout.")
    compare_parser.add_argument("--format", choices=("json", "csv", "md", "html"), default="json", help="Report format.")
    compare_parser.add_argument("--min-score", type=float, default=0.60, help="Minimum duplicate or overlap score to report.")
    compare_parser.add_argument("--duplicate-threshold", type=float, default=0.85, help="Score for likely_duplicate classification.")
    compare_parser.add_argument("--overlap-threshold", type=float, default=0.65, help="Score for high_overlap classification.")
    compare_parser.add_argument("--top", type=int, default=50, help="Maximum findings to return. Use 0 for all.")
    compare_parser.add_argument("--common-limit", type=int, default=25, help="Maximum common object names to list per object type per finding. Use 0 for all.")
    compare_parser.add_argument("--fail-on-duplicates", action="store_true", help="Return exit code 2 if likely duplicates are found.")
    compare_parser.set_defaults(func=compare_command)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
