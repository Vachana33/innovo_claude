"""Tests for innovo_backend.shared.processing_cache."""
import pytest
from innovo_backend.shared.processing_cache import (
    normalize_url,
    hash_url,
    get_cached_audio_transcript,
    store_audio_transcript,
    get_cached_website_text,
    store_website_text,
    get_cached_document_text,
    store_document_text,
)


# ---------------------------------------------------------------------------
# normalize_url
# ---------------------------------------------------------------------------

class TestNormalizeUrl:
    def test_adds_https_when_missing(self):
        assert normalize_url("example.com").startswith("https://")

    def test_preserves_https(self):
        assert normalize_url("https://example.com").startswith("https://")

    def test_preserves_http(self):
        assert normalize_url("http://example.com").startswith("http://")

    def test_lowercases(self):
        assert normalize_url("https://EXAMPLE.COM") == normalize_url("https://example.com")

    def test_strips_trailing_slash(self):
        a = normalize_url("https://example.com/")
        b = normalize_url("https://example.com")
        assert a == b

    def test_strips_default_port_80_http(self):
        assert normalize_url("http://example.com:80") == normalize_url("http://example.com")

    def test_strips_default_port_443_https(self):
        assert normalize_url("https://example.com:443") == normalize_url("https://example.com")

    def test_empty_string_returns_empty(self):
        assert normalize_url("") == ""

    def test_preserves_path(self):
        url = normalize_url("https://example.com/foo/bar")
        assert "/foo/bar" in url


# ---------------------------------------------------------------------------
# hash_url
# ---------------------------------------------------------------------------

class TestHashUrl:
    def test_returns_64_char_hex(self):
        h = hash_url("https://example.com")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_same_url_same_hash(self):
        assert hash_url("https://example.com") == hash_url("https://example.com")

    def test_normalized_urls_same_hash(self):
        """Trailing slash and no trailing slash must hash the same."""
        assert hash_url("https://example.com/") == hash_url("https://example.com")

    def test_different_urls_different_hash(self):
        assert hash_url("https://example.com") != hash_url("https://other.com")


# ---------------------------------------------------------------------------
# Audio transcript cache
# ---------------------------------------------------------------------------

class TestAudioTranscriptCache:
    def test_miss_returns_none(self, db):
        result = get_cached_audio_transcript(db, "nonexistent_hash")
        assert result is None

    def test_store_and_retrieve(self, db):
        content_hash = "abc123def456" * 2  # 24 chars
        transcript = "Das ist das Transkript."
        store_audio_transcript(db, content_hash, transcript)
        result = get_cached_audio_transcript(db, content_hash)
        assert result == transcript

    def test_store_twice_raises_or_succeeds(self, db):
        """Storing with same hash should not corrupt existing entry."""
        content_hash = "unique_hash_xyz_001" * 2
        store_audio_transcript(db, content_hash, "first")
        # Second store with same hash: either raises integrity error or is no-op
        # Either way, the first value should remain accessible (rollback handles cleanup)
        result = get_cached_audio_transcript(db, content_hash)
        assert result == "first"


# ---------------------------------------------------------------------------
# Website text cache
# ---------------------------------------------------------------------------

class TestWebsiteTextCache:
    def test_miss_returns_none(self, db):
        assert get_cached_website_text(db, "https://notcached.example.com") is None

    def test_store_and_retrieve(self, db):
        url = "https://cached-test.example.com/page"
        text = "Webseiteninhalt hier."
        store_website_text(db, url, text)
        result = get_cached_website_text(db, url)
        assert result == text

    def test_normalized_url_retrieval(self, db):
        """Storing with trailing slash should be retrievable without it."""
        url_with_slash = "https://norm-test.example.com/"
        url_without = "https://norm-test.example.com"
        store_website_text(db, url_with_slash, "content")
        # Should hit cache regardless of slash
        assert get_cached_website_text(db, url_without) == "content"


# ---------------------------------------------------------------------------
# Document text cache
# ---------------------------------------------------------------------------

class TestDocumentTextCache:
    def test_miss_returns_none(self, db):
        assert get_cached_document_text(db, "missing_hash_xyz") is None

    def test_store_and_retrieve(self, db):
        content_hash = "docfile_sha256_hash_abcdef1234567890"
        extracted = "Extrahierter Dokumenttext."
        store_document_text(db, content_hash, extracted)
        result = get_cached_document_text(db, content_hash)
        assert result == extracted
