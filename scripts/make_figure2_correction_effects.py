"""Generate Figure 2 from frozen correction and grounding evaluation outputs."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any, Iterable

import fitz

from evaluate_asr import character_error_rate, loanword_error_counts, loanwords_for_utterance


WIDTH = 2800
HEIGHT = 2100

ASR_MODELS = (
    ("whisper_large_v3_local", "Whisper large-v3"),
    ("typhoon_asr_api", "Typhoon ASR"),
)
METHODS = (
    ("A_no_screen_cleanup", "A"),
    ("B_screen_string_match", "B"),
    ("C_full_screen_aware_alias", "C"),
)
TIERS = (
    ("T1_verbatim", "T1"),
    ("T2_paraphrase", "T2"),
    ("T3_intent", "T3"),
    ("T4_visual_positional", "T4"),
)
GROUNDING_MODELS = ("G1", "G2")

RAW_CONDITIONS = {
    "whisper_large_v3_local": "asr_whisper_large_v3_local",
    "typhoon_asr_api": "asr_typhoon_asr_api",
}


def corrected_condition(asr_model: str, method: str) -> str:
    suffix = "whisper" if asr_model == "whisper_large_v3_local" else "typhoon"
    return f"corrected_{method}_{suffix}"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
    return rows


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def mean(values: Iterable[float]) -> float | None:
    values = list(values)
    return sum(values) / len(values) if values else None


def is_correct(row: dict[str, Any]) -> bool:
    return row.get("click_in_target_bbox") is True


def same_coordinates(raw: dict[str, Any], corrected: dict[str, Any]) -> bool:
    values = (raw.get("pred_x"), raw.get("pred_y"), corrected.get("pred_x"), corrected.get("pred_y"))
    return all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values) and (
        values[0] == values[2] and values[1] == values[3]
    )


def build_source_rows(
    utterances: list[dict[str, Any]],
    corrections: list[dict[str, Any]],
    evaluations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    utterances_by_id = {row["utterance_id"]: row for row in utterances}
    correction_by_key = {
        (row["asr_model"], row["method"], row["audio_id"]): row
        for row in corrections
        if row.get("status") == "success"
    }
    if len(correction_by_key) != 2 * 3 * 471:
        raise ValueError(f"expected 2826 unique successful corrections, found {len(correction_by_key)}")

    raw_by_key: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    for row in evaluations:
        asr_model = str(row.get("asr_model") or "")
        if row.get("input_condition") != RAW_CONDITIONS.get(asr_model):
            continue
        key = (
            str(row.get("grounding_model")),
            asr_model,
            str(row.get("utterance_id")),
            str(row.get("audio_id")),
            str(row.get("screen_id")),
        )
        if key in raw_by_key:
            raise ValueError(f"duplicate raw grounding evaluation pair: {key}")
        raw_by_key[key] = row

    pairs: dict[tuple[str, str, str, str], list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]]] = defaultdict(list)
    valid_conditions = {
        corrected_condition(asr_model, method): (asr_model, method)
        for asr_model, _ in ASR_MODELS
        for method, _ in METHODS
    }
    seen_corrected: set[tuple[str, str, str, str, str, str]] = set()
    for corrected in evaluations:
        condition = str(corrected.get("input_condition") or "")
        if condition not in valid_conditions:
            continue
        asr_model, method = valid_conditions[condition]
        pair_key = (
            str(corrected.get("grounding_model")),
            asr_model,
            str(corrected.get("utterance_id")),
            str(corrected.get("audio_id")),
            str(corrected.get("screen_id")),
        )
        dedupe_key = (*pair_key, method)
        if dedupe_key in seen_corrected:
            raise ValueError(f"duplicate corrected grounding evaluation pair: {dedupe_key}")
        seen_corrected.add(dedupe_key)
        raw = raw_by_key.get(pair_key)
        if raw is None:
            raise ValueError(f"missing raw grounding evaluation pair: {pair_key}")
        correction = correction_by_key.get((asr_model, method, str(corrected.get("audio_id"))))
        if correction is None:
            raise ValueError(f"missing correction record for {dedupe_key}")
        if correction.get("utterance_id") != corrected.get("utterance_id"):
            raise ValueError(f"correction utterance mismatch for {dedupe_key}")
        tier = str(corrected.get("tier"))
        if tier != correction.get("tier"):
            raise ValueError(f"correction tier mismatch for {dedupe_key}")
        pairs[(pair_key[0], asr_model, method, tier)].append((raw, corrected, correction))

    transcript_metrics: dict[tuple[str, str, str], dict[str, int]] = {}
    correction_groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for correction in correction_by_key.values():
        correction_groups[(correction["asr_model"], correction["method"], correction["tier"])].append(correction)
    for key, group in correction_groups.items():
        recovery_count = 0
        false_count = 0
        for correction in group:
            utterance = utterances_by_id[correction["utterance_id"]]
            gold = str(utterance.get("text_gold", ""))
            raw_text = str(correction.get("input_transcript", ""))
            corrected_text = str(correction.get("corrected_transcript", ""))
            raw_cer = character_error_rate(gold, raw_text)
            corrected_cer = character_error_rate(gold, corrected_text)
            loanwords = loanwords_for_utterance(utterance)
            raw_loan_errors = loanword_error_counts(loanwords, raw_text)[1]
            corrected_loan_errors = loanword_error_counts(loanwords, corrected_text)[1]
            if corrected_cer < raw_cer or corrected_loan_errors < raw_loan_errors:
                recovery_count += 1
            if corrected_cer > raw_cer or (correction.get("changed") and raw_cer == 0):
                false_count += 1
        transcript_metrics[key] = {
            "n": len(group),
            "changed": sum(1 for row in group if row.get("changed")),
            "recovery": recovery_count,
            "false": false_count,
        }

    asr_labels = dict(ASR_MODELS)
    method_labels = dict(METHODS)
    tier_labels = {
        "T1_verbatim": "T1 verbatim",
        "T2_paraphrase": "T2 paraphrase",
        "T3_intent": "T3 intent",
        "T4_visual_positional": "T4 visual/positional",
    }
    rows: list[dict[str, Any]] = []
    for asr_model, _ in ASR_MODELS:
        for grounding_model in GROUNDING_MODELS:
            for method, _ in METHODS:
                for tier, _ in TIERS:
                    group = pairs[(grounding_model, asr_model, method, tier)]
                    transcript = transcript_metrics[(asr_model, method, tier)]
                    changed_group = [pair for pair in group if pair[2].get("changed")]
                    unchanged_group = [pair for pair in group if not pair[2].get("changed")]
                    if len(group) != transcript["n"] or len(changed_group) != transcript["changed"]:
                        raise ValueError(
                            f"transcript/grounding denominator mismatch for {(grounding_model, asr_model, method, tier)}"
                        )
                    raw_accuracy = mean(1.0 if is_correct(raw) else 0.0 for raw, _, _ in group)
                    corrected_accuracy = mean(1.0 if is_correct(corrected) else 0.0 for _, corrected, _ in group)
                    changed_raw = mean(1.0 if is_correct(raw) else 0.0 for raw, _, _ in changed_group)
                    changed_corrected = mean(
                        1.0 if is_correct(corrected) else 0.0 for _, corrected, _ in changed_group
                    )
                    unchanged_raw = mean(1.0 if is_correct(raw) else 0.0 for raw, _, _ in unchanged_group)
                    unchanged_corrected = mean(
                        1.0 if is_correct(corrected) else 0.0 for _, corrected, _ in unchanged_group
                    )
                    rows.append(
                        {
                            "asr_model": asr_model,
                            "asr_label": asr_labels[asr_model],
                            "grounding_model": grounding_model,
                            "correction_method": method,
                            "method_label": method_labels[method],
                            "tier": tier,
                            "tier_label": tier_labels[tier],
                            "n_total": len(group),
                            "n_changed": len(changed_group),
                            "n_unchanged": len(unchanged_group),
                            "raw_click_accuracy": raw_accuracy,
                            "corrected_run_click_accuracy": corrected_accuracy,
                            "pooled_click_delta": corrected_accuracy - raw_accuracy,
                            "changed_raw_click_accuracy": changed_raw,
                            "changed_corrected_click_accuracy": changed_corrected,
                            "changed_click_delta": (
                                changed_corrected - changed_raw
                                if changed_raw is not None and changed_corrected is not None
                                else None
                            ),
                            "unchanged_raw_click_accuracy": unchanged_raw,
                            "unchanged_corrected_click_accuracy": unchanged_corrected,
                            "unchanged_click_delta": (
                                unchanged_corrected - unchanged_raw
                                if unchanged_raw is not None and unchanged_corrected is not None
                                else None
                            ),
                            "exact_same_coordinate_changed": sum(
                                1 for raw, corrected, _ in changed_group if same_coordinates(raw, corrected)
                            ),
                            "different_coordinate_changed": sum(
                                1 for raw, corrected, _ in changed_group if not same_coordinates(raw, corrected)
                            ),
                            "recovery_count": transcript["recovery"],
                            "recovery_rate": transcript["recovery"] / transcript["n"],
                            "false_correction_count": transcript["false"],
                            "false_correction_rate": transcript["false"] / transcript["n"],
                        }
                    )
    if len(rows) != 48:
        raise ValueError(f"expected 48 per-tier source rows, found {len(rows)}")
    return rows


def weighted_accuracy(rows: list[dict[str, Any]], field: str, denominator: str) -> float | None:
    usable = [row for row in rows if row[field] is not None and row[denominator] > 0]
    total = sum(row[denominator] for row in usable)
    return sum(row[field] * row[denominator] for row in usable) / total if total else None


def assert_close(actual: float | None, expected: str, context: str, tolerance: float = 1e-6) -> None:
    if expected == "":
        if actual is not None:
            raise ValueError(f"expected no value for {context}, found {actual}")
        return
    if actual is None or abs(actual - float(expected)) > tolerance:
        raise ValueError(f"aggregate mismatch for {context}: {actual} != {expected}")


def validate_against_final_tables(
    source_rows: list[dict[str, Any]],
    table4: list[dict[str, str]],
    table4b: list[dict[str, str]],
) -> None:
    source_groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in source_rows:
        source_groups[(row["grounding_model"], row["asr_model"], row["correction_method"])].append(row)
    for final in table4:
        key = (final["grounding_model"], final["asr_model"], final["correction_method"])
        group = source_groups[key]
        if sum(row["n_total"] for row in group) != int(final["n_total"]):
            raise ValueError(f"n_total mismatch for {key}")
        if sum(row["n_changed"] for row in group) != int(final["changed_count"]):
            raise ValueError(f"changed count mismatch for {key}")
        if sum(row["false_correction_count"] for row in group) != int(final["false_correction_count"]):
            raise ValueError(f"false-correction count mismatch for {key}")
        assert_close(weighted_accuracy(group, "raw_click_accuracy", "n_total"), final["raw_click_accuracy"], f"raw {key}")
        assert_close(
            weighted_accuracy(group, "corrected_run_click_accuracy", "n_total"),
            final["corrected_run_click_accuracy"],
            f"corrected {key}",
        )

    changed_final = [row for row in table4b if row["subset"] == "changed"]
    for final in changed_final:
        key = (final["grounding_model"], final["asr_model"], final["correction_method"])
        group = source_groups[key]
        if sum(row["n_changed"] for row in group) != int(final["n"]):
            raise ValueError(f"changed subset n mismatch for {key}")
        assert_close(
            weighted_accuracy(group, "changed_raw_click_accuracy", "n_changed"),
            final["raw_click_accuracy"],
            f"changed raw {key}",
        )
        assert_close(
            weighted_accuracy(group, "changed_corrected_click_accuracy", "n_changed"),
            final["corrected_run_click_accuracy"],
            f"changed corrected {key}",
        )


def write_source_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: "" if value is None else f"{value:.6f}" if isinstance(value, float) else value
                    for key, value in row.items()
                }
            )


def svg_text(
    x: float,
    y: float,
    value: str,
    size: int,
    *,
    anchor: str = "middle",
    weight: int = 400,
    fill: str = "#111111",
) -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" '
        f'font-family="Arial, Helvetica, sans-serif" font-size="{size}" '
        f'font-weight="{weight}" fill="{fill}">{escape(value)}</text>'
    )


def marker_svg(
    x: float,
    y: float,
    method: str,
    stroke: str,
    size: float = 8.0,
    fill: str = "#ffffff",
) -> str:
    if method == "A_no_screen_cleanup":
        return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{size:.1f}" fill="{fill}" stroke="{stroke}" stroke-width="3"/>'
    if method == "B_screen_string_match":
        return (
            f'<rect x="{x - size:.1f}" y="{y - size:.1f}" width="{2 * size:.1f}" height="{2 * size:.1f}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="3"/>'
        )
    points = f"{x:.1f},{y-size-1:.1f} {x-size-1:.1f},{y+size:.1f} {x+size+1:.1f},{y+size:.1f}"
    return f'<polygon points="{points}" fill="{fill}" stroke="{stroke}" stroke-width="3"/>'


@dataclass(frozen=True)
class DotPanel:
    x: int
    y: int
    width: int
    height: int
    title: str
    asr_model: str
    grounding_model: str | None
    metric: str
    x_min: float
    x_max: float
    ticks: tuple[float, ...]
    x_label: str


METHOD_COLORS = {
    "A_no_screen_cleanup": "#0072B2",
    "B_screen_string_match": "#D55E00",
    "C_full_screen_aware_alias": "#009E73",
}

TIER_DISPLAY = {
    "T1_verbatim": "T1 verbatim",
    "T2_paraphrase": "T2 paraphrase",
    "T3_intent": "T3 intent",
    "T4_visual_positional": "T4 visual/positional",
}


def dot_panel_svg(panel: DotPanel, rows: list[dict[str, Any]]) -> tuple[str, int, int]:
    plot_left = panel.x + 225
    plot_right = panel.x + panel.width - 190
    plot_top = panel.y + 72
    plot_bottom = panel.y + panel.height - 58
    plot_width = plot_right - plot_left
    band_height = (plot_bottom - plot_top) / len(TIERS)
    method_offsets = (-25.0, 0.0, 25.0)

    def x_position(value: float) -> float:
        return plot_left + ((value - panel.x_min) / (panel.x_max - panel.x_min)) * plot_width

    parts = [
        f'<rect x="{panel.x}" y="{panel.y}" width="{panel.width}" height="{panel.height}" '
        'rx="8" fill="#FCFDFE" stroke="#B8C2CC" stroke-width="2"/>',
        svg_text(panel.x + panel.width / 2, panel.y + 38, panel.title, 29, weight=700),
    ]

    for tier_index, (tier, _) in enumerate(TIERS):
        band_top = plot_top + tier_index * band_height
        center_y = band_top + band_height / 2
        if tier_index % 2 == 0:
            parts.append(
                f'<rect x="{plot_left}" y="{band_top:.1f}" width="{plot_width}" height="{band_height:.1f}" '
                'fill="#F3F6F8"/>'
            )
        parts.append(svg_text(plot_left - 18, center_y + 7, TIER_DISPLAY[tier], 22, anchor="end", weight=700))

    for tick in panel.ticks:
        x = x_position(tick)
        stroke = "#4B5563" if abs(tick) < 1e-9 else "#D8DEE4"
        width = 2.5 if abs(tick) < 1e-9 else 1.4
        parts.append(
            f'<line x1="{x:.1f}" y1="{plot_top}" x2="{x:.1f}" y2="{plot_bottom}" '
            f'stroke="{stroke}" stroke-width="{width}"/>'
        )
        parts.append(svg_text(x, plot_bottom + 27, f"{tick:.0f}", 19, fill="#4B5563"))
    parts.append(svg_text((plot_left + plot_right) / 2, panel.y + panel.height - 12, panel.x_label, 20, fill="#374151"))

    plotted = 0
    empty = 0
    for tier_index, (tier, _) in enumerate(TIERS):
        center_y = plot_top + (tier_index + 0.5) * band_height
        for method_index, (method, method_label) in enumerate(METHODS):
            candidates = [
                row
                for row in rows
                if row["asr_model"] == panel.asr_model
                and row["tier"] == tier
                and row["correction_method"] == method
                and (
                    row["grounding_model"] == panel.grounding_model
                    if panel.grounding_model is not None
                    else row["grounding_model"] == "G1"
                )
            ]
            if len(candidates) != 1:
                raise ValueError(f"expected one source row for {(panel.title, tier, method)}, found {len(candidates)}")
            row = candidates[0]
            y = center_y + method_offsets[method_index]
            color = METHOD_COLORS[method]
            denominator = row["n_changed"] if panel.metric == "changed_click_delta" else row["n_total"]
            value = row[panel.metric]
            if value is None or denominator == 0:
                parts.append(
                    svg_text(
                        plot_left + 12,
                        y + 7,
                        f"{method_label}: no changed transcripts (n=0)",
                        17,
                        anchor="start",
                        fill="#737B84",
                    )
                )
                empty += 1
                continue

            display_value = value * 100.0
            if not panel.x_min <= display_value <= panel.x_max:
                raise ValueError(f"unplottable unclipped value {display_value} in {panel.title}")
            x = x_position(display_value)
            parts.append(marker_svg(x, y, method, color, size=8.5, fill=color))
            if panel.metric == "changed_click_delta":
                label = f"{display_value:+.1f} pp (n={denominator})"
            else:
                label = f"{display_value:.1f}% (n={denominator})"
            use_left_label = display_value > panel.x_min + 0.76 * (panel.x_max - panel.x_min)
            label_x = x - 15 if use_left_label else x + 15
            anchor = "end" if use_left_label else "start"
            parts.append(svg_text(label_x, y + 7, label, 17, anchor=anchor, weight=700, fill=color))
            plotted += 1

    return "\n".join(parts), plotted, empty


def build_svg(rows: list[dict[str, Any]]) -> str:
    panel_width = 1295
    changed_height = 500
    fcr_height = 430
    panels = (
        DotPanel(70, 205, panel_width, changed_height, "Whisper / G1", "whisper_large_v3_local", "G1", "changed_click_delta", -105.0, 25.0, (-100, -75, -50, -25, 0, 25), "Changed click delta (percentage points)"),
        DotPanel(1435, 205, panel_width, changed_height, "Whisper / G2", "whisper_large_v3_local", "G2", "changed_click_delta", -105.0, 25.0, (-100, -75, -50, -25, 0, 25), "Changed click delta (percentage points)"),
        DotPanel(70, 750, panel_width, changed_height, "Typhoon / G1", "typhoon_asr_api", "G1", "changed_click_delta", -105.0, 25.0, (-100, -75, -50, -25, 0, 25), "Changed click delta (percentage points)"),
        DotPanel(1435, 750, panel_width, changed_height, "Typhoon / G2", "typhoon_asr_api", "G2", "changed_click_delta", -105.0, 25.0, (-100, -75, -50, -25, 0, 25), "Changed click delta (percentage points)"),
        DotPanel(70, 1415, panel_width, fcr_height, "Whisper", "whisper_large_v3_local", None, "false_correction_rate", 0.0, 40.0, (0, 10, 20, 30, 40), "False correction rate (%)"),
        DotPanel(1435, 1415, panel_width, fcr_height, "Typhoon", "typhoon_asr_api", None, "false_correction_rate", 0.0, 40.0, (0, 10, 20, 30, 40), "False correction rate (%)"),
    )

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
        f'<rect width="{WIDTH}" height="{HEIGHT}" fill="#ffffff"/>',
        svg_text(WIDTH / 2, 54, "Per-tier fixed-correction effects", 48, weight=700),
        svg_text(WIDTH / 2, 98, "Changed-transcript effects are separated by ASR and grounding model", 27, fill="#444444"),
        svg_text(WIDTH / 2, 158, "A. Changed-transcript click delta", 32, weight=700),
        svg_text(WIDTH / 2, 1328, "B. False correction rate", 32, weight=700),
        svg_text(WIDTH / 2, 1365, "Transcript-level metric shared by G1 and G2", 23, fill="#4B5563"),
    ]

    changed_plotted = 0
    changed_empty = 0
    fcr_plotted = 0
    for panel in panels:
        panel_content, plotted, empty = dot_panel_svg(panel, rows)
        parts.append(panel_content)
        if panel.metric == "changed_click_delta":
            changed_plotted += plotted
            changed_empty += empty
        else:
            fcr_plotted += plotted
    if changed_plotted != 28 or changed_empty != 20:
        raise ValueError(f"unexpected changed-point coverage: plotted={changed_plotted}, n0={changed_empty}")
    if fcr_plotted != 24:
        raise ValueError(f"unexpected FCR point coverage: {fcr_plotted}")

    legend_y = 1905
    parts.append(svg_text(120, legend_y, "Methods:", 23, anchor="start", weight=700))
    legend_x = 270
    for method, label in METHODS:
        color = METHOD_COLORS[method]
        parts.append(marker_svg(legend_x, legend_y - 7, method, color, size=8.5, fill=color))
        parts.append(svg_text(legend_x + 22, legend_y, f"{label}: {method.split('_', 1)[1].replace('_', ' ')}", 20, anchor="start"))
        legend_x += 620
    parts.append(svg_text(WIDTH / 2, 1960, "Exact values and denominators are printed beside every point; negative effects are not clipped.", 22, fill="#444444"))
    parts.append(svg_text(WIDTH / 2, 2000, "Pooled deltas are omitted here because independent grounding reruns confound them; see Table 4.", 22, fill="#444444"))
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def render(svg: str, svg_path: Path, png_path: Path, pdf_path: Path) -> None:
    svg_path.write_text(svg, encoding="utf-8")
    document = fitz.open(stream=svg.encode("utf-8"), filetype="svg")
    pdf_path.write_bytes(document.convert_to_pdf())
    page = document[0]
    scale = WIDTH / page.rect.width
    pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
    pixmap.save(png_path)


def main() -> None:
    repo = Path(__file__).resolve().parents[1]
    figures = repo / "figures"
    source_rows = build_source_rows(
        load_jsonl(repo / "data" / "utterances" / "utterances_audited.jsonl"),
        load_jsonl(repo / "data" / "corrections" / "corrected_transcripts.jsonl"),
        load_jsonl(repo / "data" / "predictions" / "grounding_evaluation_by_file.jsonl"),
    )
    validate_against_final_tables(
        source_rows,
        load_csv(repo / "data" / "results" / "table4_correction_effects.csv"),
        load_csv(repo / "data" / "results" / "table4b_changed_unchanged_effects.csv"),
    )
    write_source_csv(figures / "figure2_source_data.csv", source_rows)
    render(
        build_svg(source_rows),
        figures / "figure2_per_tier_correction_effects.svg",
        figures / "figure2_per_tier_correction_effects.png",
        figures / "figure2_per_tier_correction_effects.pdf",
    )
    print(f"Wrote {len(source_rows)} source rows")
    print("Validated per-tier aggregates against Tables 4 and 4b")


if __name__ == "__main__":
    main()
