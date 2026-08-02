"""Rules and constants for the gethired validation pipeline.

Single source of truth for the three resume checklists, the grounding rules,
the anti-AI language rules, and the plagiarism avoidance rules.
"""

from __future__ import annotations

from typing import Final

CHECKLIST_RUBRIC: Final[tuple[str, ...]] = (
    # UIowa Resume Critique Checklist
    "first_impression_inviting",
    "professional_design",
    "summary_conveys_match",
    "appropriate_length",
    "visually_pleasing",
    "simple_readable_font",
    "bullets_bold_underline_consistent",
    "adequate_white_space",
    "even_margins",
    "consistent_design_elements",
    "labeled_sections",
    "sections_highlight_strengths",
    "reverse_chronological",
    "targeted_to_specific_position",
    "career_change_stated_in_summary",
    "solid_career_accomplishments",
    "quantified_accomplishments",
    "strong_varied_action_verbs",
    "accomplishments_separated_from_responsibilities",
    "relevant_to_position",
    "summary_supported_by_content",
    "awards_included",
    "no_marital_status_age_nationality",
    "implied_first_person_voice",
    "no_personal_pronouns",
    "logical_content_flow",
    "crisp_bullet_phrases",
    "no_typos_or_grammar_errors",
    # Indeed 10-step checklist
    "structure_appropriate_for_experience_level",
    "name_in_larger_font",
    "contact_info_complete",
    "professional_summary_3_to_5_sentences",
    "work_experience_reverse_chronological",
    "past_tense_for_past_present_for_current",
    "action_verbs_for_each_bullet",
    "include_keywords_from_jd",
    "3_to_5_bullets_per_role_star_method",
    "hard_and_soft_skills_listed",
    "education_simple_streamlined",
    "certifications_optional_section",
    "regular_font_10_to_12pt",
    "bold_section_headings",
    "save_as_pdf",
    "proofread_no_spelling_errors",
    "no_complete_sentences_in_bullets",
    "margin_at_least_half_inch",
    # Bridgewater checklist
    "easy_to_read_consistent_style",
    "font_10_to_12_points",
    "bold_italics_underlining_minimal_consistent",
    "margins_and_line_spacing_appropriate",
    "appropriate_length_one_page",
    "no_personal_pronouns",
    "no_typos_or_grammar_mistakes",
    "no_references_on_resume",
    "include_name_address_email_phone",
    "include_linkedin_url",
    "professional_email_address",
    "education_reverse_chronological",
    "include_college_degree_major_graduation",
    "include_gpa_if_required",
    "academic_projects_highlighted",
    "list_technical_skills",
    "list_related_training_certifications",
    "list_language_skills",
    "experience_reverse_chronological",
    "list_company_city_state_job_title",
    "include_month_year_dates",
    "no_supervisor_or_salary",
    "bullet_points_start_with_action_verbs",
    "avoid_passive_phrases",
    "present_tense_for_current_past_for_past",
    "include_numbers_to_quantify",
    "split_experience_if_necessary",
    "leadership_experience_included",
)


BANNED_WORDS: Final[frozenset[str]] = frozenset(
    {
        # AI-tell vocabulary
        "leverage",
        "leveraging",
        "leverages",
        "robust",
        "streamlined",
        "streamline",
        "seamless",
        "seamlessly",
        "comprehensive",
        "holistic",
        "spearheaded",
        "championed",
        "underscores",
        "underscore",
        "showcases",
        "showcase",
        "demonstrates",
        "demonstrate",
        "delve",
        "delves",
        "delving",
        "navigate",
        "navigating",
        "elevate",
        "elevating",
        "fostering",
        "foster",
        "pivotal",
        "crucial",
        "tapestry",
        "myriad",
        "vibrant",
        "dynamic",
        "empower",
        "empowering",
        "transformative",
        "realm",
        "landscape",
        "harness",
        "harnessing",
        "endeavor",
        "endeavors",
        "meticulous",
        "meticulously",
        "bespoke",
        "intricate",
        "paramount",
        "multifaceted",
        "cutting-edge",
        "cutting_edge",
        "state-of-the-art",
        "state_of_the_art",
        "game-changer",
        "game_changer",
        "unprecedented",
        "revolutionary",
        "world-class",
        "world_class",
        "best-in-class",
        "best_in_class",
    }
)


BANNED_CONSTRUCTIONS: Final[frozenset[str]] = frozenset(
    {
        # Over-formal phrasings
        "in order to",
        "due to the fact that",
        "with regard to",
        "in light of the fact that",
        "at this point in time",
        "for the purpose of",
        "in the event that",
        "as a means of",
        # Empty intensifiers
        "significantly",
        "substantially",
        "greatly",
        "vastly",
        "highly",  # when followed by noun
    }
)


TECHNICAL_NGRAMS_ALLOWLIST: Final[frozenset[str]] = frozenset(
    {
        "natural language processing",
        "machine learning",
        "deep learning",
        "computer vision",
        "reinforcement learning",
        "convolutional neural network",
        "neural network",
        "large language model",
        "large language models",
        "retrieval augmented generation",
        "real time video",
        "real time",
        "end to end",
        "real time analytics",
        "distributed systems",
        "distributed system",
        "data processing",
        "data pipeline",
        "data pipelines",
        "test driven",
        "event driven",
        "object oriented",
        "open source",
        "high availability",
        "high performance",
        "search engine",
        "supply chain",
        "production grade",
        "real world",
        "machine learning systems",
        "knowledge intensive",
        "vision language",
        "vision language inference",
    }
)


GROUNDING_RULES: Final[tuple[str, ...]] = (
    "only_use_facts_present_in_master",
    "never_invent_skills_projects_companies_roles_dates_education_awards_certifications_metrics",
    "concrete_claims_must_appear_verbatim_in_master",
    "numbers_tech_outcomes_verbatim_from_master",
    "missing_skill_or_credential_is_a_gap_not_a_fabrication",
    "bullets_may_be_paraphrased_to_mirror_jd_terminology",
    "summary_may_be_rewritten_using_only_master_facts",
    "reorder_emphasize_prune_never_invent",
)


ANTI_AI_RULES: Final[tuple[str, ...]] = (
    "no_banned_words_in_tailored_text",
    "no_three_plus_bullets_sharing_same_opening_verb",
    "no_three_plus_bullets_in_role_sharing_opening_verb_stem",
    "bullet_length_variance_at_least_30_percent_of_mean",
    "no_bullet_length_exceeding_2x_voice_profile_avg",
    "no_banned_constructions",
    "no_4_word_jd_phrase_copied_verbatim",
    "no_5_gram_jd_overlap_minus_technical_allowlist",
    "maintain_candidate_authentic_voice",
    "vary_opening_verbs_per_role",
    "vary_sentence_length",
)


PLAGIARISM_RULES: Final[tuple[str, ...]] = (
    "do_not_copy_jd_phrases_verbatim",
    "mirror_concepts_not_phrasing",
    "use_master_wording_when_overlapping",
    "5_grams_must_be_excluded_from_technical_ngrams_allowlist",
)


ACTION_VERBS: Final[frozenset[str]] = frozenset(
    {
        "achieved", "added", "administered", "advised", "allocated", "analyzed",
        "applied", "assembled", "assessed", "authored", "audited", "built",
        "boosted", "brought", "budgeted", "coached", "coded", "collaborated",
        "collected", "communicated", "completed", "composed", "conceived",
        "conducted", "configured", "constructed", "contributed", "converted",
        "created", "cultivated", "cut", "decreased", "delivered", "deployed",
        "designed", "determined", "developed", "directed", "discovered",
        "drove", "drafted", "engineered", "established", "evaluated",
        "expanded", "expedited", "extracted", "facilitated", "finalised",
        "finalized", "formulated", "founded", "generated", "guided", "handed",
        "headed", "helped", "identified", "implemented", "improved",
        "increased", "initiated", "integrated", "introduced", "invented",
        "investigated", "launched", "led", "leveraged", "managed", "mapped",
        "migrated", "modeled", "modelled", "modified", "monitored",
        "negotiated", "organized", "orchestrated", "outlined", "participated",
        "performed", "planned", "prepared", "presented", "prioritised",
        "prioritized", "produced", "programmed", "promoted", "proposed",
        "prototyped", "provided", "recommended", "reduced", "refactored",
        "released", "reliably", "resolved", "resourced", "restored",
        "restructured", "resulted", "retained", "reviewed", "revised", "saved",
        "scaled", "scheduled", "secured", "selected", "set", "simplified",
        "sold", "solved", "specified", "started", "steered", "streamlined",
        "structured", "succeeded", "suggested", "supervised", "supported",
        "synced", "trained", "transformed", "tuned", "turned", "undertook",
        "updated", "used", "utilized", "validated", "verified", "won", "worked",
        "wrote",
    }
)


REQUIRED_SECTION_HEADINGS: Final[tuple[str, ...]] = (
    "Summary",
    "Experience",
    "Education",
    "Technical Skills",
    "Selected Projects",
)


OPTIONAL_SECTION_HEADINGS: Final[tuple[str, ...]] = (
    "Awards & Recognition",
    "Certifications",
    "Publications",
)


__all__ = [
    "ACTION_VERBS",
    "ANTI_AI_RULES",
    "BANNED_CONSTRUCTIONS",
    "BANNED_WORDS",
    "CHECKLIST_RUBRIC",
    "GROUNDING_RULES",
    "OPTIONAL_SECTION_HEADINGS",
    "PLAGIARISM_RULES",
    "REQUIRED_SECTION_HEADINGS",
    "TECHNICAL_NGRAMS_ALLOWLIST",
]
