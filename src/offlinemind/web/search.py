"""Web search provider abstraction and privacy-preserving DuckDuckGo searcher using standard library."""

from __future__ import annotations
from abc import ABC, abstractmethod
import html
import logging
import re
from typing import Dict, List, Optional, Any
from urllib.parse import quote_plus, unquote
import requests

logger = logging.getLogger(__name__)


def strip_html_tags(text: str) -> str:
    """Removes HTML tags and unescapes entities."""
    clean = re.sub(r"<[^>]+>", " ", text)
    clean = html.unescape(clean)
    return " ".join(clean.split())


class SearchResultItem:
    """Structured search result with title, snippet, and source URL."""

    def __init__(self, title: str, snippet: str, url: str, source: str = "Web"):
        self.title = title.strip()
        self.snippet = snippet.strip()
        self.url = url.strip()
        self.source = source.strip()

    def to_dict(self) -> Dict[str, str]:
        return {
            "title": self.title,
            "snippet": self.snippet,
            "url": self.url,
            "source": self.source,
        }

    def __repr__(self) -> str:
        return f"<SearchResultItem title='{self.title[:30]}' url='{self.url}'>"


class WebSearchProvider(ABC):
    """Abstract interface for web search providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @abstractmethod
    def search(self, query: str, max_results: int = 5) -> List[SearchResultItem]:
        """Performs search and returns ranked list of results."""
        pass

    @abstractmethod
    def fetch_page(self, url: str, timeout: float = 8.0) -> Optional[str]:
        """Fetches and cleans plain text content from a web page."""
        pass


class DuckDuckGoSearchProvider(WebSearchProvider):
    """Zero-dependency web search provider using DuckDuckGo HTML endpoint."""

    def __init__(self, user_agent: Optional[str] = None):
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.user_agent})

    @property
    def provider_name(self) -> str:
        return "duckduckgo"

    def search(self, query: str, max_results: int = 5) -> List[SearchResultItem]:
        clean_query = query.strip()
        if not clean_query:
            return []

        results: List[SearchResultItem] = []
        try:
            url = f"https://html.duckduckgo.com/html/?q={quote_plus(clean_query)}"
            resp = self.session.post(
                url,
                data={"q": clean_query},
                timeout=7.0,
            )
            if resp.status_code != 200:
                logger.warning("DuckDuckGo returned HTTP %d", resp.status_code)
                return []

            raw_html = resp.text

            # Match result blocks: result__a (title and url) and result__snippet
            blocks = re.findall(
                r'<a[^>]*class="[^"]*result__a[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?'
                r'<(?:a|div)[^>]*class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</(?:a|div)>',
                raw_html,
                re.DOTALL,
            )

            for href, raw_title, raw_snippet in blocks:
                # Extract actual target url from DuckDuckGo uddg parameter if present
                if "uddg=" in href:
                    m = re.search(r"uddg=([^&]+)", href)
                    target_url = unquote(m.group(1)) if m else href
                else:
                    target_url = href

                title = strip_html_tags(raw_title)
                snippet = strip_html_tags(raw_snippet)

                if target_url.startswith("http") and title and snippet:
                    results.append(SearchResultItem(title=title, snippet=snippet, url=target_url, source="DuckDuckGo"))
                    if len(results) >= max_results:
                        break
        except Exception as e:
            logger.warning("Web search failed on '%s': %s", clean_query, e)

        return results

    def fetch_page(self, url: str, timeout: float = 8.0) -> Optional[str]:
        try:
            resp = self.session.get(url, timeout=timeout)
            if resp.status_code != 200:
                return None
            raw = resp.text
            # Strip scripts, styles, nav, footer, header
            cleaned = re.sub(r"<(script|style|nav|header|footer|noscript)[^>]*>.*?</\1>", " ", raw, flags=re.DOTALL | re.IGNORECASE)
            text = strip_html_tags(cleaned)
            return text[:10000]
        except Exception as e:
            logger.warning("Failed to fetch page %s: %s", url, e)
            return None


class MockSearchProvider(WebSearchProvider):
    """Deterministic mock search provider for unit tests and air-gapped demo environments."""

    def __init__(self, predefined_results: Optional[List[SearchResultItem]] = None):
        self.predefined_results = predefined_results or [
            SearchResultItem(
                title="Python 3.14 Official Release Notes",
                snippet="Python 3.14 introduces new features including improved performance and type system enhancements.",
                url="https://docs.python.org/3.14/whatsnew/3.14.html",
                source="Python Official Docs",
            )
        ]

    @property
    def provider_name(self) -> str:
        return "mock"

    def search(self, query: str, max_results: int = 5) -> List[SearchResultItem]:
        return self.predefined_results[:max_results]

    def fetch_page(self, url: str, timeout: float = 8.0) -> Optional[str]:
        return "This is mock webpage content for " + url
