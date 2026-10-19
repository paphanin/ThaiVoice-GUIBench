# Split Report

- Profile: `provisional20`
- Seed: `42`
- Screen-disjoint: `true`
- Dev screens: `5`
- Test screens: `15`
- Dev utterances: `32`
- Test utterances: `96`
- Dev expected voices: `None`
- Test expected voices: `None`
- Test-only voices: `azure/voice_02`
- Dev expected audio slots: `0`
- Test expected audio slots: `0`
- Total expected audio slots: `0`

## Dev Screens

- `messaging_001`
- `messaging_003`
- `mock_finance_002`
- `settings_001`
- `shopping_004`

## Test Screens

- `messaging_002`
- `messaging_004`
- `messaging_005`
- `mock_finance_001`
- `mock_finance_003`
- `mock_finance_004`
- `mock_finance_005`
- `settings_002`
- `settings_003`
- `settings_004`
- `settings_005`
- `shopping_001`
- `shopping_002`
- `shopping_003`
- `shopping_005`

## Domains

| Split | Domain | Screens |
| --- | --- | ---: |
| dev | `messaging` | 2 |
| dev | `mock_finance` | 1 |
| dev | `settings` | 1 |
| dev | `shopping` | 1 |
| test | `messaging` | 3 |
| test | `mock_finance` | 4 |
| test | `settings` | 4 |
| test | `shopping` | 4 |

## Tiers

| Split | Tier | Utterances |
| --- | --- | ---: |
| dev | `T1_verbatim` | 8 |
| dev | `T2_paraphrase` | 8 |
| dev | `T3_intent` | 8 |
| dev | `T4_visual_positional` | 8 |
| test | `T1_verbatim` | 24 |
| test | `T2_paraphrase` | 24 |
| test | `T3_intent` | 24 |
| test | `T4_visual_positional` | 24 |

## Validation

- Validation result: pending
- Test result: pending
