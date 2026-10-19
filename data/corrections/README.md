# Correction Outputs

This directory is reserved for Step 14 fixed-rule transcript correction experiments.

The correction configuration is frozen before final evaluation in:

`configs/correction.yaml`

The UI alias table is:

`data/corrections/aliases/ui_aliases_th_en.yaml`

## Methods

| Method | Description |
| --- | --- |
| `A_no_screen_cleanup` | Transcript-only cleanup. It does not use screenshots, visible labels, aliases, target IDs, or bboxes. |
| `B_screen_string_match` | Uses only the visible screen lexicon for high-confidence string matching. |
| `C_full_screen_aware_alias` | Uses the visible screen lexicon plus the fixed Thai/English alias table and conservative phonetic-style matching. |

## Fixed Rules

- Thresholds are fixed in `configs/correction.yaml`.
- Do not tune thresholds on test results.
- Do not run correction before the declared configuration is reviewed.
- Correction may use only ASR transcript, `screen_id`, visible screen lexicon, and the alias table.
- Correction must not use `target_element_id`, target bbox, gold transcript, grounding predictions, or grounding evaluation results.
- T3/T4 label injection is disabled. A visible label may only be restored when the ASR transcript already contains a clear matching surface form.
- Prefer preserving the original ASR transcript over making a risky correction.
- Every changed span must include an explainable reason and score in the correction output record.

## Expected Output Files

Future correction runs should write method-specific JSONL outputs, for example:

- `data/corrections/A_no_screen_cleanup.jsonl`
- `data/corrections/B_screen_string_match.jsonl`
- `data/corrections/C_full_screen_aware_alias.jsonl`

No correction has been run as part of creating this README.
