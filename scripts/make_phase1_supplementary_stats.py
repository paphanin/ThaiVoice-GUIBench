"""Post-hoc supplementary statistics over the frozen outputs.

Computes, without modifying any frozen artifact:
  A. Exact two-sided sign tests on paired WC/CW click flips for every
     correction group (changed, unchanged, and pooled subsets).
  B. Wilson 95% intervals for the six baseline grounding accuracies.
  C. A per-command paired comparison of gold versus raw-ASR grounding
     (commands are the clustering unit; audio renditions are averaged
     within command) with a seeded bootstrap interval.
  D. A split of frozen "changed" transcripts into cosmetic
     (Unicode/whitespace-only under NFKC) versus substantive changes,
     with recovery/false-correction recomputed under NFKC-normalized CER.

Outputs (new files under data/analysis/):
  phase1_supplementary_stats.csv
  false_correction_cosmetic_split.csv
  PHASE1_SUPPLEMENTARY_ANALYSIS.md
"""

from __future__ import annotations

import csv
import json
import math
import random
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

from evaluate_asr import (
    character_error_rate,
    loanword_error_counts,
    loanwords_for_utterance,
    normalize_text,
)

ROOT = Path(__file__).resolve().parent.parent
ANALYSIS_DIR = ROOT / "data" / "analysis"
BOOTSTRAP_SEED = 20260719
BOOTSTRAP_ITERATIONS = 10000


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def sign_test_p(b: int, c: int) -> float | None:
    """Exact two-sided binomial sign test on b vs c discordant pairs."""
    n = b + c
    if n == 0:
        return None
    k = max(b, c)
    tail = sum(math.comb(n, i) for i in range(k, n + 1)) / (2 ** n)
    return min(1.0, 2.0 * tail)


def wilson_interval(successes: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    phat = successes / n
    denom = 1 + z * z / n
    center = (phat + z * z / (2 * n)) / denom
    margin = (z / denom) * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n))
    return (center - margin, center + margin)


def record_correct(record: dict[str, Any]) -> bool:
    return record.get("status") == "success" and record.get("click_in_target_bbox") is True


def nfkc(text: str) -> str:
    return unicodedata.normalize("NFKC", normalize_text(text))


def cer_nfkc(gold: str, transcript: str) -> float:
    return character_error_rate(nfkc(gold), nfkc(transcript))


def main() -> None:
    stats_rows: list[dict[str, Any]] = []

    # A. Sign tests from the frozen transition counts.
    for row in load_csv(ROOT / "data" / "results" / "table4b_changed_unchanged_effects.csv"):
        wc, cw = int(row["WC"]), int(row["CW"])
        stats_rows.append(
            {
                "analysis": "sign_test",
                "grounding_model": row["grounding_model"],
                "asr_model": row["asr_model"],
                "correction_method": row["correction_method"],
                "subset": row["subset"],
                "n": row["n"],
                "WC": wc,
                "CW": cw,
                "click_delta": row["click_delta"],
                "sign_test_p_two_sided": sign_test_p(wc, cw),
            }
        )
    for row in load_csv(ROOT / "data" / "results" / "table4_correction_effects.csv"):
        wc, cw = int(row["WC"]), int(row["CW"])
        stats_rows.append(
            {
                "analysis": "sign_test",
                "grounding_model": row["grounding_model"],
                "asr_model": row["asr_model"],
                "correction_method": row["correction_method"],
                "subset": "pooled",
                "n": row["n_total"],
                "WC": wc,
                "CW": cw,
                "click_delta": row["pooled_click_delta"],
                "sign_test_p_two_sided": sign_test_p(wc, cw),
            }
        )

    # B. Wilson intervals for the six baseline rows.
    for row in load_csv(ROOT / "data" / "results" / "table3_grounding_degradation.csv"):
        if row["slice"] != "grounding_model+input_condition+asr_model":
            continue
        n = int(row["n_total"])
        acc = float(row["click_accuracy_including_failures"])
        successes = round(acc * n)
        low, high = wilson_interval(successes, n)
        stats_rows.append(
            {
                "analysis": "wilson_interval",
                "grounding_model": row["grounding_model"],
                "asr_model": row["asr_model"] or "",
                "correction_method": "",
                "subset": row["input_condition"],
                "n": n,
                "successes": successes,
                "click_accuracy": acc,
                "wilson_low": round(low, 6),
                "wilson_high": round(high, 6),
            }
        )

    # C. Per-command paired gold-vs-ASR comparison (clustered bootstrap).
    evaluations = load_jsonl(ROOT / "data" / "predictions" / "grounding_evaluation_by_file.jsonl")
    by_condition: dict[tuple[str, str], dict[str, list[bool]]] = defaultdict(lambda: defaultdict(list))
    for record in evaluations:
        key = (record["grounding_model"], record["input_condition"])
        by_condition[key][record["utterance_id"]].append(record_correct(record))
    rng = random.Random(BOOTSTRAP_SEED)
    for model in ("G1", "G2"):
        gold = by_condition[(model, "gold")]
        for condition in ("asr_whisper_large_v3_local", "asr_typhoon_asr_api"):
            asr = by_condition[(model, condition)]
            commands = sorted(set(gold) & set(asr))
            diffs = [
                (sum(asr[u]) / len(asr[u])) - (sum(gold[u]) / len(gold[u]))
                for u in commands
            ]
            mean_diff = sum(diffs) / len(diffs)
            boots = []
            for _ in range(BOOTSTRAP_ITERATIONS):
                sample = [diffs[rng.randrange(len(diffs))] for _ in diffs]
                boots.append(sum(sample) / len(sample))
            boots.sort()
            low = boots[int(0.025 * BOOTSTRAP_ITERATIONS)]
            high = boots[int(0.975 * BOOTSTRAP_ITERATIONS) - 1]
            stats_rows.append(
                {
                    "analysis": "paired_command_gold_vs_asr",
                    "grounding_model": model,
                    "asr_model": condition.removeprefix("asr_"),
                    "correction_method": "",
                    "subset": "per_command_paired",
                    "n": len(commands),
                    "mean_paired_diff": round(mean_diff, 6),
                    "bootstrap_low": round(low, 6),
                    "bootstrap_high": round(high, 6),
                    "bootstrap_seed": BOOTSTRAP_SEED,
                }
            )

    fields: list[str] = []
    for row in stats_rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with (ANALYSIS_DIR / "phase1_supplementary_stats.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(stats_rows)

    # D. Cosmetic versus substantive changes under NFKC.
    utterances = {row["utterance_id"]: row for row in load_jsonl(ROOT / "data" / "utterances" / "utterances_audited.jsonl")}
    corrections = load_jsonl(ROOT / "data" / "corrections" / "corrected_transcripts.jsonl")
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in corrections:
        if row.get("status") == "success":
            groups[(row["asr_model"], row["method"])].append(row)

    split_rows: list[dict[str, Any]] = []
    for (asr_model, method), group in sorted(groups.items()):
        n_total = len(group)
        changed = cosmetic = substantive = recovery_nfkc = false_nfkc = 0
        for row in group:
            utt = utterances[row["utterance_id"]]
            gold = str(utt.get("text_gold", ""))
            raw = str(row.get("input_transcript", ""))
            corrected = str(row.get("corrected_transcript", ""))
            is_changed = bool(row.get("changed"))
            if is_changed:
                changed += 1
                if nfkc(raw) == nfkc(corrected):
                    cosmetic += 1
                else:
                    substantive += 1
            raw_cer = cer_nfkc(gold, raw)
            corrected_cer = cer_nfkc(gold, corrected)
            loanwords = loanwords_for_utterance(utt)
            raw_loan = loanword_error_counts(loanwords, raw)[1]
            corrected_loan = loanword_error_counts(loanwords, corrected)[1]
            substantive_change = is_changed and nfkc(raw) != nfkc(corrected)
            if corrected_cer < raw_cer or corrected_loan < raw_loan:
                recovery_nfkc += 1
            if corrected_cer > raw_cer or (substantive_change and raw_cer == 0):
                false_nfkc += 1
        split_rows.append(
            {
                "asr_model": asr_model,
                "correction_method": method,
                "n_total": n_total,
                "changed_frozen": changed,
                "cosmetic_unicode_ws_only": cosmetic,
                "substantive_changes": substantive,
                "recovery_count_nfkc": recovery_nfkc,
                "recovery_rate_nfkc": round(recovery_nfkc / n_total, 6),
                "false_correction_count_nfkc": false_nfkc,
                "false_correction_rate_nfkc": round(false_nfkc / n_total, 6),
            }
        )

    with (ANALYSIS_DIR / "false_correction_cosmetic_split.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(split_rows[0].keys()))
        writer.writeheader()
        writer.writerows(split_rows)

    lines = [
        "# Phase 1 Supplementary Statistics (post-hoc)",
        "",
        "These diagnostics were computed 2026-07-19 from the frozen outputs after the",
        "primary results were fixed. They do not modify any frozen artifact and are",
        "reported as post-hoc reanalysis, not as primary metrics.",
        "",
        "## Sign tests (changed subsets)",
        "",
        "| Grounding | ASR | Method | n | WC | CW | delta | p |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in stats_rows:
        if row["analysis"] == "sign_test" and row["subset"] == "changed":
            p = row["sign_test_p_two_sided"]
            lines.append(
                f"| {row['grounding_model']} | {row['asr_model']} | {row['correction_method']} "
                f"| {row['n']} | {row['WC']} | {row['CW']} | {row['click_delta']} "
                f"| {'n/a' if p is None else format(p, '.4f')} |"
            )
    lines += [
        "",
        "## Sign tests (unchanged/no-op subsets)",
        "",
        "| Grounding | ASR | Method | n | WC | CW | delta | p |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in stats_rows:
        if row["analysis"] == "sign_test" and row["subset"] == "unchanged":
            p = row["sign_test_p_two_sided"]
            lines.append(
                f"| {row['grounding_model']} | {row['asr_model']} | {row['correction_method']} "
                f"| {row['n']} | {row['WC']} | {row['CW']} | {row['click_delta']} "
                f"| {'n/a' if p is None else format(p, '.4f')} |"
            )
    lines += [
        "",
        "## Baseline Wilson 95% intervals",
        "",
        "| Grounding | Condition | n | Accuracy | 95% interval |",
        "|---|---|---|---|---|",
    ]
    for row in stats_rows:
        if row["analysis"] == "wilson_interval":
            lines.append(
                f"| {row['grounding_model']} | {row['subset']} | {row['n']} "
                f"| {row['click_accuracy']:.4f} | [{row['wilson_low']:.4f}, {row['wilson_high']:.4f}] |"
            )
    lines += [
        "",
        "## Per-command paired gold-vs-ASR differences (clustered bootstrap)",
        "",
        f"Commands are the resampling unit; {BOOTSTRAP_ITERATIONS} draws, seed {BOOTSTRAP_SEED}.",
        "",
        "| Grounding | ASR | Commands | Mean paired diff | 95% bootstrap interval |",
        "|---|---|---|---|---|",
    ]
    for row in stats_rows:
        if row["analysis"] == "paired_command_gold_vs_asr":
            lines.append(
                f"| {row['grounding_model']} | {row['asr_model']} | {row['n']} "
                f"| {row['mean_paired_diff']:+.4f} | [{row['bootstrap_low']:+.4f}, {row['bootstrap_high']:+.4f}] |"
            )
    lines += [
        "",
        "## Cosmetic versus substantive transcript changes (NFKC)",
        "",
        "A change is cosmetic when the raw and corrected transcripts are identical",
        "after NFKC and whitespace normalization. Recovery and false correction are",
        "recomputed here under NFKC-normalized CER; the frozen Table 4 numbers remain",
        "the primary metrics.",
        "",
        "| ASR | Method | n | Changed | Cosmetic-only | Substantive | Recovery (NFKC) | False corr. (NFKC) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in split_rows:
        lines.append(
            f"| {row['asr_model']} | {row['correction_method']} | {row['n_total']} "
            f"| {row['changed_frozen']} | {row['cosmetic_unicode_ws_only']} | {row['substantive_changes']} "
            f"| {row['recovery_count_nfkc']} ({row['recovery_rate_nfkc']:.4f}) "
            f"| {row['false_correction_count_nfkc']} ({row['false_correction_rate_nfkc']:.4f}) |"
        )
    (ANALYSIS_DIR / "PHASE1_SUPPLEMENTARY_ANALYSIS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {len(stats_rows)} stats rows and {len(split_rows)} split rows.")


if __name__ == "__main__":
    main()
