# Screen Generation Report

- Generation date: `2026-07-19T03:16:45+07:00`
- Seed: `42`
- Number of screens: `20`
- Number of target candidates: `40`
- Number of distractor groups: `60` screen-level groups; `6` distinct group names

## Screens Per Domain

| Metric | Count |
| --- | ---: |
| mock_finance | 5 |
| shopping | 5 |
| settings | 5 |
| messaging | 5 |

## Elements Per Domain

| Metric | Count |
| --- | ---: |
| mock_finance | 60 |
| shopping | 60 |
| settings | 60 |
| messaging | 60 |

## Label Mix

| Metric | Count |
| --- | ---: |
| Thai-only screens | 8 |
| English-only screens | 4 |
| Mixed-label screens | 8 |

## Example Distractor Groups

- `bottom_navigation` in `mock_finance_001`: `หน้าแรก`, `Home`, `สแกน`, `Scan`
- `message_actions` in `messaging_001`: `ส่ง`, `ค้นหา`, `ปิดเสียง`, `โปรไฟล์`
- `money_actions` in `mock_finance_001`: `โอนเงิน`, `Transfer`, `เติมเงิน`, `Top up`
- `secondary_actions` in `mock_finance_001`: `จ่ายบิล`, `Pay bill`, `เงินออม`, `Savings`
- `settings_controls` in `settings_001`: `ตั้งค่า`, `Settings`, `ภาษา`, `Language`
- `shopping_actions` in `shopping_001`: `ค้นหา`, `Search`, `เรียงลำดับ`, `Sort`

## Known Limitations

- Screens are synthetic templates, so they do not cover the full visual diversity of real mobile apps.
- Labels are curated mock labels and do not model all Thai regional wording, slang, or speech-register variants.
- Layouts use fixed mobile-style regions; overlapping, scrolling, modal, and gesture-heavy interfaces are out of scope.
- Icons are represented mainly through text/button affordances, so icon-only grounding is not yet stressed.
- TTS, ASR, correction, and grounding stages are not exercised by this screen-generation report.

## Validation

- Command: `python scripts/validate_screens.py --screens-jsonl data/screens/screens.jsonl --image-root .`
- Result: `passed`
