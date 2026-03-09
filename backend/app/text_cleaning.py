"""
Text cleaning utilities for company content.
Performs noise removal and normalization without summarization or restructuring.
"""
import re
import logging

logger = logging.getLogger(__name__)

# Common filler words (German and English)
FILLER_WORDS = {
    # German
    "äh", "ähm", "also", "so", "halt", "eben", "eigentlich", "irgendwie",
    "quasi", "praktisch", "sowieso", "naja", "na", "hm", "hmm",
    # English
    "um", "uh", "er", "ah", "like", "you know", "well", "so", "actually",
    "basically", "literally", "kind of", "sort of"
}

# Common navigation/boilerplate patterns
NAVIGATION_PATTERNS = [
    r"cookie.*policy",
    r"privacy.*policy",
    r"terms.*of.*service",
    r"imprint",
    r"impressum",
    r"datenschutz",
    r"agb",
    r"copyright.*\d{4}",
    r"©.*\d{4}",
    r"all rights reserved",
    r"alle rechte vorbehalten",
    r"skip to content",
    r"skip to main",
    r"menu",
    r"navigation",
    r"home",
    r"startseite",
]

def clean_transcript(raw_transcript: str) -> str:
    """
    Clean transcript by removing filler words and normalizing spacing.
    
    Args:
        raw_transcript: Raw transcript text from Whisper
        
    Returns:
        Cleaned transcript with filler words removed and normalized spacing
    """
    if not raw_transcript:
        return ""
    
    # Convert to lowercase for pattern matching, but preserve original case structure
    text = raw_transcript
    
    # Remove filler words (case-insensitive, whole word only)
    for filler in FILLER_WORDS:
        # Match whole words only (with word boundaries)
        pattern = r'\b' + re.escape(filler) + r'\b'
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    
    # Remove obvious speech artifacts
    text = re.sub(r'\b(äh|ähm|um|uh|er|ah)\b', '', text, flags=re.IGNORECASE)
    
    # Normalize spacing: multiple spaces to single space
    text = re.sub(r' +', ' ', text)
    
    # Remove leading/trailing whitespace from each line
    lines = [line.strip() for line in text.split('\n')]
    
    # Remove empty lines
    lines = [line for line in lines if line]
    
    # Join lines back
    text = '\n'.join(lines)
    
    # Final whitespace normalization
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text


def clean_website_text(raw_text: str) -> str:
    """
    Clean website text by removing navigation, boilerplate, and legal text.
    Preserves paragraph structure.
    
    Args:
        raw_text: Raw extracted website text
        
    Returns:
        Cleaned text with navigation/boilerplate removed
    """
    if not raw_text:
        return ""
    
    text = raw_text
    
    # Split into paragraphs (preserve structure)
    paragraphs = text.split('\n\n')
    cleaned_paragraphs = []
    
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        
        # Skip paragraphs that match navigation/boilerplate patterns
        para_lower = para.lower()
        is_boilerplate = False
        
        for pattern in NAVIGATION_PATTERNS:
            if re.search(pattern, para_lower, re.IGNORECASE):
                is_boilerplate = True
                break
        
        # Skip very short paragraphs that are likely navigation items
        if len(para) < 20 and para_lower in ["home", "about", "contact", "services", "products", 
                                               "startseite", "über uns", "kontakt", "leistungen", "produkte"]:
            is_boilerplate = True
        
        # Skip paragraphs that are mostly links or navigation
        if para.count('|') > 2 or para.count('•') > 3:
            is_boilerplate = True
        
        if not is_boilerplate:
            cleaned_paragraphs.append(para)
    
    # Join paragraphs back
    text = '\n\n'.join(cleaned_paragraphs)
    
    # Remove repeated boilerplate elements (same text appearing multiple times)
    lines = text.split('\n')
    seen_lines = set()
    unique_lines = []
    for line in lines:
        line_stripped = line.strip().lower()
        if line_stripped and line_stripped not in seen_lines:
            seen_lines.add(line_stripped)
            unique_lines.append(line)
        elif not line_stripped:
            unique_lines.append(line)  # Keep empty lines for structure
    
    text = '\n'.join(unique_lines)
    
    # Normalize whitespace (multiple spaces to single, but preserve line breaks)
    text = re.sub(r'[ \t]+', ' ', text)  # Multiple spaces/tabs to single space
    text = re.sub(r'\n{3,}', '\n\n', text)  # Multiple newlines to double
    
    # Remove leading/trailing whitespace
    text = text.strip()
    
    return text
