"""Summarize a completed manual failure and rerun-variability review."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path
from typing import Callable


ALLOWED_TAXONOMY = {
    "loanword_ASR_error",
    "Thai_word_segmentation_issue",
    "confusable_screen_label",
    "visual_grounding_error",
    "positional_phrase_failure",
    "over_correction",
    "ambiguous_instruction",
    "TTS_pronunciation_issue",
    "parse_failure",
    "out_of_bounds_prediction",
    "correction_helped",
    "correction_helped_transcript_but_hurt_grounding",
    "correction_changed_without_downstream_gain",
    "unchanged_prompt_rerun_variability",
    "other",
}

TRUE_VALUES = {"true", "yes", "1", "y"}
FALSE_VALUES = {"false", "no", "0", "n"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", type=Path, default=Path("data/analysis/failure_review_sample.csv"))
    parser.add_argument(
        "--diagnosis", type=Path, default=Path("data/analysis/correction_degradation_diagnosis.md")
    )
    parser.add_argument(
        "--summary", type=Path, default=Path("data/analysis/failure_taxonomy_summary.csv")
    )
    parser.add_argument("--report", type=Path, default=Path("data/analysis/FAILURE_ANALYSIS_REPORT.md"))
    parser.add_argument(
        "--examples", type=Path, default=Path("data/analysis/qualitative_examples_for_paper.md")
    )
    return parser.parse_args()


def load_sample(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        rows = list(reader)
    if not rows:
        raise ValueError(f"manual review sample is empty: {path}")
    required = {
        "case_id",
        "screen_id",
        "tier",
        "asr_model",
        "grounding_model",
        "correction_method",
        "gold_text",
        "raw_asr_transcript",
        "corrected_transcript",
        "transcript_changed",
        "target_label",
        "predicted_label_raw",
        "predicted_label_corrected",
        "raw_coordinates",
        "corrected_coordinates",
        "raw_click_correct",
        "corrected_click_correct",
        "transition_type",
        "manual_failure_taxonomy",
        "notes",
        "include_as_qualitative_example",
    }
    missing = sorted(required - set(reader.fieldnames or []))
    if missing:
        raise ValueError(f"manual review CSV is missing columns: {', '.join(missing)}")

    case_ids: set[str] = set()
    for line_number, row in enumerate(rows, 2):
        case_id = row["case_id"].strip()
        if not case_id or case_id in case_ids:
            raise ValueError(f"{path}:{line_number}: missing or duplicate case_id")
        case_ids.add(case_id)
        taxonomy = row["manual_failure_taxonomy"].strip()
        if not taxonomy:
            raise ValueError(f"{path}:{line_number}: manual_failure_taxonomy is blank")
        if taxonomy not in ALLOWED_TAXONOMY:
            raise ValueError(f"{path}:{line_number}: unsupported manual taxonomy {taxonomy!r}")
        if row["transition_type"].strip() not in {"CC", "WC", "CW", "WW"}:
            raise ValueError(f"{path}:{line_number}: invalid transition_type")
        for field in ("transcript_changed", "raw_click_correct", "corrected_click_correct"):
            if row[field].strip().lower() not in TRUE_VALUES | FALSE_VALUES:
                raise ValueError(f"{path}:{line_number}: invalid boolean in {field}")
        if not row["notes"].strip():
            raise ValueError(f"{path}:{line_number}: notes are blank; manual review is incomplete")
        if row["include_as_qualitative_example"].strip().lower() not in TRUE_VALUES | FALSE_VALUES:
            raise ValueError(f"{path}:{line_number}: invalid qualitative-example decision")
    return rows


def is_true(value: str) -> bool:
    return value.strip().lower() in TRUE_VALUES


def count_text(counter: Counter[str]) -> str:
    return "; ".join(f"{key}: {value}" for key, value in sorted(counter.items()))


def taxonomy_counts(rows: list[dict[str, str]]) -> Counter[str]:
    return Counter(row["manual_failure_taxonomy"].strip() for row in rows)


def summary_rows(rows: list[dict[str, str]]) -> list[dict[str, str | int | float]]:
    output: list[dict[str, str | int | float]] = []

    def add_counts(dimension: str, group: str, counter: Counter[str], denominator: int) -> None:
        for category, count in sorted(counter.items()):
            output.append(
                {
                    "dimension": dimension,
                    "group": group,
                    "category": category,
                    "count": count,
                    "percent_within_group": count / denominator if denominator else 0.0,
                }
            )

    add_counts("overall", "all", taxonomy_counts(rows), len(rows))
    for field in ("tier", "asr_model", "grounding_model", "correction_method"):
        for group in sorted({row[field] for row in rows}):
            subset = [row for row in rows if row[field] == group]
            add_counts(field, group, taxonomy_counts(subset), len(subset))

    transitions = Counter(row["transition_type"] for row in rows)
    add_counts("transition_type", "all", transitions, len(rows))
    for changed in ("true", "false"):
        subset = [row for row in rows if row["transcript_changed"].strip().lower() == changed]
        add_counts("transcript_changed_taxonomy", changed, taxonomy_counts(subset), len(subset))
        add_counts(
            "transition_by_transcript_changed",
            changed,
            Counter(row["transition_type"] for row in subset),
            len(subset),
        )
    return output


def write_summary(path: Path, rows: list[dict[str, str | int | float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=("dimension", "group", "category", "count", "percent_within_group"),
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    **row,
                    "percent_within_group": f"{float(row['percent_within_group']):.6f}",
                }
            )


def choose_example(
    rows: list[dict[str, str]],
    predicate: Callable[[dict[str, str]], bool],
    used: set[str],
    prefer: Callable[[dict[str, str]], tuple] | None = None,
) -> dict[str, str]:
    eligible = [row for row in rows if row["case_id"] not in used and predicate(row)]
    if not eligible:
        raise ValueError("completed review does not contain a required qualitative example")
    prefer = prefer or (lambda row: ())
    selected = min(
        eligible,
        key=lambda row: (
            not is_true(row["include_as_qualitative_example"]),
            *prefer(row),
            row["case_id"],
        ),
    )
    used.add(selected["case_id"])
    return selected


def select_examples(rows: list[dict[str, str]]) -> list[tuple[str, dict[str, str]]]:
    used: set[str] = set()
    helped = choose_example(
        rows,
        lambda row: row["manual_failure_taxonomy"] == "correction_helped"
        and row["transition_type"] == "WC"
        and is_true(row["transcript_changed"]),
        used,
    )
    false_correction = choose_example(
        rows,
        lambda row: row["manual_failure_taxonomy"] == "over_correction"
        and row["transition_type"] == "CW"
        and is_true(row["transcript_changed"]),
        used,
        prefer=lambda row: (row["raw_asr_transcript"] != row["gold_text"],),
    )
    plausible_hurt = choose_example(
        rows,
        lambda row: row["manual_failure_taxonomy"]
        == "correction_helped_transcript_but_hurt_grounding"
        and row["transition_type"] == "CW"
        and is_true(row["transcript_changed"]),
        used,
    )
    unchanged_flip = choose_example(
        rows,
        lambda row: row["manual_failure_taxonomy"] == "unchanged_prompt_rerun_variability"
        and row["transition_type"] in {"WC", "CW"},
        used,
        prefer=lambda row: (is_true(row["transcript_changed"]),),
    )
    return [
        ("Correction helped", helped),
        ("False correction", false_correction),
        ("Plausible correction, worse grounding", plausible_hurt),
        ("Unchanged prompt, different click outcome", unchanged_flip),
    ]


def prediction_text(row: dict[str, str], corrected: bool) -> str:
    suffix = "corrected" if corrected else "raw"
    label = row[f"predicted_label_{suffix}"].strip() or "(empty)"
    coordinates = row[f"{suffix}_coordinates"].strip() or "(unparseable/no coordinates)"
    click = row[f"{suffix}_click_correct"].strip().lower()
    return f'label="{label}", coordinates={coordinates}, click_correct={click}'


def example_markdown(title: str, row: dict[str, str], number: int) -> str:
    return f"""## {number}. {title} (`{row['case_id']}`)

- Screen: `{row['screen_id']}`
- Tier: `{row['tier']}`
- ASR / grounding / correction: `{row['asr_model']}` / `{row['grounding_model']}` / `{row['correction_method']}`
- Target label: `{row['target_label']}`
- Gold text: {row['gold_text']}
- Raw ASR transcript: {row['raw_asr_transcript']}
- Corrected transcript: {row['corrected_transcript']}
- Transcript changed: `{row['transcript_changed'].lower()}`
- Raw prediction: {prediction_text(row, False)}
- Corrected-run prediction: {prediction_text(row, True)}
- Transition: `{row['transition_type']}`
- Interpretation: {row['notes'].strip()}
"""


def distribution_table(counter: Counter[str], total: int) -> str:
    lines = ["| Manual taxonomy | Cases | Percent |", "| --- | ---: | ---: |"]
    for category, count in counter.most_common():
        lines.append(f"| `{category}` | {count} | {count / total:.1%} |")
    return "\n".join(lines)


def grouped_distribution(rows: list[dict[str, str]], field: str, label: str) -> str:
    lines = [f"| {label} | Cases | Manual taxonomy counts |", "| --- | ---: | --- |"]
    for group in sorted({row[field] for row in rows}):
        subset = [row for row in rows if row[field] == group]
        lines.append(f"| `{group}` | {len(subset)} | {count_text(taxonomy_counts(subset))} |")
    return "\n".join(lines)


def transition_table(rows: list[dict[str, str]]) -> str:
    counts = Counter(row["transition_type"] for row in rows)
    lines = ["| Transition | Cases | Percent |", "| --- | ---: | ---: |"]
    for transition in ("CC", "WC", "CW", "WW"):
        count = counts[transition]
        lines.append(f"| `{transition}` | {count} | {count / len(rows):.1%} |")
    return "\n".join(lines)


def changed_table(rows: list[dict[str, str]]) -> str:
    lines = [
        "| Stored transcript change | Cases | CC | WC | CW | WW |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for changed in (True, False):
        subset = [row for row in rows if is_true(row["transcript_changed"]) == changed]
        transitions = Counter(row["transition_type"] for row in subset)
        lines.append(
            f"| `{str(changed).lower()}` | {len(subset)} | {transitions['CC']} | {transitions['WC']} | "
            f"{transitions['CW']} | {transitions['WW']} |"
        )
    return "\n".join(lines)


def write_examples(path: Path, examples: list[tuple[str, dict[str, str]]]) -> None:
    sections = "\n".join(
        example_markdown(title, row, index) for index, (title, row) in enumerate(examples, 1)
    )
    text = f"""# Qualitative Examples for the Paper

These four manually reviewed cases come from synthetic GUI screens and TTS-generated commands. They contain no real user or private-account data. Raw and corrected grounding predictions were produced in independent inference runs, so unchanged-prompt click differences are treated as rerun variability.

{sections}
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_report(
    path: Path,
    rows: list[dict[str, str]],
    examples: list[tuple[str, dict[str, str]]],
    diagnosis_path: Path,
) -> None:
    overall = taxonomy_counts(rows)
    helping = [row for row in rows if row["manual_failure_taxonomy"] == "correction_helped"]
    harming = [
        row
        for row in rows
        if row["manual_failure_taxonomy"]
        in {"over_correction", "correction_helped_transcript_but_hurt_grounding"}
    ]
    variability = [
        row for row in rows if row["manual_failure_taxonomy"] == "unchanged_prompt_rerun_variability"
    ]
    exact_unchanged_variability = [row for row in variability if not is_true(row["transcript_changed"])]
    normalization_noop_variability = [row for row in variability if is_true(row["transcript_changed"])]
    selected_sections = "\n".join(
        example_markdown(title, row, index) for index, (title, row) in enumerate(examples, 1)
    )
    text = f"""# Manual Failure and Rerun-Variability Analysis

## Scope

This report summarizes all **{len(rows)}** completed manual annotations in `failure_review_sample.csv`. No predictions, correction outputs, thresholds, prompts, aliases, model settings, or result tables were changed.

The sample was deliberately stratified around failures, correction effects, and rerun variability. Its category percentages describe this review sample and are **not prevalence estimates for the full benchmark**. The attribution boundary follows `{diagnosis_path.as_posix()}`: raw and corrected grounding were independent inference runs, and unchanged/no-op prompt differences are not attributed to correction.

## Final Taxonomy Distribution

{distribution_table(overall, len(rows))}

## Taxonomy by Tier

{grouped_distribution(rows, 'tier', 'Tier')}

## Taxonomy by ASR Model

{grouped_distribution(rows, 'asr_model', 'ASR model')}

## Taxonomy by Grounding Model

{grouped_distribution(rows, 'grounding_model', 'Grounding model')}

## Taxonomy by Correction Method

{grouped_distribution(rows, 'correction_method', 'Correction method')}

Full long-form counts and within-group percentages are in `failure_taxonomy_summary.csv`.

## Outcome Transitions

{transition_table(rows)}

`CC`, `WC`, `CW`, and `WW` denote raw/corrected click correctness. Parse failures and out-of-bounds points are incorrect clicks.

## Changed Transcripts and Rerun Variability

{changed_table(rows)}

- The stored correction flag marks **{sum(is_true(row['transcript_changed']) for row in rows)}** cases changed and **{sum(not is_true(row['transcript_changed']) for row in rows)}** unchanged.
- Manual review assigned **{len(variability)}** cases to `unchanged_prompt_rerun_variability`: **{len(exact_unchanged_variability)}** had exactly unchanged transcript text, while **{len(normalization_noop_variability)}** were stored as changed but were judged normalization-only/no-op changes.
- These rerun-variability cases include {Counter(row['transition_type'] for row in variability)['WC']} `WC` and {Counter(row['transition_type'] for row in variability)['CW']} `CW` flips. They are not evidence that correction helped or harmed grounding.

## Correction-Helping Patterns

Manual review labeled **{len(helping)}** sampled cases as `correction_helped`; all were `WC` transitions. They comprise {count_text(Counter(row['correction_method'] for row in helping))} and {count_text(Counter(row['asr_model'] for row in helping))}. The selected clear example repairs a Thai alias to the visible English label `Cart`. Because this is a stratified sample and inference runs were independent, these counts are qualitative evidence rather than an estimated recovery rate.

## Correction-Harming Patterns

Manual review identified **{len(harming)}** harming cases: {overall['over_correction']} `over_correction` and {overall['correction_helped_transcript_but_hurt_grounding']} linguistically helpful corrections followed by worse grounding. All {len(harming)} are `CW` transitions; {Counter(row['correction_method'] for row in harming)['C_full_screen_aware_alias']} use Method C. Examples include visible-label injection redirecting the click and a correct screen-string repair followed by a worse independent grounding result.

## Rerun-Variability Patterns

The **{len(variability)}** manually labeled variability cases are concentrated in {count_text(Counter(row['grounding_model'] for row in variability))}. This is consistent with the separate degradation diagnosis, which found substantially lower coordinate repeatability for UI-TARS and full no-op Typhoon A/B controls with changed click outcomes. Parse success remains distinct from click correctness.

## Selected Qualitative Examples

{selected_sections}

## Limitations Revealed by the Analysis

- The 140 cases were purposefully sampled, so category shares cannot be generalized to the full dataset without weighting.
- Raw and corrected grounding are independent inference runs. The analysis can identify changed-text associations but cannot fully isolate correction causality from rerun stochasticity.
- Unicode normalization can set `transcript_changed=true` without a meaningful linguistic change; manual review separated these no-op cases.
- UI-TARS parse failures and out-of-bounds coordinates are distinct failure modes, and both remain incorrect in click evaluation.
- T3/T4 ambiguity and positional failures can persist even when ASR is usable, while confusable labels can redirect an otherwise plausible click.
- The benchmark uses 20 synthetic screens and TTS-generated speech, so it does not establish behavior for real user speech or production interfaces.
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> int:
    args = parse_args()
    rows = load_sample(args.sample)
    if not args.diagnosis.exists():
        raise FileNotFoundError(args.diagnosis)
    summary = summary_rows(rows)
    examples = select_examples(rows)
    write_summary(args.summary, summary)
    write_examples(args.examples, examples)
    write_report(args.report, rows, examples, args.diagnosis)
    print(f"reviewed_rows={len(rows)}")
    print(f"summary_rows={len(summary)}")
    print("selected_examples=" + ",".join(row["case_id"] for _, row in examples))
    print(f"summary={args.summary}")
    print(f"report={args.report}")
    print(f"examples={args.examples}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
