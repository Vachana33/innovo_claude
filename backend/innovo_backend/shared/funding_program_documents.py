"""Funding Program Document Ingestion Utilities."""
import logging
import os

logger = logging.getLogger(__name__)

CATEGORY_KEYWORDS = {
    "guidelines": ["guideline", "guidelines"],
    "general_guidelines": ["general", "overview"],
    "application_companies": ["company", "companies", "research institution", "research institutions", "application process"],
    "knowledge_transfer": ["knowledge", "technology transfer", "transfer", "knowledge transfer"],
    "university_procedures": ["university", "universities", "procedure", "procedures"],
}

VALID_CATEGORIES = set(CATEGORY_KEYWORDS.keys())


def detect_category_from_filename(filename: str, folder_path: str = "") -> str:
    search_text = f"{folder_path} {filename}".lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in search_text:
                logger.info(f"Detected category '{category}' from filename/folder: {filename}")
                return category
    logger.info(f"No category match found for {filename}, defaulting to 'guidelines'")
    return "guidelines"


def validate_category(category: str) -> bool:
    return category in VALID_CATEGORIES


def get_file_type_from_filename(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower().lstrip(".")
    ext_map = {"pdf": "pdf", "docx": "docx", "doc": "docx", "txt": "txt", "text": "txt"}
    return ext_map.get(ext, ext if ext else "unknown")


def is_text_file(filename: str) -> bool:
    return get_file_type_from_filename(filename) == "txt"
