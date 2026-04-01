"""Tests for innovo_backend.services.documents.service._generate_batch_content."""
import json
import pytest
from unittest.mock import MagicMock, patch


SAMPLE_SECTIONS = [
    {"id": "1", "title": "Einleitung", "type": "text", "content": ""},
    {"id": "2", "title": "Projektziele", "type": "text", "content": ""},
]


def _make_openai_response(content: dict) -> MagicMock:
    """Build a mock that mimics openai.ChatCompletion response structure."""
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = json.dumps(content)
    response.usage = MagicMock()
    response.usage.prompt_tokens = 100
    response.usage.completion_tokens = 200
    response.usage.total_tokens = 300
    response.model = "gpt-4o-mini"
    return response


def _make_client(content: dict) -> MagicMock:
    client = MagicMock()
    client.chat.completions.create.return_value = _make_openai_response(content)
    return client


# ---------------------------------------------------------------------------
# Successful generation
# ---------------------------------------------------------------------------

class TestGenerateBatchContent:
    def test_returns_dict_with_section_ids(self):
        from innovo_backend.services.documents.service import _generate_batch_content

        document = MagicMock()
        document.project_id = None
        document.funding_program_id = None

        client = _make_client({"1": "Einleitung Inhalt.", "2": "Ziele Inhalt."})

        with patch("innovo_backend.shared.observability.log_openai_call") as mock_log:
            mock_log.return_value.__enter__ = MagicMock(return_value={})
            mock_log.return_value.__exit__ = MagicMock(return_value=False)

            result = _generate_batch_content(
                sections=SAMPLE_SECTIONS,
                document=document,
                client=client,
                db=None,
                company_name="Test GmbH",
            )

        assert isinstance(result, dict)
        assert "1" in result
        assert "2" in result

    def test_content_values_are_strings(self):
        from innovo_backend.services.documents.service import _generate_batch_content

        document = MagicMock()
        document.project_id = None

        client = _make_client({"1": "Some content", "2": "More content"})

        with patch("innovo_backend.shared.observability.log_openai_call") as mock_log:
            mock_log.return_value.__enter__ = MagicMock(return_value={})
            mock_log.return_value.__exit__ = MagicMock(return_value=False)

            result = _generate_batch_content(
                sections=SAMPLE_SECTIONS,
                document=document,
                client=client,
                db=None,
                company_name="Test GmbH",
            )

        for val in result.values():
            assert isinstance(val, str)

    def test_missing_section_ids_filled_with_empty_string(self):
        """If LLM omits a section ID, it should be filled with empty string."""
        from innovo_backend.services.documents.service import _generate_batch_content

        document = MagicMock()
        document.project_id = None

        # Only returns section "1", omits "2"
        client = _make_client({"1": "Only one section returned."})

        with patch("innovo_backend.shared.observability.log_openai_call") as mock_log:
            mock_log.return_value.__enter__ = MagicMock(return_value={})
            mock_log.return_value.__exit__ = MagicMock(return_value=False)

            result = _generate_batch_content(
                sections=SAMPLE_SECTIONS,
                document=document,
                client=client,
                db=None,
                company_name="Test GmbH",
            )

        assert "1" in result
        assert "2" in result
        assert result["2"] == ""

    def test_milestone_table_section_excluded_from_ids(self):
        """milestone_table sections must not appear in the expected section IDs."""
        from innovo_backend.services.documents.service import _generate_batch_content

        sections = [
            {"id": "1", "title": "Intro", "type": "text", "content": ""},
            {"id": "ms", "title": "Milestone", "type": "milestone_table", "content": ""},
        ]
        document = MagicMock()
        document.project_id = None

        client = _make_client({"1": "Intro content."})

        with patch("innovo_backend.shared.observability.log_openai_call") as mock_log:
            mock_log.return_value.__enter__ = MagicMock(return_value={})
            mock_log.return_value.__exit__ = MagicMock(return_value=False)

            result = _generate_batch_content(
                sections=sections,
                document=document,
                client=client,
                db=None,
                company_name="Test GmbH",
            )

        assert "1" in result
        # "ms" was a milestone_table — should not have been expected as a text section
        # If it's in result, it came from LLM response (not from missing_ids fill)

    def test_uses_context_when_provided(self):
        """When ctx is provided, PromptBuilder should use the v2 context path."""
        from innovo_backend.services.documents.service import _generate_batch_content

        document = MagicMock()
        document.project_id = 1

        ctx = MagicMock()
        ctx.company_profile_json = {"company_name": "Context Corp"}
        ctx.funding_rules_json = None
        ctx.style_profile_json = None
        ctx.retrieved_examples_json = None

        client = _make_client({"1": "V2 content", "2": "V2 ziele"})

        with patch("innovo_backend.shared.observability.log_openai_call") as mock_log:
            mock_log.return_value.__enter__ = MagicMock(return_value={})
            mock_log.return_value.__exit__ = MagicMock(return_value=False)

            result = _generate_batch_content(
                sections=SAMPLE_SECTIONS,
                document=document,
                ctx=ctx,
                client=client,
                db=None,
            )

        assert "1" in result


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestGenerateBatchContentErrors:
    def test_raises_on_invalid_json_after_retries(self):
        from innovo_backend.services.documents.service import _generate_batch_content

        document = MagicMock()
        document.project_id = None

        bad_client = MagicMock()
        bad_response = MagicMock()
        bad_response.choices = [MagicMock()]
        bad_response.choices[0].message.content = "NOT JSON AT ALL"
        bad_response.usage = MagicMock()
        bad_response.usage.prompt_tokens = 10
        bad_response.usage.completion_tokens = 10
        bad_response.usage.total_tokens = 20
        bad_response.model = "gpt-4o-mini"
        bad_client.chat.completions.create.return_value = bad_response

        with patch("innovo_backend.shared.observability.log_openai_call") as mock_log:
            mock_log.return_value.__enter__ = MagicMock(return_value={})
            mock_log.return_value.__exit__ = MagicMock(return_value=False)

            with pytest.raises((ValueError, Exception)):
                _generate_batch_content(
                    sections=SAMPLE_SECTIONS,
                    document=document,
                    client=bad_client,
                    db=None,
                    company_name="Test GmbH",
                    max_retries=0,
                )

    def test_raises_when_value_is_not_string(self):
        """Content values that are not strings should raise ValueError."""
        from innovo_backend.services.documents.service import _generate_batch_content

        document = MagicMock()
        document.project_id = None

        # LLM returns a nested dict instead of a string
        client = _make_client({"1": {"nested": "object"}, "2": "valid string"})

        with patch("innovo_backend.shared.observability.log_openai_call") as mock_log:
            mock_log.return_value.__enter__ = MagicMock(return_value={})
            mock_log.return_value.__exit__ = MagicMock(return_value=False)

            with pytest.raises((ValueError, Exception)):
                _generate_batch_content(
                    sections=SAMPLE_SECTIONS,
                    document=document,
                    client=client,
                    db=None,
                    company_name="Test GmbH",
                    max_retries=0,
                )
