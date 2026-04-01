"""Tests for innovo_backend.shared.funding_program_documents."""
import pytest
from innovo_backend.shared.funding_program_documents import (
    detect_category_from_filename,
    validate_category,
    get_file_type_from_filename,
    is_text_file,
    VALID_CATEGORIES,
)


# ---------------------------------------------------------------------------
# detect_category_from_filename
# ---------------------------------------------------------------------------

class TestDetectCategoryFromFilename:
    def test_detects_guidelines_from_filename(self):
        result = detect_category_from_filename("funding_guidelines_2025.pdf")
        assert result == "guidelines"

    def test_detects_general_from_filename(self):
        result = detect_category_from_filename("general_overview.pdf")
        assert result == "general_guidelines"

    def test_detects_company_from_filename(self):
        result = detect_category_from_filename("company_application_form.pdf")
        assert result == "application_companies"

    def test_detects_knowledge_from_filename(self):
        result = detect_category_from_filename("knowledge_transfer_program.pdf")
        assert result == "knowledge_transfer"

    def test_detects_university_from_filename(self):
        result = detect_category_from_filename("university_procedures.pdf")
        assert result == "university_procedures"

    def test_defaults_to_guidelines_when_no_match(self):
        result = detect_category_from_filename("random_document.pdf")
        assert result == "guidelines"

    def test_uses_folder_path_in_detection(self):
        result = detect_category_from_filename("document.pdf", folder_path="university")
        assert result == "university_procedures"

    def test_case_insensitive(self):
        result = detect_category_from_filename("GUIDELINES_DOCUMENT.PDF")
        assert result == "guidelines"


# ---------------------------------------------------------------------------
# validate_category
# ---------------------------------------------------------------------------

class TestValidateCategory:
    def test_valid_categories_pass(self):
        for cat in VALID_CATEGORIES:
            assert validate_category(cat) is True

    def test_invalid_category_fails(self):
        assert validate_category("nonexistent_category") is False

    def test_empty_string_fails(self):
        assert validate_category("") is False

    def test_case_sensitive(self):
        assert validate_category("Guidelines") is False  # must be lowercase


# ---------------------------------------------------------------------------
# get_file_type_from_filename
# ---------------------------------------------------------------------------

class TestGetFileTypeFromFilename:
    def test_pdf_extension(self):
        assert get_file_type_from_filename("document.pdf") == "pdf"

    def test_docx_extension(self):
        assert get_file_type_from_filename("document.docx") == "docx"

    def test_doc_extension_mapped_to_docx(self):
        assert get_file_type_from_filename("document.doc") == "docx"

    def test_txt_extension(self):
        assert get_file_type_from_filename("notes.txt") == "txt"

    def test_text_extension(self):
        assert get_file_type_from_filename("notes.text") == "txt"

    def test_uppercase_extension(self):
        assert get_file_type_from_filename("DOCUMENT.PDF") == "pdf"

    def test_no_extension_returns_unknown(self):
        assert get_file_type_from_filename("nodotfile") == "unknown"


# ---------------------------------------------------------------------------
# is_text_file
# ---------------------------------------------------------------------------

class TestIsTextFile:
    def test_txt_is_text_file(self):
        assert is_text_file("notes.txt") is True

    def test_pdf_is_not_text_file(self):
        assert is_text_file("document.pdf") is False

    def test_docx_is_not_text_file(self):
        assert is_text_file("report.docx") is False
