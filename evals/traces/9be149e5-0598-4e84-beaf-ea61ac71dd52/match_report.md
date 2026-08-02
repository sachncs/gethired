# gethired run `9be149e5-0598-4e84-beaf-ea61ac71dd52`

## Run Description
- Run.id: `9be149e5-0598-4e84-beaf-ea61ac71dd52`
- started_at: 2026-08-02T11:25:34.279Z
- master_hash: `15c83d1b25c6ef220548a957286206eae99c1cad85d08e05d827c333ee56a72d`
- jd_urls_hash: `c72ce086fafb9e92`
- model: `test`

## Result Description
- completed_at: 2026-08-02T11:25:34.299Z
- duration_seconds: 0.00
- total_input_tokens: 0
- total_output_tokens: 0
- retry_attempts: 0
- final_outcome: `ats_hard_fail`

## Job Trail
| id | type | inputs | outputs | rationale | status |
|----|------|--------|---------|-----------|--------|
| 658cc890 | `lookup` | — | tool:lookup_experience | Called read-only tool lookup_experience | `success` |
| 68bf1c93 | `lookup` | — | tool:lookup_project | Called read-only tool lookup_project | `success` |
| 94303806 | `lookup` | — | tool:list_skills | Called read-only tool list_skills | `success` |
| 226beacd | `lookup` | — | tool:list_projects | Called read-only tool list_projects | `success` |
| aa9c2b7b | `lookup` | — | tool:list_education | Called read-only tool list_education | `success` |
| 0b385bde | `lookup` | — | tool:list_awards | Called read-only tool list_awards | `success` |
| 1cdec103 | `lookup` | — | tool:read_jd_summary | Called read-only tool read_jd_summary | `success` |
| e92b34b3 | `lookup` | — | tool:lookup_experience | Called read-only tool lookup_experience | `success` |
| 55322d76 | `lookup` | — | tool:lookup_project | Called read-only tool lookup_project | `success` |
| 555854b7 | `lookup` | — | tool:list_skills | Called read-only tool list_skills | `success` |
| 433d001a | `lookup` | — | tool:list_projects | Called read-only tool list_projects | `success` |
| 7e0413fa | `lookup` | — | tool:list_education | Called read-only tool list_education | `success` |
| 5e9cde22 | `lookup` | — | tool:list_awards | Called read-only tool list_awards | `success` |
| 0be4eef9 | `lookup` | — | tool:read_jd_summary | Called read-only tool read_jd_summary | `success` |
| 55197894 | `lookup` | — | tool:final_result | Called read-only tool final_result | `success` |
| 685e0b9a | `lookup` | — | tool:final_result | Called read-only tool final_result | `success` |
| 00311f63 | `tailor` | — | tailored_resume | LLM produced 1 rewritten bullets; rationale: a | `success` |
| 14d22ca7 | `validate_grounding` | — | grounding_violations | Validated that every claim traces to master | `success` |
| 03cced51 | `validate_style` | — | style_violations | Validated banned words, parallelism, quantification | `success` |
| 6aab8b50 | `validate_plagiarism` | — | plagiarism_violations | Validated no verbatim JD phrase overlap | `success` |
| bd4df504 | `validate_ats` | — | ats_gates | Ran all 11 ATS gates (compile, extract, headings, layout, etc.) | `success` |

## ATS Gate Results
| gate | passed | detail |
|------|--------|--------|
| `pdf_compiles` | FAIL | PDF not compiled |
| `pdf_text_extractable` | FAIL | PDF missing |
| `pdf_text_matches_txt` | FAIL | PDF missing |
| `section_headings_standard` | PASS | All required sections present |
| `no_tables_for_layout` | PASS | OK |
| `no_images` | PASS | OK |
| `no_colors` | PASS | OK |
| `font_size_10_12` | PASS | 11pt OK |
| `length_within_limit` | FAIL | ~9.00 pages exceeds limit of 1.0 (36 bullets; tex=36, structured=33) |
| `keywords_covered` | PASS | All keywords covered |
| `bullets_quantified` | FAIL | 18% quantified (< 70%) |
| `action_verbs_first` | FAIL | 7 bullets don't start with action verbs |

## Reasoning Trace
| # | rationale |
|---|-----------|
| 1 | Called read-only tool lookup_experience |
| 2 | Called read-only tool lookup_project |
| 3 | Called read-only tool list_skills |
| 4 | Called read-only tool list_projects |
| 5 | Called read-only tool list_education |
| 6 | Called read-only tool list_awards |
| 7 | Called read-only tool read_jd_summary |
| 8 | Called read-only tool lookup_experience |
| 9 | Called read-only tool lookup_project |
| 10 | Called read-only tool list_skills |
| 11 | Called read-only tool list_projects |
| 12 | Called read-only tool list_education |
| 13 | Called read-only tool list_awards |
| 14 | Called read-only tool read_jd_summary |
| 15 | Called read-only tool final_result |
| 16 | Called read-only tool final_result |
| 17 | LLM produced 1 rewritten bullets; rationale: a |
| 18 | Validated that every claim traces to master |
| 19 | Validated banned words, parallelism, quantification |
| 20 | Validated no verbatim JD phrase overlap |
| 21 | Ran all 11 ATS gates (compile, extract, headings, layout, etc.) |

## Keyword Coverage
(See Job Trail above for per-step keyword usage.)

## Tailored Summary
a
