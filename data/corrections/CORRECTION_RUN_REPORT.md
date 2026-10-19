# Correction Run Report

Run date: `2026-07-19`

This is the final fixed-rule Step 14 correction run on the restored original 20-screen dataset.

## Frozen Inputs

| File | SHA-256 |
| --- | --- |
| `data/corrections/frozen_correction_config.yaml` | `A9197BB6074C56D6B8EA2CBE632CE90C8464198436C20C0678A9C7286CB48B52` |
| `data/corrections/frozen_aliases.yaml` | `2B821E1FF706380486336E748A066240B2D867CD133E2B80EA396172AD5AB53A` |

The active dataset was confirmed to contain exactly `20` screens before this run.

## Inputs

| Input | Path |
| --- | --- |
| Correction config | `configs/correction.yaml` |
| Alias table | `data/corrections/aliases/ui_aliases_th_en.yaml` |
| Screens | `data/screens/screens.jsonl` |
| Utterances | `data/utterances/utterances_audited.jsonl` |
| Audio manifest | `data/audio/audio_manifest.jsonl` |
| Whisper ASR | `data/asr_outputs/whisper_large_v3_local.jsonl` |
| Typhoon ASR | `data/asr_outputs/typhoon_asr_api.jsonl` |

## Output

`data/corrections/corrected_transcripts.jsonl`

## Processing Summary

| Metric | Count |
| --- | ---: |
| Candidate ASR records | 942 |
| Selected ASR records | 942 |
| Correction methods | 3 |
| Correction output records | 2,826 |
| Successful correction records | 2,826 |
| Failed correction records | 0 |
| Changed records | 310 |

## ASR Records By Model

| ASR model | ASR records | Correction records |
| --- | ---: | ---: |
| `whisper_large_v3_local` | 471 | 1,413 |
| `typhoon_asr_api` | 471 | 1,413 |

## Records By Correction Method

| Method | Records | Changed | Changed rate |
| --- | ---: | ---: | ---: |
| `A_no_screen_cleanup` | 942 | 72 | 0.076433 |
| `B_screen_string_match` | 942 | 72 | 0.076433 |
| `C_full_screen_aware_alias` | 942 | 166 | 0.176221 |

## Changed Rate By Tier

| Tier | Records | Changed | Changed rate |
| --- | ---: | ---: | ---: |
| `T1_verbatim` | 666 | 127 | 0.190691 |
| `T2_paraphrase` | 720 | 113 | 0.156944 |
| `T3_intent` | 720 | 48 | 0.066667 |
| `T4_visual_positional` | 720 | 22 | 0.030556 |

## Validation

```powershell
.\.venv\Scripts\python.exe scripts/validate_corrections.py --corrections data/corrections/corrected_transcripts.jsonl --schema schemas/correction_output.schema.json --screens data/screens/screens.jsonl --utterances data/utterances/utterances_audited.jsonl --manifest data/audio/audio_manifest.jsonl
```

Validation result: passed for `2,826` records.

## Notes

- Thresholds, aliases, prompts, model versions, and n-best settings were not tuned for this run.
- Screens, utterances, TTS, ASR, and baseline grounding files were not modified.
- Grounding was not run as part of this correction step.
