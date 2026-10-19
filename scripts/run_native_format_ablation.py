"""Phase 2 (optional): UI-TARS native-format ablation on a subsample.

Queries UI-TARS-1.5-7B with its official GROUNDING prompt template
(bytedance/UI-TARS codes/ui_tars/prompt.py, accessed 2026-07-19) instead of
the benchmark's shared JSON protocol, on a 100-item G2/Whisper subsample:
every frozen parse-failure item plus a seeded random fill. Measures how much
of the shared-protocol parse-failure rate is format-induced.

Coordinates are treated as absolute original-image pixels, matching the
frozen protocol; screen images are within the Qwen2.5-VL pixel budget, so
smart-resize rounding (28px multiples) shifts coordinates by at most ~1-2%.

Outputs (new files only):
  data/predictions/phase2_native_ablation/native_predictions.jsonl
  data/analysis/phase2_native_format_ablation.csv
  data/analysis/PHASE2_NATIVE_FORMAT_ABLATION.md
"""

from __future__ import annotations

import csv
import json
import random
import re
import time
from pathlib import Path
from typing import Any

from run_grounding import (
    build_asr_examples,
    image_data_url,
    index_by,
    include_audio,
    load_json,
    load_jsonl,
    utc_now,
)
from evaluate_grounding import (
    normalized_bbox,
    point_in_bbox,
    point_in_image,
    screen_dimensions,
    target_element,
)

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "predictions" / "phase2_native_ablation"
OUT_JSONL = OUT_DIR / "native_predictions.jsonl"
OUT_CSV = ROOT / "data" / "analysis" / "phase2_native_format_ablation.csv"
OUT_MD = ROOT / "data" / "analysis" / "PHASE2_NATIVE_FORMAT_ABLATION.md"
SEED = 20260719
SAMPLE_SIZE = 100
CONDITION = "asr_whisper_large_v3_local"

NATIVE_TEMPLATE = (
    "You are a GUI agent. You are given a task and your action history, with screenshots. "
    "You need to perform the next action to complete the task.\n"
    "\n"
    "## Action Space\n"
    "\n"
    "click(point='<point>x1 y1</point>')\n"
    "\n"
    "## User Instruction\n"
    "{instruction}"
)

POINT_PATTERNS = (
    re.compile(
        r"<points?\s[^>]*x1\s*=\s*['\"](-?\d+(?:\.\d+)?)['\"]\s+y1\s*=\s*['\"](-?\d+(?:\.\d+)?)['\"]",
        re.IGNORECASE,
    ),
    re.compile(r"<point>\s*(-?\d+(?:\.\d+)?)[\s,]+(-?\d+(?:\.\d+)?)\s*</point>"),
    re.compile(r"point\s*=\s*['\"]?\(?\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)?", re.IGNORECASE),
    re.compile(r"start_box\s*=\s*['\"]?\(?\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)", re.IGNORECASE),
    re.compile(r"click\s*\(\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)", re.IGNORECASE),
)


def parse_native(text: str) -> tuple[float, float] | None:
    for pattern in POINT_PATTERNS:
        match = pattern.search(text)
        if match:
            return float(match.group(1)), float(match.group(2))
    return None


def main() -> None:
    config = load_json(ROOT / "configs" / "grounding_phase2_rerun.yaml")
    model_config = config["models"]["G2"]

    screens = load_jsonl(ROOT / "data" / "screens" / "screens.jsonl", "screens")
    utterances = load_jsonl(ROOT / "data" / "utterances" / "utterances_audited.jsonl", "utterances")
    manifest = load_jsonl(ROOT / "data" / "audio" / "audio_manifest.jsonl", "audio manifest")
    screens_by_id = index_by(screens, "screen_id")
    utterances_by_id = index_by(utterances, "utterance_id")
    valid_audio_by_id = {
        str(r["audio_id"]): r for r in manifest if isinstance(r.get("audio_id"), str) and include_audio(r)
    }
    examples = build_asr_examples(
        "G2",
        CONDITION,
        ROOT / "data" / "asr_outputs" / "whisper_large_v3_local.jsonl",
        utterances_by_id,
        screens_by_id,
        valid_audio_by_id,
    )
    examples_by_id = {e.prediction_id: e for e in examples}

    frozen = [
        r
        for r in load_jsonl(ROOT / "data" / "predictions" / "grounding_predictions.jsonl", "frozen predictions")
        if r.get("grounding_model") == "G2" and r.get("input_condition") == CONDITION
    ]
    frozen_by_id = {r["prediction_id"]: r for r in frozen}
    failure_ids = sorted(r["prediction_id"] for r in frozen if r.get("status") != "success")
    other_ids = sorted(pid for pid in frozen_by_id if pid not in set(failure_ids))
    rng = random.Random(SEED)
    fill = rng.sample(other_ids, max(0, SAMPLE_SIZE - len(failure_ids)))
    sample_ids = failure_ids + fill

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    done_ids: set[str] = set()
    if OUT_JSONL.exists():
        for line in OUT_JSONL.read_text(encoding="utf-8").splitlines():
            if line.strip():
                done_ids.add(json.loads(line)["prediction_id"])

    from openai import OpenAI

    client = OpenAI(api_key="local-no-key", base_url=model_config["base_url"], timeout=120, max_retries=2)

    for pid in sample_ids:
        if pid in done_ids:
            continue
        example = examples_by_id[pid]
        screen = example.screen or screens_by_id[example.screen_id]
        prompt = NATIVE_TEMPLATE.format(instruction=example.transcript)
        image_path = ROOT / str(screen.get("image_path", ""))
        started = time.perf_counter()
        record: dict[str, Any] = {
            "prediction_id": pid,
            "utterance_id": example.utterance_id,
            "audio_id": example.audio_id,
            "screen_id": example.screen_id,
            "target_element_id": example.target_element_id,
            "input_condition": CONDITION,
            "grounding_model": "G2_native_format",
            "asr_model": example.asr_model,
            "transcript": example.transcript,
            "created_at": utc_now(),
            "params": {"prompt_style": "ui_tars_native_grounding", "seed_sample": SEED},
        }
        try:
            response = client.chat.completions.create(
                model=model_config["model_name"],
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": image_data_url(image_path)}},
                        ],
                    }
                ],
            )
            output_text = response.choices[0].message.content or ""
            record["raw_output_text"] = output_text
            point = parse_native(output_text)
            if point is None:
                record["status"] = "failed"
                record["error_message"] = "could not parse native click point"
                record["pred_x"] = record["pred_y"] = None
            else:
                record["status"] = "success"
                record["pred_x"], record["pred_y"] = point
                record["error_message"] = None
        except Exception as exc:  # noqa: BLE001
            record["status"] = "failed"
            record["error_message"] = str(exc)
            record["raw_output_text"] = ""
            record["pred_x"] = record["pred_y"] = None
        record["latency_ms"] = round((time.perf_counter() - started) * 1000, 1)
        with OUT_JSONL.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    # Evaluate both protocols on the sample.
    native_by_id = {}
    for line in OUT_JSONL.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            native_by_id[r["prediction_id"]] = r

    def correct(record: dict[str, Any], screen: dict[str, Any]) -> tuple[bool, bool]:
        ok = record.get("status") == "success" and record.get("pred_x") is not None
        if not ok:
            return False, False
        x, y = float(record["pred_x"]), float(record["pred_y"])
        width, height = screen_dimensions(screen)
        element = target_element(screen, str(record.get("target_element_id", "")))
        bbox = element.get("bbox") if element else None
        hit = bbox is not None and point_in_bbox(x, y, normalized_bbox(bbox))
        return True, hit and point_in_image(x, y, width, height)

    rows = []
    for subset_name, ids in (
        ("frozen_parse_failures", failure_ids),
        ("random_fill", fill),
        ("all_sampled", sample_ids),
    ):
        n = len(ids)
        frozen_parse = frozen_correct = native_parse = native_correct = 0
        for pid in ids:
            screen = screens_by_id[frozen_by_id[pid]["screen_id"]]
            fp, fc = correct(frozen_by_id[pid], screen)
            np_, nc = correct(native_by_id[pid], screen)
            frozen_parse += fp
            frozen_correct += fc
            native_parse += np_
            native_correct += nc
        rows.append(
            {
                "subset": subset_name,
                "n": n,
                "frozen_parse_ok": frozen_parse,
                "frozen_click_correct": frozen_correct,
                "native_parse_ok": native_parse,
                "native_click_correct": native_correct,
            }
        )

    with OUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# Phase 2: UI-TARS Native-Format Ablation (post-hoc, subsample)",
        "",
        "Official UI-TARS GROUNDING template versus the benchmark's shared JSON",
        f"protocol, on {len(sample_ids)} G2/Whisper items: all {len(failure_ids)} frozen",
        f"parse failures plus {len(fill)} seeded random items (seed {SEED}).",
        "Native run performed 2026-07-19 on the same vLLM serving stack; frozen",
        "artifacts unmodified. Coordinates treated as absolute pixels in both",
        "protocols. This is a diagnostic bound, not a benchmark result.",
        "",
        "| Subset | n | Frozen parse-ok | Frozen correct | Native parse-ok | Native correct |",
        "|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['subset']} | {row['n']} | {row['frozen_parse_ok']} | {row['frozen_click_correct']} "
            f"| {row['native_parse_ok']} | {row['native_click_correct']} |"
        )
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    for row in rows:
        print(row)


if __name__ == "__main__":
    main()
