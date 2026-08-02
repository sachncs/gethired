# gethired run `0184bb78-7041-4b54-aa5f-de1e4dbf72f5`

## Run Description
- Run.id: `0184bb78-7041-4b54-aa5f-de1e4dbf72f5`
- started_at: 2026-08-02T11:25:34.252Z
- master_hash: `15c83d1b25c6ef220548a957286206eae99c1cad85d08e05d827c333ee56a72d`
- jd_urls_hash: `c72ce086fafb9e92`
- model: `test`

## Result Description
- completed_at: 2026-08-02T11:25:34.273Z
- duration_seconds: 0.00
- total_input_tokens: 0
- total_output_tokens: 0
- retry_attempts: 0
- final_outcome: `ats_hard_fail`

## Job Trail
| id | type | inputs | outputs | rationale | status |
|----|------|--------|---------|-----------|--------|
| 934a5d43 | `lookup` | — | tool:lookup_experience | Called read-only tool lookup_experience | `success` |
| 5a84f089 | `lookup` | — | tool:lookup_project | Called read-only tool lookup_project | `success` |
| debfe8b0 | `lookup` | — | tool:list_skills | Called read-only tool list_skills | `success` |
| fe6c1ee8 | `lookup` | — | tool:list_projects | Called read-only tool list_projects | `success` |
| 9e9b1123 | `lookup` | — | tool:list_education | Called read-only tool list_education | `success` |
| 151417f2 | `lookup` | — | tool:list_awards | Called read-only tool list_awards | `success` |
| aedb68d2 | `lookup` | — | tool:read_jd_summary | Called read-only tool read_jd_summary | `success` |
| 35bed8d5 | `lookup` | — | tool:lookup_experience | Called read-only tool lookup_experience | `success` |
| 7c3f2483 | `lookup` | — | tool:lookup_project | Called read-only tool lookup_project | `success` |
| 060b2c82 | `lookup` | — | tool:list_skills | Called read-only tool list_skills | `success` |
| 9300dfb9 | `lookup` | — | tool:list_projects | Called read-only tool list_projects | `success` |
| dc0bd1b1 | `lookup` | — | tool:list_education | Called read-only tool list_education | `success` |
| 9a749ea8 | `lookup` | — | tool:list_awards | Called read-only tool list_awards | `success` |
| 013cd6bf | `lookup` | — | tool:read_jd_summary | Called read-only tool read_jd_summary | `success` |
| 5c2a04ad | `lookup` | — | tool:final_result | Called read-only tool final_result | `success` |
| 88df6781 | `lookup` | — | tool:final_result | Called read-only tool final_result | `success` |
| 131296f0 | `tailor` | — | tailored_resume | LLM produced 1 rewritten bullets; rationale: a | `success` |
| 7d24238c | `validate_grounding` | — | grounding_violations | Validated that every claim traces to master | `success` |
| 61a8d99d | `validate_style` | — | style_violations | Validated banned words, parallelism, quantification | `success` |
| 2177e927 | `validate_plagiarism` | — | plagiarism_violations | Validated no verbatim JD phrase overlap | `success` |
| cc954056 | `validate_ats` | — | ats_gates | Ran all 11 ATS gates (compile, extract, headings, layout, etc.) | `success` |

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
| `keywords_covered` | FAIL | Missing must-have keywords: ['distributed systems'] |
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
