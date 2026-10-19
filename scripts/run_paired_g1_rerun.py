"""Phase 2b: paired raw-vs-corrected GPT-5.5 grounding on changed subsets.

For every changed transcript in the four non-empty changed subsets
(Whisper A/B/C, Typhoon C; 310 items, 620 calls), submits BOTH the raw ASR
transcript and the corrected transcript to GPT-5.5 in one session with
temperature 0 (if the API accepts it) and the snapshot pinned to
gpt-5.5-2026-04-23. Within a pair, only the transcript differs, giving the
closest feasible causal estimate of correction's click effect.

Frozen artifacts are read-only inputs. Outputs (new files only):
  data/predictions/phase2b_paired_g1/paired_predictions.jsonl
  data/predictions/phase2b_paired_g1/raw/<call_id>.json

Fail-fast: aborts immediately on authentication/quota errors and after five
consecutive API failures so a dead key cannot burn the batch.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from run_grounding import (
    GroundingExample,
    build_prompt,
    image_data_url,
    index_by,
    load_jsonl,
    parse_model_json,
    utc_now,
)

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "predictions" / "phase2b_paired_g1"
OUT_JSONL = OUT_DIR / "paired_predictions.jsonl"
RAW_DIR = OUT_DIR / "raw"
MODEL_SNAPSHOT = "gpt-5.5-2026-04-23"

SUBSETS = (
    ("whisper_large_v3_local", "A_no_screen_cleanup"),
    ("whisper_large_v3_local", "B_screen_string_match"),
    ("whisper_large_v3_local", "C_full_screen_aware_alias"),
    ("typhoon_asr_api", "C_full_screen_aware_alias"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, help="limit number of PAIRS (for smoke test)")
    parser.add_argument(
        "--c-only",
        action="store_true",
        help="run only the two method-C changed subsets (Whisper C, Typhoon C)",
    )
    return parser.parse_args()


def extract_xy(parsed: dict[str, Any]) -> tuple[float, float] | None:
    x, y = parsed.get("pred_x"), parsed.get("pred_y")
    try:
        return float(x), float(y)
    except (TypeError, ValueError):
        return None


def main() -> int:
    args = parse_args()
    import os

    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is not set in the environment")
    from openai import OpenAI

    client = OpenAI(timeout=120, max_retries=2)

    screens_by_id = index_by(load_jsonl(ROOT / "data" / "screens" / "screens.jsonl", "screens"), "screen_id")
    utterances_by_id = index_by(
        load_jsonl(ROOT / "data" / "utterances" / "utterances_audited.jsonl", "utterances"), "utterance_id"
    )
    corrections = load_jsonl(ROOT / "data" / "corrections" / "corrected_transcripts.jsonl", "corrections")

    subsets = tuple(s for s in SUBSETS if not args.c_only or s[1].startswith("C_"))
    pairs: list[dict[str, Any]] = []
    for asr_model, method in subsets:
        rows = [
            r
            for r in corrections
            if r.get("status") == "success"
            and r.get("asr_model") == asr_model
            and r.get("method") == method
            and r.get("changed") is True
        ]
        rows.sort(key=lambda r: (str(r.get("utterance_id")), str(r.get("audio_id"))))
        for r in rows:
            pairs.append(r)
    if args.limit is not None:
        pairs = pairs[: args.limit]
    print(f"selected_pairs={len(pairs)} (calls={2 * len(pairs)})")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    done: set[str] = set()
    if OUT_JSONL.exists():
        for line in OUT_JSONL.read_text(encoding="utf-8").splitlines():
            if line.strip():
                done.add(json.loads(line)["call_id"])

    temperature_supported: bool | None = None
    consecutive_failures = 0
    processed = 0

    for row in pairs:
        utt = utterances_by_id[row["utterance_id"]]
        screen = screens_by_id[row["screen_id"]]
        image_path = ROOT / str(screen.get("image_path", ""))
        for variant, transcript in (
            ("raw", str(row.get("input_transcript", ""))),
            ("corrected", str(row.get("corrected_transcript", ""))),
        ):
            call_id = f"{row['asr_model']}__{row['method']}__{row['audio_id']}__{variant}"
            if call_id in done:
                continue
            example = GroundingExample(
                prediction_id=call_id,
                utterance_id=str(row["utterance_id"]),
                audio_id=str(row.get("audio_id")),
                screen_id=str(row["screen_id"]),
                target_element_id=str(utt.get("target_element_id", "")),
                input_condition=f"paired_{variant}",
                asr_model=str(row["asr_model"]),
                transcript_source=variant,
                transcript=transcript,
                screen=screen,
            )
            prompt = build_prompt(example, screen)
            record: dict[str, Any] = {
                "call_id": call_id,
                "pair_id": f"{row['asr_model']}__{row['method']}__{row['audio_id']}",
                "variant": variant,
                "asr_model": row["asr_model"],
                "correction_method": row["method"],
                "utterance_id": row["utterance_id"],
                "audio_id": row.get("audio_id"),
                "screen_id": row["screen_id"],
                "target_element_id": example.target_element_id,
                "transcript": transcript,
                "model": MODEL_SNAPSHOT,
                "created_at": utc_now(),
            }
            request: dict[str, Any] = {
                "model": MODEL_SNAPSHOT,
                "text": {"format": {"type": "json_object"}},
                "input": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": prompt},
                            {"type": "input_image", "image_url": image_data_url(image_path)},
                        ],
                    }
                ],
            }
            try:
                if temperature_supported in (None, True):
                    try:
                        response = client.responses.create(**request, temperature=0)
                        temperature_supported = True
                        record["temperature"] = 0
                    except Exception as exc:  # noqa: BLE001
                        message = str(exc).lower()
                        if temperature_supported is None and "temperature" in message and (
                            "unsupported" in message or "not supported" in message or "does not support" in message
                        ):
                            temperature_supported = False
                            print("NOTE: temperature rejected by API; continuing without it")
                            response = client.responses.create(**request)
                            record["temperature"] = None
                        else:
                            raise
                else:
                    response = client.responses.create(**request)
                    record["temperature"] = None
                raw_json = response.model_dump_json(indent=2)
                (RAW_DIR / f"{call_id}.json").write_text(raw_json, encoding="utf-8")
                output_text = getattr(response, "output_text", "") or ""
                record["output_text"] = output_text
                record["response_id"] = getattr(response, "id", None)
                record["response_model"] = getattr(response, "model", None)
                try:
                    parsed = parse_model_json(output_text)
                    xy = extract_xy(parsed)
                except Exception:  # noqa: BLE001
                    xy = None
                    parsed = {}
                if xy is None:
                    record["status"] = "failed"
                    record["error_message"] = "unparseable_model_output"
                    record["pred_x"] = record["pred_y"] = None
                else:
                    record["status"] = "success"
                    record["error_message"] = None
                    record["pred_x"], record["pred_y"] = xy
                    record["pred_label"] = str(parsed.get("pred_label") or "")
                consecutive_failures = 0
            except Exception as exc:  # noqa: BLE001
                message = str(exc)
                lowered = message.lower()
                if "insufficient_quota" in lowered or "invalid_api_key" in lowered or "401" in lowered:
                    print(f"FATAL billing/auth error, aborting: {message[:200]}")
                    return 1
                record["status"] = "failed"
                record["error_message"] = message[:500]
                record["pred_x"] = record["pred_y"] = None
                consecutive_failures += 1
                if consecutive_failures >= 5:
                    with OUT_JSONL.open("a", encoding="utf-8") as handle:
                        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                    print("FATAL: five consecutive API failures, aborting")
                    return 1
                time.sleep(2)
            with OUT_JSONL.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            processed += 1
            if processed % 25 == 0:
                print(f"processed={processed}")
    print(f"DONE processed={processed} temperature_supported={temperature_supported}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
