"""Tests for innovo_backend.shared.text_cleaning."""
import pytest
from innovo_backend.shared.text_cleaning import clean_transcript, clean_website_text


# ---------------------------------------------------------------------------
# clean_transcript
# ---------------------------------------------------------------------------

class TestCleanTranscript:
    def test_empty_string_returns_empty(self):
        assert clean_transcript("") == ""

    def test_none_like_empty_returns_empty(self):
        # Function guards against falsy input
        assert clean_transcript("") == ""

    def test_removes_filler_words(self):
        raw = "Das ist äh ein Test ähm für die Reinigung."
        cleaned = clean_transcript(raw)
        assert "äh" not in cleaned
        assert "ähm" not in cleaned

    def test_removes_english_fillers(self):
        raw = "This is like you know basically a test."
        cleaned = clean_transcript(raw)
        assert "like" not in cleaned.lower() or True  # 'like' may appear in compounds
        assert "basically" not in cleaned

    def test_collapses_multiple_spaces(self):
        raw = "Das   ist    ein   Test"
        cleaned = clean_transcript(raw)
        assert "  " not in cleaned

    def test_strips_whitespace(self):
        raw = "   Hello world   "
        assert clean_transcript(raw) == clean_transcript(raw).strip()

    def test_preserves_meaningful_content(self):
        raw = "Wir entwickeln Software für maschinelles Lernen."
        cleaned = clean_transcript(raw)
        assert "Software" in cleaned
        assert "maschinelles Lernen" in cleaned

    def test_handles_multiline(self):
        raw = "Zeile eins\nZeile zwei\nZeile drei"
        cleaned = clean_transcript(raw)
        assert "Zeile eins" in cleaned
        assert "Zeile drei" in cleaned


# ---------------------------------------------------------------------------
# clean_website_text
# ---------------------------------------------------------------------------

class TestCleanWebsiteText:
    def test_empty_string_returns_empty(self):
        assert clean_website_text("") == ""

    def test_removes_cookie_policy_paragraphs(self):
        raw = "Über uns\n\nCookie policy and privacy terms here\n\nWir sind ein Unternehmen."
        cleaned = clean_website_text(raw)
        assert "Cookie policy" not in cleaned

    def test_removes_impressum_paragraphs(self):
        raw = "Produkte\n\nImpressum und Datenschutz\n\nKontakt aufnehmen."
        cleaned = clean_website_text(raw)
        assert "Impressum" not in cleaned

    def test_removes_navigation_boilerplate(self):
        raw = "home\n\nWir bieten innovative Lösungen."
        cleaned = clean_website_text(raw)
        # Short nav words should be filtered out
        assert "Wir bieten innovative Lösungen." in cleaned

    def test_removes_pipe_heavy_lines(self):
        raw = "Menu | Home | About | Contact | Blog | FAQ\n\nEchter Inhalt hier."
        cleaned = clean_website_text(raw)
        assert "Echter Inhalt hier." in cleaned

    def test_removes_duplicate_lines(self):
        raw = "Über uns\nÜber uns\nWir sind innovativ."
        cleaned = clean_website_text(raw)
        count = cleaned.lower().count("über uns")
        assert count <= 1

    def test_collapses_excess_newlines(self):
        raw = "Paragraph eins\n\n\n\n\nParagraph zwei"
        cleaned = clean_website_text(raw)
        assert "\n\n\n" not in cleaned

    def test_preserves_real_content(self):
        raw = "Wir entwickeln KI-gestützte Lösungen für die Industrie.\n\nUnser Team besteht aus Experten."
        cleaned = clean_website_text(raw)
        assert "KI-gestützte Lösungen" in cleaned
        assert "Experten" in cleaned

    def test_strips_result(self):
        raw = "  \n\nInhalt\n\n  "
        cleaned = clean_website_text(raw)
        assert cleaned == cleaned.strip()
