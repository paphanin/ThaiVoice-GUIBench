# Phase 2: UI-TARS Native-Format Ablation (post-hoc, subsample)

Official UI-TARS GROUNDING template versus the benchmark's shared JSON
protocol, on 100 G2/Whisper items: all 34 frozen
parse failures plus 66 seeded random items (seed 20260719).
Native run performed 2026-07-19 on the same vLLM serving stack; frozen
artifacts unmodified. Coordinates treated as absolute pixels in both
protocols. This is a diagnostic bound, not a benchmark result.

| Subset | n | Frozen parse-ok | Frozen correct | Native parse-ok | Native correct |
|---|---|---|---|---|---|
| frozen_parse_failures | 34 | 0 | 0 | 23 | 14 |
| random_fill | 66 | 66 | 30 | 45 | 21 |
| all_sampled | 100 | 66 | 30 | 68 | 35 |
