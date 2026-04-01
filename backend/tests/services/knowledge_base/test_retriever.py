"""Tests for innovo_backend.services.knowledge_base.retriever."""
import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# retrieve_kb_context
# ---------------------------------------------------------------------------

class TestRetrieveKbContext:
    def test_returns_dict_with_expected_keys(self, db):
        from innovo_backend.services.knowledge_base.retriever import retrieve_kb_context

        # With no chunks in DB, should return empty lists gracefully
        result = retrieve_kb_context(
            db=db,
            query_text="Förderantrag für KI-Projekt",
            program_tag="ZIM",
        )
        assert isinstance(result, dict)
        assert "examples" in result
        assert "guidelines" in result
        assert "domain" in result

    def test_returns_lists(self, db):
        from innovo_backend.services.knowledge_base.retriever import retrieve_kb_context

        result = retrieve_kb_context(db=db, query_text="test query", program_tag=None)
        assert isinstance(result["examples"], list)
        assert isinstance(result["guidelines"], list)
        assert isinstance(result["domain"], list)

    def test_empty_db_returns_empty_lists(self, db):
        from innovo_backend.services.knowledge_base.retriever import retrieve_kb_context

        result = retrieve_kb_context(db=db, query_text="irrelevant query", program_tag="NONEXISTENT")
        assert result["examples"] == []
        assert result["guidelines"] == []
        assert result["domain"] == []


# ---------------------------------------------------------------------------
# scraper._split_text
# ---------------------------------------------------------------------------

class TestSplitText:
    def test_splits_long_text_into_chunks(self):
        from innovo_backend.services.knowledge_base.scraper import _split_text

        long_text = "A" * 5000
        chunks = _split_text(long_text)
        assert len(chunks) > 1

    def test_short_text_returns_one_chunk(self):
        from innovo_backend.services.knowledge_base.scraper import _split_text

        short = "This is a short text."
        chunks = _split_text(short)
        assert len(chunks) == 1
        assert chunks[0] == short

    def test_empty_text_returns_empty_list(self):
        from innovo_backend.services.knowledge_base.scraper import _split_text

        assert _split_text("") == []

    def test_chunks_max_size(self):
        from innovo_backend.services.knowledge_base.scraper import _split_text, _CHUNK_SIZE

        text = ("X" * (_CHUNK_SIZE + 100) + "\n\n") * 3
        chunks = _split_text(text)
        for chunk in chunks:
            assert len(chunk) <= _CHUNK_SIZE + 50  # small tolerance for paragraph boundary


# ---------------------------------------------------------------------------
# scraper._sha256
# ---------------------------------------------------------------------------

class TestSha256:
    def test_returns_64_char_hex(self):
        from innovo_backend.services.knowledge_base.scraper import _sha256

        result = _sha256("some text")
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_same_input_same_hash(self):
        from innovo_backend.services.knowledge_base.scraper import _sha256

        assert _sha256("hello") == _sha256("hello")

    def test_different_input_different_hash(self):
        from innovo_backend.services.knowledge_base.scraper import _sha256

        assert _sha256("hello") != _sha256("world")
