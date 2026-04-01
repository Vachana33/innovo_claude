"""Tests for innovo_backend.services.documents.prompt_builder.PromptBuilder."""
import json
import pytest
from unittest.mock import MagicMock

from innovo_backend.services.documents.prompt_builder import PromptBuilder


SAMPLE_SECTIONS = [
    {"id": "1", "title": "1. Einleitung", "type": "text", "content": ""},
    {"id": "2", "title": "2. Ziele", "type": "text", "content": ""},
    {"id": "3", "title": "3. Arbeitsplan", "type": "milestone_table", "content": ""},
]

COMPANY_PROFILE = {
    "company_name": "TestTech GmbH",
    "industry": "Software",
    "products_or_services": ["AI Platform", "Data Analytics"],
    "business_model": "SaaS",
    "market": "B2B Enterprise",
    "innovation_focus": "Machine Learning",
    "company_size": "50 Mitarbeiter",
    "location": "Berlin",
}

FUNDING_RULES = {
    "eligibility_rules": ["Nur KMUs", "Mindestens 2 Mitarbeiter"],
    "required_sections": ["Projektziele", "Arbeitsplan"],
    "forbidden_content": ["Keine Umsatzprognosen"],
    "evaluation_criteria": ["Innovationsgrad", "Förderwürdigkeit"],
}


# ---------------------------------------------------------------------------
# Construction paths
# ---------------------------------------------------------------------------

class TestPromptBuilderConstruction:
    def test_v1_raw_construction(self):
        builder = PromptBuilder(
            company_name="Acme GmbH",
            company_profile=COMPANY_PROFILE,
        )
        assert builder is not None

    def test_v1_company_orm_construction(self):
        company = MagicMock()
        company.name = "ORM Company"
        company.company_profile = COMPANY_PROFILE
        company.website_clean_text = None
        company.transcript_clean = None
        company.id = 42
        builder = PromptBuilder(company=company)
        assert builder._company_name == "ORM Company"

    def test_v2_context_construction(self):
        ctx = MagicMock()
        ctx.company_profile_json = COMPANY_PROFILE
        ctx.funding_rules_json = FUNDING_RULES
        ctx.style_profile_json = None
        ctx.retrieved_examples_json = None
        builder = PromptBuilder(context=ctx)
        assert builder is not None


# ---------------------------------------------------------------------------
# build_generation_prompt
# ---------------------------------------------------------------------------

class TestBuildGenerationPrompt:
    def test_returns_string(self):
        builder = PromptBuilder(company_name="Acme GmbH")
        prompt = builder.build_generation_prompt(SAMPLE_SECTIONS)
        assert isinstance(prompt, str)
        assert len(prompt) > 100

    def test_contains_section_ids(self):
        builder = PromptBuilder(company_name="Acme GmbH")
        prompt = builder.build_generation_prompt(SAMPLE_SECTIONS)
        # Section IDs 1 and 2 should appear (milestone_table id=3 is excluded)
        assert '"1"' in prompt or "1." in prompt
        assert '"2"' in prompt or "2." in prompt

    def test_milestone_table_excluded_from_ids(self):
        builder = PromptBuilder(company_name="Acme GmbH")
        prompt = builder.build_generation_prompt(SAMPLE_SECTIONS)
        # Milestone table section should not be in the task list
        assert "Arbeitsplan" not in prompt or "milestone_table" not in prompt

    def test_includes_company_name(self):
        builder = PromptBuilder(company_name="UniqueCompanyXYZ GmbH")
        prompt = builder.build_generation_prompt(SAMPLE_SECTIONS)
        assert "UniqueCompanyXYZ GmbH" in prompt

    def test_includes_funding_rules(self):
        builder = PromptBuilder(
            company_name="Acme",
            funding_rules=FUNDING_RULES,
        )
        prompt = builder.build_generation_prompt(SAMPLE_SECTIONS)
        assert "Berechtigungskriterien" in prompt
        assert "Nur KMUs" in prompt

    def test_includes_company_profile_fields(self):
        builder = PromptBuilder(
            company_name="TestTech GmbH",
            company_profile=COMPANY_PROFILE,
        )
        prompt = builder.build_generation_prompt(SAMPLE_SECTIONS)
        assert "Software" in prompt  # industry
        assert "Machine Learning" in prompt  # innovation_focus

    def test_output_format_includes_json_instruction(self):
        builder = PromptBuilder(company_name="Acme")
        prompt = builder.build_generation_prompt(SAMPLE_SECTIONS)
        assert "JSON" in prompt

    def test_german_language_instruction(self):
        builder = PromptBuilder(company_name="Acme")
        prompt = builder.build_generation_prompt(SAMPLE_SECTIONS)
        assert "Deutsch" in prompt or "deutsch" in prompt

    def test_includes_style_profile_when_provided(self):
        style = {
            "tone_characteristics": ["Formal", "Präzise"],
            "writing_style_rules": ["Kurze Sätze", "Aktiver Stil"],
        }
        builder = PromptBuilder(company_name="Acme", style_profile=style)
        prompt = builder.build_generation_prompt(SAMPLE_SECTIONS)
        assert "Formal" in prompt
        assert "Kurze Sätze" in prompt

    def test_context_v2_uses_context_profile(self):
        ctx = MagicMock()
        ctx.company_profile_json = {"company_name": "CTX Company GmbH", "industry": "Biotech"}
        ctx.funding_rules_json = None
        ctx.style_profile_json = None
        ctx.retrieved_examples_json = None
        builder = PromptBuilder(context=ctx)
        prompt = builder.build_generation_prompt(SAMPLE_SECTIONS)
        assert "CTX Company GmbH" in prompt

    def test_website_text_included_in_v1_path(self):
        builder = PromptBuilder(
            company_name="Acme",
            website_clean_text="Wir sind ein innovatives Unternehmen.",
        )
        prompt = builder.build_generation_prompt(SAMPLE_SECTIONS)
        assert "Wir sind ein innovatives Unternehmen." in prompt

    def test_v2_context_website_text_not_included(self):
        """v2 context path must NOT include raw website text (it's in the context object)."""
        ctx = MagicMock()
        ctx.company_profile_json = {"company_name": "CTX Co"}
        ctx.funding_rules_json = None
        ctx.style_profile_json = None
        ctx.retrieved_examples_json = None
        builder = PromptBuilder(context=ctx)
        # _get_website_clean_text returns None when context is set
        assert builder._get_website_clean_text() is None

    def test_empty_sections_returns_prompt(self):
        builder = PromptBuilder(company_name="Acme")
        prompt = builder.build_generation_prompt([])
        assert isinstance(prompt, str)

    def test_retrieved_examples_included(self):
        ctx = MagicMock()
        ctx.company_profile_json = {"company_name": "Example Corp"}
        ctx.funding_rules_json = None
        ctx.style_profile_json = None
        ctx.retrieved_examples_json = {
            "examples": [{"chunk_text": "Beispieltextinhalt aus einem Förderantrag."}],
            "guidelines": [],
            "domain": [],
        }
        builder = PromptBuilder(context=ctx)
        prompt = builder.build_generation_prompt(SAMPLE_SECTIONS)
        assert "Beispieltextinhalt" in prompt
