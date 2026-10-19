# Correction Freeze Note

Frozen at: `2026-07-19`

This note freezes the Step 14 fixed-rule transcript correction method before the final correction run on the restored 20-screen dataset.

## Dataset State

- Active screens: `20`
- Screens per domain: `5` each for `mock_finance`, `shopping`, `settings`, and `messaging`
- Expansion screen IDs `*_006` through `*_010`: absent from the active screen dataset
- ASR inputs:
  - `data/asr_outputs/whisper_large_v3_local.jsonl`
  - `data/asr_outputs/typhoon_asr_api.jsonl`

## Frozen Files

| File | SHA-256 |
| --- | --- |
| `data/corrections/frozen_correction_config.yaml` | `A9197BB6074C56D6B8EA2CBE632CE90C8464198436C20C0678A9C7286CB48B52` |
| `data/corrections/frozen_aliases.yaml` | `2B821E1FF706380486336E748A066240B2D867CD133E2B80EA396172AD5AB53A` |

The frozen files are exact copies of:

- `configs/correction.yaml`
- `data/corrections/aliases/ui_aliases_th_en.yaml`

## Frozen Methods

- `A_no_screen_cleanup`
- `B_screen_string_match`
- `C_full_screen_aware_alias`

## Guardrails

- Do not tune thresholds after this freeze.
- Do not change prompts, aliases, model versions, or n-best size after this freeze.
- Do not use target element IDs, target bboxes, gold transcripts, grounding predictions, or grounding evaluation results for correction.
- Do not modify screens, utterances, TTS, ASR, or baseline grounding.
- Correction must use only the ASR transcript, `screen_id`, visible screen lexicon, and the frozen alias table.
