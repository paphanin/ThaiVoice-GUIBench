# Paper status

Revision: 2026-10-19. Supersedes all prior generic-template status notes.

## Manuscript and scope

Required reviewer reporting revisions only, based on frozen results. No new model calls, controlled reruns, human reference study, sensitivity tests, or comprehensive loanword audit. IEEEtran conference/US Letter defaults, 10-point Times-compatible body, IEEE bibliography, six pages including references. The requested ISBN/fee/copyright notice appears once on page 1; publication-ID space is reserved in both columns. All fonts are embedded, with no Type 3 font or font substitution. The per-tier figure is full text width; the pipeline diagram is preserved in the release. The class's standard reference trigger balances the last page. No custom margins, reference font compression, or global float-spacing overrides remain. Anonymous Authors is retained because replacement metadata was not supplied.

## Revised interpretation

- Correction differences are exploratory associations from independent runs, not causal estimates. GPT-5.5/Typhoon/C has WC=0/CW=6 from three commands, unadjusted post-hoc p=0.03125, with repeated-rendition and multiple-comparison caveats. No significance claim remains in the abstract or conclusion.
- No detectable gold-versus-ASR difference does not establish equivalence, robustness, adequate power, or a model ceiling. All six baseline rows include T1--T4 scores; GPT-5.5 gold T4 is 62.50 percent, versus 58.33--59.17 percent under raw ASR.
- One Thai-speaking author reviewed all 128 commands, with 20 edits. Human checks are separated from heuristic score prefilling and leakage validation. No independent human reference clicks/agreement by tier are available.
- One unblinded reviewer coded 140 purposively selected cases. No inter-reviewer agreement, between-reviewer dispute resolution, or benchmark-wide ambiguity prevalence is claimed.
- T1-only code-switching appears in the abstract and conclusion. Cosmetic changes and literal/normalized metrics are distinguished; transliteration equivalence remains unverified.
- Provider weighting, native-probe selection/subgroup counts, exact prompts, and historical serving gaps are disclosed. The selected native probe does not establish fairness.

## Reproducibility and verification

Release permalink: https://github.com/paphanin/ThaiVoice-GUIBench/releases/tag/v1.0.0

The release asset includes the frozen benchmark and all 480 WAV files with exclusions flagged, original predictions/raw responses, existing reruns/probe, review records, exact prompts, configurations/aliases, schemas, code/tests, manuscript, and checksums. The publication workflow separately checks the public permalink and downloaded asset hash. See `docs/REPRODUCIBILITY.md`. No IEEE PDF eXpress certification or venue submission is claimed.

- pytest verification includes release integrity, path exclusion, corruption rejection, and literal-LF JSONL handling for Unicode separators inside transcripts; the final test log is retained in the workspace.
- Ten applicable validators pass, including actual audio files, both ASR models, corrections, primary grounding, and the saved UI-TARS rerun.
- All aggregate and 24 tier baseline scores, consolidated correction metrics/deltas, and preserved changed/unchanged numeric rows match frozen sources.
- SHA-256 checks of 9,561 pre-existing data/config/schema/script/test/figure files show zero modified and zero missing.
- All six PDF pages were rendered and inspected. No clipping, overlap, overfull boxes, unresolved citations/references, or substituted fonts. Minor underfull warnings are visually acceptable.
