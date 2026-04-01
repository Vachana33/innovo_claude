"""
Text cleaning utilities for company content.
Performs noise removal and normalization without summarization or restructuring.
"""
import re
import logging

logger = logging.getLogger(__name__)

FILLER_WORDS = {
    "äh", "ähm", "also", "so", "halt", "eben", "eigentlich", "irgendwie",
    "quasi", "praktisch", "sowieso", "naja", "na", "hm", "hmm",
    "um", "uh", "er", "ah", "like", "you know", "well", "so", "actually",
    "basically", "literally", "kind of", "sort of",
}

NAVIGATION_PATTERNS = [
    r"cookie.*policy", r"privacy.*policy", r"terms.*of.*service",
    r"imprint", r"impressum", r"datenschutz", r"agb",
    r"copyright.*\d{4}", r"©.*\d{4}", r"all rights reserved",
    r"alle rechte vorbehalten", r"skip to content", r"skip to main",
    r"menu", r"navigation", r"home", r"startseite",
]


def clean_transcript(raw_transcript: str) -> str:
    if not raw_transcript:
        return ""
    text = raw_transcript
    for filler in FILLER_WORDS:
        pattern = r"\b" + re.escape(filler) + r"\b"
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(äh|ähm|um|uh|er|ah)\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r" +", " ", text)
    lines = [line.strip() for line in text.split("\n")]
    lines = [line for line in lines if line]
    text = "\n".join(lines)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def clean_website_text(raw_text: str) -> str:
    if not raw_text:
        return ""
    text = raw_text
    paragraphs = text.split("\n\n")
    cleaned_paragraphs = []
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        para_lower = para.lower()
        is_boilerplate = False
        for pattern in NAVIGATION_PATTERNS:
            if re.search(pattern, para_lower, re.IGNORECASE):
                is_boilerplate = True
                break
        if len(para) < 20 and para_lower in [
            "home", "about", "contact", "services", "products",
            "startseite", "über uns", "kontakt", "leistungen", "produkte",
        ]:
            is_boilerplate = True
        if para.count("|") > 2 or para.count("•") > 3:
            is_boilerplate = True
        if not is_boilerplate:
            cleaned_paragraphs.append(para)
    text = "\n\n".join(cleaned_paragraphs)
    lines = text.split("\n")
    seen_lines: set = set()
    unique_lines = []
    for line in lines:
        line_stripped = line.strip().lower()
        if line_stripped and line_stripped not in seen_lines:
            seen_lines.add(line_stripped)
            unique_lines.append(line)
        elif not line_stripped:
            unique_lines.append(line)
    text = "\n".join(unique_lines)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
