"""Apply native audit edits to generated utterances and write QC statistics."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


AUDIT_COLUMNS = [
    "utterance_id",
    "domain",
    "tier",
    "intent_id",
    "screen_id",
    "target_element_id",
    "target_label",
    "original_text",
    "naturalness_score",
    "tier_validity",
    "label_leakage",
    "asr_tts_risk",
    "edited_text",
    "edit_type",
    "edit_reason",
    "auditor_notes",
]

NO_LEAKAGE_VALUES = {"", "none", "no_leakage", "false"}
VALID_TIER_VALUES = {"", "valid", "ok"}
REMOVE_EDIT_TYPE = "remove_bad_item"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--utterances", type=Path, default=Path("data/utterances/utterances.jsonl"))
    parser.add_argument("--audit", type=Path, default=Path("data/utterances/audit/native_audit_v1.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/utterances/utterances_audited.jsonl"))
    parser.add_argument("--summary", type=Path, default=Path("data/utterances/audit/native_audit_summary.md"))
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def load_jsonl(path: Path, label: str) -> list[dict[str, Any]]:
    if not path.exists():
        raise ValueError(f"{label} does not exist: {path}")
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{label}:{line_number}: invalid JSON: {exc.msg}") from exc
            if not isinstance(record, dict):
                raise ValueError(f"{label}:{line_number}: expected JSON object")
            records.append(record)
    if not records:
        raise ValueError(f"{label} contains no records: {path}")
    return records


def require_columns(fieldnames: list[str] | None, path: Path) -> None:
    if fieldnames is None:
        raise ValueError(f"audit CSV has no header: {path}")
    missing = [column for column in AUDIT_COLUMNS if column not in fieldnames]
    if missing:
        raise ValueError(f"audit CSV missing required columns {missing}: {path}")


def load_audit_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise ValueError(f"audit CSV does not exist: {path}")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        require_columns(reader.fieldnames, path)
        for line_number, row in enumerate(reader, start=2):
            utterance_id = clean(row.get("utterance_id"))
            if not utterance_id:
                raise ValueError(f"audit CSV:{line_number}: missing utterance_id")
            if utterance_id in seen:
                raise ValueError(f"duplicate audit utterance_id `{utterance_id}`")
            seen.add(utterance_id)
            rows.append({column: clean(row.get(column)) for column in AUDIT_COLUMNS})
    if not rows:
        raise ValueError(f"audit CSV contains no rows: {path}")
    return rows


def clean(value: str | None) -> str:
    return (value or "").strip()


def output_path_guard(path: Path, overwrite: bool) -> None:
    if path.exists() and path.stat().st_size > 0 and not overwrite:
        raise ValueError(f"{path} already exists; pass --overwrite to replace it")


def is_removed(row: dict[str, str]) -> bool:
    return clean(row.get("edit_type")) == REMOVE_EDIT_TYPE


def edited_text(row: dict[str, str]) -> str:
    return clean(row.get("edited_text"))


def is_edited(row: dict[str, str]) -> bool:
    return bool(edited_text(row)) and not is_removed(row)


def is_label_leakage_case(row: dict[str, str]) -> bool:
    return clean(row.get("label_leakage")).lower() not in NO_LEAKAGE_VALUES


def is_tier_mismatch_case(row: dict[str, str]) -> bool:
    value = clean(row.get("tier_validity"))
    if value.lower() in VALID_TIER_VALUES:
        return False
    return value != clean(row.get("tier"))


def validate_audit_against_utterances(
    utterances: list[dict[str, Any]], audit_rows_by_id: dict[str, dict[str, str]]
) -> None:
    utterance_ids: set[str] = set()
    for index, utterance in enumerate(utterances, start=1):
        utterance_id = utterance.get("utterance_id")
        if not isinstance(utterance_id, str) or not utterance_id:
            raise ValueError(f"utterances:{index}: missing or invalid utterance_id")
        if utterance_id in utterance_ids:
            raise ValueError(f"duplicate utterance_id `{utterance_id}` in source utterances")
        utterance_ids.add(utterance_id)

        audit_row = audit_rows_by_id.get(utterance_id)
        if audit_row is None:
            raise ValueError(f"missing audit row for utterance_id `{utterance_id}`")
        if clean(audit_row["original_text"]) != str(utterance.get("text_gold", "")).strip():
            raise ValueError(f"audit original_text does not match source text_gold for `{utterance_id}`")

    extra_ids = sorted(set(audit_rows_by_id) - utterance_ids)
    if extra_ids:
        raise ValueError(f"audit CSV contains rows for unknown utterance IDs {extra_ids}")


def apply_audit_edits(
    utterances: list[dict[str, Any]], audit_rows_by_id: dict[str, dict[str, str]]
) -> list[dict[str, Any]]:
    audited: list[dict[str, Any]] = []
    for utterance in utterances:
        audit_row = audit_rows_by_id[utterance["utterance_id"]]
        if is_removed(audit_row):
            continue
        output_record = dict(utterance)
        replacement_text = edited_text(audit_row)
        if replacement_text:
            output_record["text_gold"] = replacement_text
        audited.append(output_record)
    return audited


def write_jsonl(records: list[dict[str, Any]], path: Path, overwrite: bool) -> None:
    output_path_guard(path, overwrite)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def rate(numerator: int, denominator: int) -> str:
    percent = 0.0 if denominator == 0 else (numerator / denominator) * 100
    return f"{numerator}/{denominator} ({percent:.1f}%)"


def markdown_count_table(headers: tuple[str, ...], rows: list[tuple[Any, ...]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines)


def top_reason_rows(audit_rows: list[dict[str, str]]) -> list[tuple[str, int]]:
    counts = Counter(clean(row.get("edit_reason")) for row in audit_rows if clean(row.get("edit_reason")))
    return [(reason, count) for reason, count in counts.most_common()]


def edit_rate_rows(audit_rows: list[dict[str, str]], field: str) -> list[tuple[str, str]]:
    totals = Counter(clean(row.get(field)) or "<blank>" for row in audit_rows)
    edits = Counter(clean(row.get(field)) or "<blank>" for row in audit_rows if is_edited(row))
    return [(value, rate(edits[value], totals[value])) for value in sorted(totals)]


def case_rows(audit_rows: list[dict[str, str]], predicate: Any, field: str) -> list[tuple[str, str]]:
    rows = []
    for row in audit_rows:
        if predicate(row):
            rows.append((row["utterance_id"], clean(row.get(field))))
    return rows


def build_summary(audit_rows: list[dict[str, str]]) -> str:
    generated_count = len(audit_rows)
    naturalness_counts = Counter(clean(row.get("naturalness_score")) for row in audit_rows)
    edited_count = sum(1 for row in audit_rows if is_edited(row))
    removed_count = sum(1 for row in audit_rows if is_removed(row))
    leakage_cases = case_rows(audit_rows, is_label_leakage_case, "label_leakage")
    tier_mismatches = case_rows(audit_rows, is_tier_mismatch_case, "tier_validity")
    reason_rows = top_reason_rows(audit_rows)

    overview_rows = [
        ("number generated", generated_count),
        ("number natural", naturalness_counts["natural"]),
        ("number slightly awkward", naturalness_counts["slightly_awkward"]),
        ("number bad", naturalness_counts["bad"]),
        ("number edited", edited_count),
        ("edit rate", rate(edited_count, generated_count)),
        ("number removed", removed_count),
        ("label leakage cases found", len(leakage_cases)),
        ("tier mismatch cases found", len(tier_mismatches)),
    ]
    reason_table = (
        markdown_count_table(("edit_reason", "count"), reason_rows)
        if reason_rows
        else "No edit reasons recorded."
    )
    leakage_table = (
        markdown_count_table(("utterance_id", "label_leakage"), leakage_cases)
        if leakage_cases
        else "No label leakage cases recorded."
    )
    tier_table = (
        markdown_count_table(("utterance_id", "tier_validity"), tier_mismatches)
        if tier_mismatches
        else "No tier mismatch cases recorded."
    )

    return "\n\n".join(
        [
            "# Native Audit QC Summary",
            "This summary was generated from `data/utterances/audit/native_audit_v1.csv`.",
            "## Overview\n\n" + markdown_count_table(("metric", "value"), overview_rows),
            "## Top Edit Reasons\n\n" + reason_table,
            "## Edit Rate By Tier\n\n"
            + markdown_count_table(("tier", "edit_rate"), edit_rate_rows(audit_rows, "tier")),
            "## Edit Rate By Domain\n\n"
            + markdown_count_table(("domain", "edit_rate"), edit_rate_rows(audit_rows, "domain")),
            "## Label Leakage Cases\n\n" + leakage_table,
            "## Tier Mismatch Cases\n\n" + tier_table,
        ]
    ) + "\n"


def write_summary(audit_rows: list[dict[str, str]], path: Path, overwrite: bool) -> None:
    output_path_guard(path, overwrite)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_summary(audit_rows), encoding="utf-8")


def apply_native_audit(
    utterances_path: Path,
    audit_path: Path,
    output_path: Path,
    summary_path: Path,
    overwrite: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    utterances = load_jsonl(utterances_path, "utterances")
    audit_rows = load_audit_rows(audit_path)
    audit_rows_by_id = {row["utterance_id"]: row for row in audit_rows}
    validate_audit_against_utterances(utterances, audit_rows_by_id)
    audited = apply_audit_edits(utterances, audit_rows_by_id)
    write_jsonl(audited, output_path, overwrite=overwrite)
    write_summary(audit_rows, summary_path, overwrite=overwrite)
    return audited, audit_rows


def main() -> int:
    args = parse_args()
    try:
        audited, audit_rows = apply_native_audit(
            utterances_path=args.utterances,
            audit_path=args.audit,
            output_path=args.output,
            summary_path=args.summary,
            overwrite=args.overwrite,
        )
    except ValueError as exc:
        print(f"Native audit application failed: {exc}")
        return 1
    print(f"Wrote {len(audited)} audited utterances to {args.output}")
    print(f"Wrote QC summary for {len(audit_rows)} audit rows to {args.summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
