"""Phase 2: run-to-run reproducibility of UI-TARS under the frozen protocol.

Compares the frozen G2 raw-condition predictions against an identical-prompt
rerun (same code path, same prompts, same serving stack, no sampling changes).
The frozen artifacts are read-only inputs; the rerun lives under
data/predictions/phase2_rerun_g2/.

Outputs (new files):
  data/analysis/phase2_g2_rerun_reproducibility.csv
  data/analysis/PHASE2_G2_RERUN_REPORT.md
"""

from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

from evaluate_grounding import normalized_bbox, point_in_bbox, screen_dimensions, point_in_image, target_element

ROOT = Path(__file__).resolve().parent.parent
FROZEN = ROOT / "data" / "predictions" / "grounding_predictions.jsonl"
RERUN = ROOT / "data" / "predictions" / "phase2_rerun_g2" / "grounding_predictions_rerun.jsonl"
SCREENS = ROOT / "data" / "screens" / "screens.jsonl"
OUT_CSV = ROOT / "data" / "analysis" / "phase2_g2_rerun_reproducibility.csv"
OUT_MD = ROOT / "data" / "analysis" / "PHASE2_G2_RERUN_REPORT.md"

RAW_CONDITIONS = ("gold", "asr_whisper_large_v3_local", "asr_typhoon_asr_api")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def sign_test_p(b: int, c: int) -> float | None:
    n = b + c
    if n == 0:
        return None
    k = max(b, c)
    tail = sum(math.comb(n, i) for i in range(k, n + 1)) / (2 ** n)
    return min(1.0, 2.0 * tail)


def classify(record: dict[str, Any], screens: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Correctness under the frozen evaluation rules."""
    screen = screens[record["screen_id"]]
    ok_parse = record.get("status") == "success" and record.get("pred_x") is not None and record.get("pred_y") is not None
    correct = in_image = False
    if ok_parse:
        x, y = float(record["pred_x"]), float(record["pred_y"])
        width, height = screen_dimensions(screen)
        in_image = point_in_image(x, y, width, height)
        element = target_element(screen, str(record.get("target_element_id", "")))
        bbox = element.get("bbox") if element else None
        if bbox is not None:
            correct = point_in_bbox(x, y, normalized_bbox(bbox))
    return {
        "parse_ok": ok_parse,
        "in_image": in_image,
        "correct": correct,
        "coords": (record.get("pred_x"), record.get("pred_y")) if ok_parse else None,
    }


def main() -> None:
    screens = {row["screen_id"]: row for row in load_jsonl(SCREENS)}
    frozen = {
        r["prediction_id"]: r
        for r in load_jsonl(FROZEN)
        if r.get("grounding_model") == "G2" and r.get("input_condition") in RAW_CONDITIONS
    }
    rerun = {
        r["prediction_id"]: r
        for r in load_jsonl(RERUN)
        if r.get("grounding_model") == "G2" and r.get("input_condition") in RAW_CONDITIONS
    }

    rows = []
    for condition in RAW_CONDITIONS:
        ids = sorted(pid for pid, r in frozen.items() if r["input_condition"] == condition and pid in rerun)
        n = len(ids)
        same_coord = flips_wc = flips_cw = both_correct = both_wrong = 0
        parse_changes = 0
        acc1 = acc2 = 0
        for pid in ids:
            a = classify(frozen[pid], screens)
            b = classify(rerun[pid], screens)
            acc1 += a["correct"]
            acc2 += b["correct"]
            if a["parse_ok"] != b["parse_ok"]:
                parse_changes += 1
            if a["coords"] is not None and a["coords"] == b["coords"]:
                same_coord += 1
            if a["correct"] and b["correct"]:
                both_correct += 1
            elif a["correct"] and not b["correct"]:
                flips_cw += 1
            elif not a["correct"] and b["correct"]:
                flips_wc += 1
            else:
                both_wrong += 1
        p = sign_test_p(flips_wc, flips_cw)
        rows.append(
            {
                "condition": condition,
                "n_paired": n,
                "frozen_accuracy": round(acc1 / n, 6) if n else None,
                "rerun_accuracy": round(acc2 / n, 6) if n else None,
                "accuracy_delta": round((acc2 - acc1) / n, 6) if n else None,
                "exact_same_coordinate": same_coord,
                "parse_status_changes": parse_changes,
                "CC": both_correct,
                "WC": flips_wc,
                "CW": flips_cw,
                "WW": both_wrong,
                "flip_rate": round((flips_wc + flips_cw) / n, 6) if n else None,
                "sign_test_p_two_sided": None if p is None else round(p, 6),
            }
        )

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# Phase 2: UI-TARS Run-to-Run Reproducibility (identical prompts)",
        "",
        "The frozen raw-condition G2 predictions were rerun with the same code path,",
        "prompts, serving stack (vLLM, UI-TARS-1.5-7B, bfloat16), and request",
        "parameters (no explicit temperature or seed, matching the frozen protocol).",
        "Frozen artifacts were not modified; the rerun is stored separately under",
        "`data/predictions/phase2_rerun_g2/`.",
        "",
        "| Condition | n | Frozen acc | Rerun acc | Delta | Same coord | WC | CW | Flip rate | p |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        p = row["sign_test_p_two_sided"]
        lines.append(
            f"| {row['condition']} | {row['n_paired']} | {row['frozen_accuracy']:.4f} "
            f"| {row['rerun_accuracy']:.4f} | {row['accuracy_delta']:+.4f} "
            f"| {row['exact_same_coordinate']}/{row['n_paired']} | {row['WC']} | {row['CW']} "
            f"| {row['flip_rate']:.4f} | {'n/a' if p is None else format(p, '.4f')} |"
        )
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {OUT_CSV.name} and {OUT_MD.name}")
    for row in rows:
        print(row)


if __name__ == "__main__":
    main()
