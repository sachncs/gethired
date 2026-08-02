# gethired run `8c4f8b41-a112-47f1-8fd7-a2c7dfabdd77`

## Run Description
- Run.id: `8c4f8b41-a112-47f1-8fd7-a2c7dfabdd77`
- started_at: 2026-08-02T11:25:34.192Z
- master_hash: `15c83d1b25c6ef220548a957286206eae99c1cad85d08e05d827c333ee56a72d`
- jd_urls_hash: `c72ce086fafb9e92`
- model: `test`

## Result Description
- completed_at: 2026-08-02T11:25:34.219Z
- duration_seconds: 0.00
- total_input_tokens: 0
- total_output_tokens: 0
- retry_attempts: 0
- final_outcome: `ats_hard_fail`

## Job Trail
| id | type | inputs | outputs | rationale | status |
|----|------|--------|---------|-----------|--------|
| 91ad1757 | `lookup` | — | tool:lookup_experience | Called read-only tool lookup_experience | `success` |
| 307f5937 | `lookup` | — | tool:lookup_project | Called read-only tool lookup_project | `success` |
| 362ac626 | `lookup` | — | tool:list_skills | Called read-only tool list_skills | `success` |
| ca939498 | `lookup` | — | tool:list_projects | Called read-only tool list_projects | `success` |
| 37d944f2 | `lookup` | — | tool:list_education | Called read-only tool list_education | `success` |
| 24bfa1c4 | `lookup` | — | tool:list_awards | Called read-only tool list_awards | `success` |
| 1648e13c | `lookup` | — | tool:read_jd_summary | Called read-only tool read_jd_summary | `success` |
| 7106879e | `lookup` | — | tool:lookup_experience | Called read-only tool lookup_experience | `success` |
| c91971b7 | `lookup` | — | tool:lookup_project | Called read-only tool lookup_project | `success` |
| d2d4f59d | `lookup` | — | tool:list_skills | Called read-only tool list_skills | `success` |
| 897ab423 | `lookup` | — | tool:list_projects | Called read-only tool list_projects | `success` |
| 74f37dc1 | `lookup` | — | tool:list_education | Called read-only tool list_education | `success` |
| 3a41c29a | `lookup` | — | tool:list_awards | Called read-only tool list_awards | `success` |
| 93bb551e | `lookup` | — | tool:read_jd_summary | Called read-only tool read_jd_summary | `success` |
| 37d33c2e | `lookup` | — | tool:final_result | Called read-only tool final_result | `success` |
| 65a57dba | `lookup` | — | tool:final_result | Called read-only tool final_result | `success` |
| f4c85af5 | `tailor` | — | tailored_resume | LLM produced 1 rewritten bullets; rationale: a | `success` |
| 81821917 | `validate_grounding` | — | grounding_violations | Validated that every claim traces to master | `success` |
| 4589f57e | `validate_style` | — | style_violations | Validated banned words, parallelism, quantification | `success` |
| 7ccb7beb | `validate_plagiarism` | — | plagiarism_violations | Validated no verbatim JD phrase overlap | `success` |
| f1ca2675 | `validate_ats` | — | ats_gates | Ran all 11 ATS gates (compile, extract, headings, layout, etc.) | `success` |

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
