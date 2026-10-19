# TTS Fidelity Audit

This audit screens synthesized audio quality for code-switched Thai commands before final experiments.

## Sample

- requested_sample_size: 100
- candidate_code_switched_audio_items: 70
- selected_audio_items: 70
- seed: 42
- sampling_policy: audit_all_available

## Counts By Voice

- azure/voice_01: 18
- azure/voice_02: 16
- openai/voice_01: 18
- openai/voice_02: 18

## Counts By Split

- dev: 6
- test: 64

## Scoring Rubric

Use 1-5 scores for `thai_intelligibility`, `english_loanword_fidelity`, `code_switch_fidelity`, and `overall_naturalness`.

- 5: excellent; clean enough for final benchmark use.
- 4: good; minor issue but acceptable.
- 3: usable but should be reviewed.
- 2: poor; likely exclude or regenerate.
- 1: unusable.

Mark `exclude_voice_candidate=true` if a voice repeatedly scores low, especially when average overall naturalness is below 3 or loanword/code-switch fidelity is below 3.

## Audit Dimensions

- `thai_intelligibility`: Thai words are understandable without reading the transcript.
- `english_loanword_fidelity`: English label or loanword sounds recognizable, such as `Transfer`, `Search`, or `Cart`.
- `code_switch_fidelity`: transition between Thai and English sounds natural and not garbled.
- `overall_naturalness`: voice sounds acceptable for benchmark use.
