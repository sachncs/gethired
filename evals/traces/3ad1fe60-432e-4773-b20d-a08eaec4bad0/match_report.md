# gethired run `3ad1fe60-432e-4773-b20d-a08eaec4bad0`

## Run Description
- Run.id: `3ad1fe60-432e-4773-b20d-a08eaec4bad0`
- started_at: 2026-08-02T11:25:34.305Z
- master_hash: `15c83d1b25c6ef220548a957286206eae99c1cad85d08e05d827c333ee56a72d`
- jd_urls_hash: `c72ce086fafb9e92`
- model: `test`

## Result Description
- completed_at: 2026-08-02T11:25:34.325Z
- duration_seconds: 0.00
- total_input_tokens: 0
- total_output_tokens: 0
- retry_attempts: 0
- final_outcome: `ats_hard_fail`

## Job Trail
| id | type | inputs | outputs | rationale | status |
|----|------|--------|---------|-----------|--------|
| 291a9537 | `lookup` | — | tool:lookup_experience | Called read-only tool lookup_experience | `success` |
| da147a35 | `lookup` | — | tool:lookup_project | Called read-only tool lookup_project | `success` |
| 8e1b6124 | `lookup` | — | tool:list_skills | Called read-only tool list_skills | `success` |
| c6728cf6 | `lookup` | — | tool:list_projects | Called read-only tool list_projects | `success` |
| 4c609b22 | `lookup` | — | tool:list_education | Called read-only tool list_education | `success` |
| c3b12eb5 | `lookup` | — | tool:list_awards | Called read-only tool list_awards | `success` |
| bc6bf5f3 | `lookup` | — | tool:read_jd_summary | Called read-only tool read_jd_summary | `success` |
| 22747ba8 | `lookup` | — | tool:lookup_experience | Called read-only tool lookup_experience | `success` |
| 28e8b2e6 | `lookup` | — | tool:lookup_project | Called read-only tool lookup_project | `success` |
| 17b3ffaa | `lookup` | — | tool:list_skills | Called read-only tool list_skills | `success` |
| 95cba33b | `lookup` | — | tool:list_projects | Called read-only tool list_projects | `success` |
| bd805c37 | `lookup` | — | tool:list_education | Called read-only tool list_education | `success` |
| de08a05f | `lookup` | — | tool:list_awards | Called read-only tool list_awards | `success` |
| 5935db75 | `lookup` | — | tool:read_jd_summary | Called read-only tool read_jd_summary | `success` |
| 9d64b6ab | `lookup` | — | tool:final_result | Called read-only tool final_result | `success` |
| 66126e9f | `lookup` | — | tool:final_result | Called read-only tool final_result | `success` |
| 0b9d7ffd | `tailor` | — | tailored_resume | LLM produced 1 rewritten bullets; rationale: a | `success` |
| 2d2efb06 | `validate_grounding` | — | grounding_violations | Validated that every claim traces to master | `success` |
| 615f9fe8 | `validate_style` | — | style_violations | Validated banned words, parallelism, quantification | `success` |
| bee5596f | `validate_plagiarism` | — | plagiarism_violations | Validated no verbatim JD phrase overlap | `success` |
| 8750b958 | `validate_ats` | — | ats_gates | Ran all 11 ATS gates (compile, extract, headings, layout, etc.) | `success` |

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
