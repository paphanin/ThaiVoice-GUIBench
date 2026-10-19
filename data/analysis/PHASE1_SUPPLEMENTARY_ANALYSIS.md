# Phase 1 Supplementary Statistics (post-hoc)

These diagnostics were computed 2026-07-19 from the frozen outputs after the
primary results were fixed. They do not modify any frozen artifact and are
reported as post-hoc reanalysis, not as primary metrics.

## Sign tests (changed subsets)

| Grounding | ASR | Method | n | WC | CW | delta | p |
|---|---|---|---|---|---|---|---|
| G1 | typhoon_asr_api | A_no_screen_cleanup | 0 | 0 | 0 |  | n/a |
| G1 | typhoon_asr_api | B_screen_string_match | 0 | 0 | 0 |  | n/a |
| G1 | typhoon_asr_api | C_full_screen_aware_alias | 53 | 0 | 6 | -0.113208 | 0.0312 |
| G1 | whisper_large_v3_local | A_no_screen_cleanup | 72 | 2 | 0 | 0.027778 | 0.5000 |
| G1 | whisper_large_v3_local | B_screen_string_match | 72 | 1 | 0 | 0.013889 | 1.0000 |
| G1 | whisper_large_v3_local | C_full_screen_aware_alias | 113 | 1 | 4 | -0.026549 | 0.3750 |
| G2 | typhoon_asr_api | A_no_screen_cleanup | 0 | 0 | 0 |  | n/a |
| G2 | typhoon_asr_api | B_screen_string_match | 0 | 0 | 0 |  | n/a |
| G2 | typhoon_asr_api | C_full_screen_aware_alias | 53 | 6 | 6 | 0.000000 | 1.0000 |
| G2 | whisper_large_v3_local | A_no_screen_cleanup | 72 | 14 | 13 | 0.013889 | 1.0000 |
| G2 | whisper_large_v3_local | B_screen_string_match | 72 | 9 | 10 | -0.013889 | 1.0000 |
| G2 | whisper_large_v3_local | C_full_screen_aware_alias | 113 | 13 | 15 | -0.017699 | 0.8506 |

## Sign tests (unchanged/no-op subsets)

| Grounding | ASR | Method | n | WC | CW | delta | p |
|---|---|---|---|---|---|---|---|
| G1 | typhoon_asr_api | A_no_screen_cleanup | 471 | 5 | 11 | -0.012739 | 0.2101 |
| G1 | typhoon_asr_api | B_screen_string_match | 471 | 8 | 12 | -0.008493 | 0.5034 |
| G1 | typhoon_asr_api | C_full_screen_aware_alias | 418 | 8 | 8 | 0.000000 | 1.0000 |
| G1 | whisper_large_v3_local | A_no_screen_cleanup | 399 | 2 | 7 | -0.012531 | 0.1797 |
| G1 | whisper_large_v3_local | B_screen_string_match | 399 | 5 | 8 | -0.007519 | 0.5811 |
| G1 | whisper_large_v3_local | C_full_screen_aware_alias | 358 | 2 | 8 | -0.016760 | 0.1094 |
| G2 | typhoon_asr_api | A_no_screen_cleanup | 471 | 49 | 78 | -0.061571 | 0.0127 |
| G2 | typhoon_asr_api | B_screen_string_match | 471 | 69 | 70 | -0.002123 | 1.0000 |
| G2 | typhoon_asr_api | C_full_screen_aware_alias | 418 | 52 | 59 | -0.016746 | 0.5692 |
| G2 | whisper_large_v3_local | A_no_screen_cleanup | 399 | 47 | 47 | 0.000000 | 1.0000 |
| G2 | whisper_large_v3_local | B_screen_string_match | 399 | 46 | 53 | -0.017544 | 0.5467 |
| G2 | whisper_large_v3_local | C_full_screen_aware_alias | 358 | 31 | 48 | -0.047486 | 0.0712 |

## Baseline Wilson 95% intervals

| Grounding | Condition | n | Accuracy | 95% interval |
|---|---|---|---|---|
| G1 | asr_typhoon_asr_api | 471 | 0.7643 | [0.7240, 0.8004] |
| G1 | asr_whisper_large_v3_local | 471 | 0.7580 | [0.7173, 0.7945] |
| G1 | gold | 128 | 0.7656 | [0.6852, 0.8306] |
| G2 | asr_typhoon_asr_api | 471 | 0.4034 | [0.3600, 0.4483] |
| G2 | asr_whisper_large_v3_local | 471 | 0.3907 | [0.3477, 0.4354] |
| G2 | gold | 128 | 0.4453 | [0.3621, 0.5318] |

## Per-command paired gold-vs-ASR differences (clustered bootstrap)

Commands are the resampling unit; 10000 draws, seed 20260719.

| Grounding | ASR | Commands | Mean paired diff | 95% bootstrap interval |
|---|---|---|---|---|
| G1 | whisper_large_v3_local | 128 | -0.0052 | [-0.0312, +0.0202] |
| G1 | typhoon_asr_api | 128 | +0.0007 | [-0.0234, +0.0286] |
| G2 | whisper_large_v3_local | 128 | -0.0443 | [-0.1250, +0.0371] |
| G2 | typhoon_asr_api | 128 | -0.0332 | [-0.1087, +0.0436] |

## Cosmetic versus substantive transcript changes (NFKC)

A change is cosmetic when the raw and corrected transcripts are identical
after NFKC and whitespace normalization. Recovery and false correction are
recomputed here under NFKC-normalized CER; the frozen Table 4 numbers remain
the primary metrics.

| ASR | Method | n | Changed | Cosmetic-only | Substantive | Recovery (NFKC) | False corr. (NFKC) |
|---|---|---|---|---|---|---|---|
| typhoon_asr_api | A_no_screen_cleanup | 471 | 0 | 0 | 0 | 0 (0.0000) | 0 (0.0000) |
| typhoon_asr_api | B_screen_string_match | 471 | 0 | 0 | 0 | 0 (0.0000) | 0 (0.0000) |
| typhoon_asr_api | C_full_screen_aware_alias | 471 | 53 | 0 | 53 | 15 (0.0318) | 48 (0.1019) |
| whisper_large_v3_local | A_no_screen_cleanup | 471 | 72 | 72 | 0 | 0 (0.0000) | 0 (0.0000) |
| whisper_large_v3_local | B_screen_string_match | 471 | 72 | 63 | 9 | 9 (0.0191) | 0 (0.0000) |
| whisper_large_v3_local | C_full_screen_aware_alias | 471 | 113 | 66 | 47 | 12 (0.0255) | 38 (0.0807) |
