"""
Website scraping utilities for company About pages.
Scrapes only the About page (or common variants) to extract company information.
"""
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from typing import Optional
import logging
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Common About page paths to try
ABOUT_PATHS = [
    "/about",
    "/about-us",
    "/company",
    "/unternehmen",
    "/ueber-uns",
    "/about/",
    "/about-us/",
    "/company/",
    "/unternehmen/",
    "/ueber-uns/",
]

def scrape_about_page(url: str, db: Optional[Session] = None) -> tuple[Optional[str], Optional[str]]:
    """
    Scrape only the About page from a website.
    Tries common About page paths: /about, /about-us, /company, /unternehmen
    
    Args:
        url: The website URL
        db: Optional database session for cache lookup/storage
        
    Returns:
        Tuple of (raw_text, clean_text) or (None, None) if scraping fails
    """
    if not url:
        return None, None
    
    # Check cache first if db session provided
    if db:
        try:
            from app.processing_cache import get_cached_website_text
            cached_text = get_cached_website_text(db, url)
            if cached_text:
                logger.info(f"[CACHE REUSE] Using cached website text for url={url}")
                # Return cached text as both raw and clean (will be cleaned separately)
                return cached_text, cached_text
        except Exception as cache_error:
            logger.warning(f"Cache lookup failed, proceeding with scrape: {str(cache_error)}")
    
    try:
        # Ensure URL has a scheme
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        parsed_url = urlparse(url)
        base_domain = f"{parsed_url.scheme}://{parsed_url.netloc}"
        
        # Try each About page path
        about_url = None
        for path in ABOUT_PATHS:
            test_url = urljoin(base_domain, path)
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                response = requests.get(test_url, headers=headers, timeout=10, allow_redirects=True)
                if response.status_code == 200:
                    about_url = response.url  # Use final URL after redirects
                    logger.info(f"Found About page at: {about_url}")
                    break
            except Exception as e:
                logger.debug(f"Failed to access {test_url}: {str(e)}")
                continue
        
        # If no About page found, try the main page
        if not about_url:
            logger.info(f"No About page found, trying main page: {url}")
            about_url = url
        
        # Scrape the found page
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(about_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove script, style, nav, footer, header elements
        for element in soup(["script", "style", "nav", "footer", "header"]):
            element.decompose()
        
        # Get text
        raw_text = soup.get_text()
        
        # Basic whitespace normalization for raw text
        lines = (line.strip() for line in raw_text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        raw_text = '\n'.join(chunk for chunk in chunks if chunk)
        
        if raw_text.strip():
            logger.info(f"[PROCESSING] Website scrape completed: url={about_url}, text_length={len(raw_text)}")
            
            # Store in cache if db session provided
            if db:
                try:
                    from app.processing_cache import store_website_text
                    store_website_text(db, url, raw_text)
                except Exception as cache_error:
                    logger.warning(f"Failed to store website text in cache: {str(cache_error)}")
            
            return raw_text, raw_text  # Return raw text (cleaning will be done separately)
        else:
            logger.warning(f"Website scrape completed but no text extracted: url={about_url}")
            return None, None
            
    except Exception as e:
        logger.error(f"Website scrape error: url={url}, error={str(e)}")
        return None, None
