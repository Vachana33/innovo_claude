"""
Preprocessing utilities for company data.
Handles website crawling and audio transcription in the background.

Phase 2: Added caching support to ensure raw processing happens only once.
"""
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from typing import Optional
import logging

import os
from sqlalchemy.orm import Session
from openai import OpenAI

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def crawl_website(url: str, max_pages: int = 20, db: Optional[Session] = None) -> Optional[str]:
    """
    Crawl a website and extract readable text from pages.
    Limits to same domain and max_pages to avoid infinite crawling.

    Phase 2: Checks cache first. If cached result exists, returns it without crawling.

    Args:
        url: The website URL to crawl
        max_pages: Maximum number of pages to crawl (default: 20)
        db: Optional database session for cache lookup/storage

    Returns:
        Combined text from all crawled pages, or None if crawling fails
    """
    if not url:
        return None

    # Phase 2: Check cache first
    if db:
        try:
            from app.processing_cache import get_cached_website_text, store_website_text
            cached_text = get_cached_website_text(db, url)
            if cached_text:
                logger.info(f"[CACHE REUSE] Using cached website text for url={url}")
                return cached_text
        except Exception as cache_error:
            logger.warning(f"Cache lookup failed, proceeding with crawl: {str(cache_error)}")

    try:
        logger.info(f"[PROCESSING] Starting website crawl: url={url}, max_pages={max_pages}")
        # Ensure URL has a scheme
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        parsed_url = urlparse(url)
        base_domain = f"{parsed_url.scheme}://{parsed_url.netloc}"

        visited_urls = set()
        all_text = []

        def extract_text_from_page(page_url: str) -> Optional[str]:
            """Extract readable text from a single page."""
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                response = requests.get(page_url, headers=headers, timeout=10)
                response.raise_for_status()

                soup = BeautifulSoup(response.content, 'html.parser')

                # Remove script and style elements
                for script in soup(["script", "style", "nav", "footer", "header"]):
                    script.decompose()

                # Get text
                text = soup.get_text()

                # Clean up whitespace
                lines = (line.strip() for line in text.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                text = ' '.join(chunk for chunk in chunks if chunk)

                return text
            except Exception as e:
                logger.warning(f"Failed to extract text from {page_url}: {str(e)}")
                return None

        # Start with the main page
        queue = [url]
        visited_urls.add(url)

        while queue and len(visited_urls) <= max_pages:
            current_url = queue.pop(0)

            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                response = requests.get(current_url, headers=headers, timeout=10)
                response.raise_for_status()

                soup = BeautifulSoup(response.content, 'html.parser')

                # Extract text from current page
                page_text = extract_text_from_page(current_url)
                if page_text:
                    all_text.append(page_text)

                # Find links to other pages on the same domain
                if len(visited_urls) < max_pages:
                    for link in soup.find_all('a', href=True):
                        href = link['href']
                        absolute_url = urljoin(base_domain, href)
                        parsed_link = urlparse(absolute_url)

                        # Only follow links on the same domain
                        if (parsed_link.netloc == parsed_url.netloc and
                            absolute_url not in visited_urls and
                            len(visited_urls) < max_pages):
                            queue.append(absolute_url)
                            visited_urls.add(absolute_url)

            except Exception as e:
                logger.warning(f"Failed to crawl {current_url}: {str(e)}")
                continue

        # Combine all text
        combined_text = '\n\n'.join(all_text)
        if combined_text.strip():
            logger.info(f"[PROCESSING] Website crawl completed: url={url}, pages_crawled={len(visited_urls)}, text_length={len(combined_text)}")

            # Phase 2: Store in cache
            if db:
                try:
                    from app.processing_cache import store_website_text
                    store_website_text(db, url, combined_text)
                except Exception as cache_error:
                    logger.warning(f"Failed to store website text in cache: {str(cache_error)}")

            return combined_text
        else:
            logger.warning(f"Website crawl completed but no text extracted: url={url}")
            return None

    except Exception as e:
        logger.error(f"Website crawl error: url={url}, error={str(e)}")
        return None


def transcribe_audio(audio_path: str, file_content_hash: Optional[str] = None, db: Optional[Session] = None) -> Optional[str]:
    """
    Transcribe audio file to text using OpenAI Whisper API.

    Phase 2: Checks cache first by file_content_hash. If cached result exists, returns it without calling Whisper.

    Args:
        audio_path: Path to the audio file
        file_content_hash: Optional SHA256 hash of file content for cache lookup
        db: Optional database session for cache lookup/storage

    Returns:
        Transcript text, or None if transcription fails
    """
    if not audio_path:
        return None

    # Phase 2: Check cache first if content_hash is provided
    if file_content_hash and db:
        try:
            from app.processing_cache import get_cached_audio_transcript, store_audio_transcript
            cached_transcript = get_cached_audio_transcript(db, file_content_hash)
            if cached_transcript:
                logger.info(f"[CACHE REUSE] Using cached transcript for content_hash={file_content_hash[:16]}...")
                return cached_transcript
        except Exception as cache_error:
            logger.warning(f"Cache lookup failed, proceeding with transcription: {str(cache_error)}")

    try:
        logger.info(f"[PROCESSING] Starting audio transcription: audio_path={audio_path}")

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.error("OPENAI_API_KEY not found in environment")
            return None

        if not os.path.exists(audio_path):
            logger.error(f"Audio file does not exist: audio_path={audio_path}")
            return None

        # Note: OpenAI v1+ does not support proxies in constructor
        # Only pass api_key explicitly - do not pass proxies, http_client, or other proxy-related parameters
        client = OpenAI(api_key=api_key)

        with open(audio_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="de",
                timeout=300.0  # 5 minute timeout for audio transcription (can be longer)
            )

        transcript_text = transcript.text
        logger.info(f"[PROCESSING] Audio transcription completed: audio_path={audio_path}, transcript_length={len(transcript_text)}")

        # Phase 2: Store in cache if content_hash is provided
        if file_content_hash and db:
            try:
                from app.processing_cache import store_audio_transcript
                store_audio_transcript(db, file_content_hash, transcript_text)
            except Exception as cache_error:
                logger.warning(f"Failed to store transcript in cache: {str(cache_error)}")

        return transcript_text

    except Exception as e:
        logger.error(f"Audio transcription error: audio_path={audio_path}, error={str(e)}")
        return None

