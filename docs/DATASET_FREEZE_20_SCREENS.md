# ThaiVoice-GUIBench 20-Screen Dataset Freeze

Generated: 2026-07-19

## Scope

The active dataset has been reverted to the original 20-screen baseline and is frozen for fixed-rule correction experiments. Do not add screens, mappings, utterances, audio, ASR outputs, grounding predictions, or correction outputs while tuning-free correction preparation is in progress.

`docs/PROJECT_CONTEXT.md` is absent in this workspace. The equivalent project context file is `docs/PROJECT_CONTXT.md`.

## Active Dataset Inventory

| Artifact | Active count |
| --- | ---: |
| Screens | 20 |
| Intents | 30 |
| Intent-screen mappings | 32 |
| Mapped screens | 20 |
| Audited utterances | 128 |
| Audio manifest rows | 480 |
| Valid audio rows | 471 |
| Excluded audio rows | 9 |
| Whisper ASR rows | 471 |
| Typhoon ASR rows | 471 |

## Screens By Domain

| Domain | Screens |
| --- | ---: |
| messaging | 5 |
| mock_finance | 5 |
| settings | 5 |
| shopping | 5 |

All 20 referenced screenshot images exist. No active `*_006` through `*_010` screen IDs or screen PNGs are present.

## Utterances By Tier

| Tier | Utterances |
| --- | ---: |
| T1_verbatim | 32 |
| T2_paraphrase | 32 |
| T3_intent | 32 |
| T4_visual_positional | 32 |

## Audio State

| Field | Count |
| --- | ---: |
| Manifest rows | 480 |
| `include_in_experiments=true` | 471 |
| `include_in_experiments=false` | 9 |
| Present audio files | 480 |

The active manifest contains the original legacy rows. The temporary expansion/all-voice rows were archived and removed from the active manifest.

## ASR Outputs

| Model | Success | Failed |
| --- | ---: | ---: |
| whisper_large_v3_local | 471 | 0 |
| typhoon_asr_api | 471 | 0 |

## Grounding Predictions

| Model | Condition | Success | Failed |
| --- | --- | ---: | ---: |
| G1 | gold | 128 | 0 |
| G1 | asr_whisper_large_v3_local | 471 | 0 |
| G1 | asr_typhoon_asr_api | 471 | 0 |
| G2 | gold | 119 | 9 |
| G2 | asr_whisper_large_v3_local | 437 | 34 |
| G2 | asr_typhoon_asr_api | 442 | 29 |

No active grounding prediction rows reference expansion screens.

## Expansion Artifacts

The 40-screen expansion artifacts are not used by the active dataset. They were archived under:

`data/archive/rollback_40_to_20_20260719_030645/`

Active expansion-specific audit and planning files are absent:

- `docs/DATASET_EXPANSION_PLAN_40_SCREENS.md`
- `data/utterances/audit/native_audit_expansion_40.csv`
- `data/utterances/audit/native_audit_expansion_40_summary.md`
- `data/audio/audit/tts_fidelity_expansion_40.csv`
- `data/audio/audit/tts_fidelity_expansion_40_summary.md`

## Validation Results

The following checks passed on the active 20-screen dataset:

```powershell
.\.venv\Scripts\python.exe scripts/validate_screens.py --screens-jsonl data/screens/screens.jsonl --image-root .
.\.venv\Scripts\python.exe scripts/validate_intents.py --intents data/intents/intents.jsonl --mappings data/intents/intent_screen_targets.jsonl --screens data/screens/screens.jsonl
.\.venv\Scripts\python.exe scripts/validate_utterances.py --utterances data/utterances/utterances_audited.jsonl --mappings data/intents/intent_screen_targets.jsonl --screens data/screens/screens.jsonl --schema schemas/utterance.schema.json
.\.venv\Scripts\python.exe scripts/validate_audio_manifest.py
.\.venv\Scripts\python.exe scripts/validate_asr_outputs.py --model whisper_large_v3_local --outputs data/asr_outputs/whisper_large_v3_local.jsonl --manifest data/audio/audio_manifest.jsonl --utterances data/utterances/utterances_audited.jsonl --schema schemas/asr_output.schema.json
.\.venv\Scripts\python.exe scripts/validate_asr_outputs.py --model typhoon_asr_api --outputs data/asr_outputs/typhoon_asr_api.jsonl --manifest data/audio/audio_manifest.jsonl --utterances data/utterances/utterances_audited.jsonl --schema schemas/asr_output.schema.json
.\.venv\Scripts\python.exe scripts/validate_grounding_predictions.py --predictions data/predictions/grounding_predictions.jsonl --screens data/screens/screens.jsonl --utterances data/utterances/utterances_audited.jsonl --manifest data/audio/audio_manifest.jsonl --schema schemas/grounding_prediction.schema.json
```

## Correction Experiment Guardrails

- Use this frozen 20-screen active dataset for fixed-rule correction experiments.
- Do not run correction yet.
- Do not tune thresholds yet.
- When correction is implemented, tune thresholds only on the dev split and keep test results untouched until final evaluation.
