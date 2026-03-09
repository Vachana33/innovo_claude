"""
Phase 4: Funding Program Document Ingestion Utilities

Category detection and document organization utilities.
"""
import logging
import os


logger = logging.getLogger(__name__)

# Category keywords for automatic detection
CATEGORY_KEYWORDS = {
    "guidelines": ["guideline", "guidelines"],
    "general_guidelines": ["general", "overview"],
    "application_companies": ["company", "companies", "research institution", "research institutions", "application process"],
    "knowledge_transfer": ["knowledge", "technology transfer", "transfer", "knowledge transfer"],
    "university_procedures": ["university", "universities", "procedure", "procedures"]
}

VALID_CATEGORIES = set(CATEGORY_KEYWORDS.keys())


def detect_category_from_filename(filename: str, folder_path: str = "") -> str:
    """
    Detect category from filename or folder path.
    Falls back to 'general_guidelines' if no match.

    Args:
        filename: Original filename
        folder_path: Optional folder path (e.g., "general_guidelines/doc.pdf")

    Returns:
        Category string (one of VALID_CATEGORIES)
    """
    # Normalize to lowercase for matching
    search_text = f"{folder_path} {filename}".lower()

    # Check each category's keywords
    for category, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in search_text:
                logger.info(f"Detected category '{category}' from filename/folder: {filename} (folder: {folder_path})")
                return category

    # Default fallback
    logger.info(f"No category match found for {filename}, defaulting to 'guidelines'")
    return "guidelines"


def validate_category(category: str) -> bool:
    """
    Validate that a category is one of the allowed values.

    Args:
        category: Category string to validate

    Returns:
        True if valid, False otherwise
    """
    return category in VALID_CATEGORIES


def get_file_type_from_filename(filename: str) -> str:
    """
    Determine file type from filename extension.

    Args:
        filename: Original filename

    Returns:
        File type string ("pdf", "docx", "txt", etc.)
    """
    ext = os.path.splitext(filename)[1].lower().lstrip('.')

    # Map common extensions
    ext_map = {
        "pdf": "pdf",
        "docx": "docx",
        "doc": "docx",  # Treat .doc as docx
        "txt": "txt",
        "text": "txt"
    }

    return ext_map.get(ext, ext if ext else "unknown")


def is_text_file(filename: str) -> bool:
    """
    Check if file is a text file based on extension.

    Args:
        filename: Original filename

    Returns:
        True if text file, False otherwise
    """
    file_type = get_file_type_from_filename(filename)
    return file_type == "txt"
