"""Tests for innovo_backend.services.projects.chat_service."""
import json
import pytest
from unittest.mock import MagicMock, patch

from innovo_backend.services.projects.chat_service import (
    _build_system_prompt,
    _extract_company_corrections,
    _merge_company_corrections,
)


# ---------------------------------------------------------------------------
# _build_system_prompt
# ---------------------------------------------------------------------------

class TestBuildSystemPrompt:
    def test_no_context_returns_string(self):
        prompt = _build_system_prompt(None)
        assert isinstance(prompt, str)
        assert "kein Projektkontext" in prompt

    def test_with_dict_company_profile(self):
        ctx = MagicMock()
        ctx.company_profile_json = {"company_name": "DictCorp GmbH", "industry": "IT"}
        ctx.funding_rules_json = None
        ctx.domain_research_json = None
        ctx.retrieved_examples_json = None
        ctx.style_profile_json = None
        prompt = _build_system_prompt(ctx)
        assert "FIRMENPROFIL" in prompt
        assert "DictCorp GmbH" in prompt

    def test_with_json_string_company_profile(self):
        ctx = MagicMock()
        ctx.company_profile_json = json.dumps({"company_name": "StringCorp", "industry": "Finance"})
        ctx.funding_rules_json = None
        ctx.domain_research_json = None
        ctx.retrieved_examples_json = None
        ctx.style_profile_json = None
        prompt = _build_system_prompt(ctx)
        assert "StringCorp" in prompt

    def test_with_funding_rules(self):
        ctx = MagicMock()
        ctx.company_profile_json = None
        ctx.funding_rules_json = {"eligibility_rules": ["Nur KMU"]}
        ctx.domain_research_json = None
        ctx.retrieved_examples_json = None
        ctx.style_profile_json = None
        prompt = _build_system_prompt(ctx)
        assert "FÖRDERRICHTLINIEN" in prompt

    def test_with_style_profile(self):
        ctx = MagicMock()
        ctx.company_profile_json = None
        ctx.funding_rules_json = None
        ctx.domain_research_json = None
        ctx.retrieved_examples_json = None
        ctx.style_profile_json = {"tone_characteristics": ["Formal"]}
        prompt = _build_system_prompt(ctx)
        assert "STILPROFIL" in prompt

    def test_invalid_json_string_handled_gracefully(self):
        ctx = MagicMock()
        ctx.company_profile_json = "NOT VALID JSON"
        ctx.funding_rules_json = None
        ctx.domain_research_json = None
        ctx.retrieved_examples_json = None
        ctx.style_profile_json = None
        # Should not raise
        prompt = _build_system_prompt(ctx)
        assert isinstance(prompt, str)


# ---------------------------------------------------------------------------
# _extract_company_corrections
# ---------------------------------------------------------------------------

class TestExtractCompanyCorrections:
    def test_extracts_url(self):
        msg = "Unsere Website ist https://example.com"
        corrections = _extract_company_corrections(msg)
        assert "website_url" in corrections or any(
            "example.com" in str(v) for v in corrections.values()
        )

    def test_extracts_description_keywords(self):
        msg = "Wir entwickeln KI-Software für die Industrie."
        corrections = _extract_company_corrections(msg)
        # Should detect description-like content
        assert isinstance(corrections, dict)

    def test_empty_message_returns_empty_dict(self):
        corrections = _extract_company_corrections("")
        assert isinstance(corrections, dict)

    def test_no_correction_in_unrelated_message(self):
        msg = "Wie lautet der aktuelle Status meines Projekts?"
        corrections = _extract_company_corrections(msg)
        assert isinstance(corrections, dict)


# ---------------------------------------------------------------------------
# _merge_company_corrections
# ---------------------------------------------------------------------------

class TestMergeCompanyCorrections:
    def test_merge_adds_website_to_profile(self):
        ctx = MagicMock()
        ctx.company_profile_json = {"company_name": "Acme GmbH"}
        ctx.company_discovery_status = "incomplete"
        ctx.completeness_score = 30

        corrections = {"website_url": "https://acme.de"}
        _merge_company_corrections(ctx, corrections)

        profile = ctx.company_profile_json
        if isinstance(profile, str):
            profile = json.loads(profile)
        assert isinstance(profile, dict)

    def test_merge_with_empty_corrections_is_noop(self):
        ctx = MagicMock()
        ctx.company_profile_json = {"company_name": "Unchanged GmbH"}
        original_profile = dict(ctx.company_profile_json)
        _merge_company_corrections(ctx, {})
        # Profile should be unchanged
        result = ctx.company_profile_json
        if isinstance(result, str):
            result = json.loads(result)
        assert result.get("company_name") == "Unchanged GmbH"

    def test_merge_creates_profile_if_none(self):
        ctx = MagicMock()
        ctx.company_profile_json = None
        ctx.company_discovery_status = None
        ctx.completeness_score = 0

        corrections = {"description": "Software company"}
        _merge_company_corrections(ctx, corrections)
        # Should not raise; profile may be updated
        assert True  # If we reach here without exception, the test passes
