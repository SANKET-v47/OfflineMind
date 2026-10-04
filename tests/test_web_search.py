"""Unit tests for WebSearchProvider."""

from unittest.mock import patch, MagicMock
import pytest
from offlinemind.web.search import (
    SearchResultItem,
    DuckDuckGoSearchProvider,
    MockSearchProvider,
)


def test_mock_search_provider():
    provider = MockSearchProvider()
    assert provider.provider_name == "mock"
    results = provider.search("python news", max_results=1)
    assert len(results) == 1
    assert "Python" in results[0].title
    assert results[0].url.startswith("http")

    page = provider.fetch_page("http://example.com")
    assert "mock webpage" in page


@patch("requests.Session.post")
def test_duckduckgo_search_parsing(mock_post):
    sample_html = """
    <html>
      <body>
        <div class="result web-result">
          <a class="result__a" href="https://example.com/python">Python Official</a>
          <a class="result__snippet">Python is a programming language that lets you work quickly.</a>
        </div>
      </body>
    </html>
    """
    mock_post.return_value = MagicMock(status_code=200, text=sample_html)

    ddg = DuckDuckGoSearchProvider()
    results = ddg.search("python programming", max_results=5)
    assert len(results) == 1
    assert results[0].title == "Python Official"
    assert results[0].url == "https://example.com/python"
    assert "programming language" in results[0].snippet


@patch("requests.Session.get")
def test_duckduckgo_fetch_page_cleaning(mock_get):
    sample_page_html = """
    <html>
      <head><script>alert('bad');</script><style>body {color: red;}</style></head>
      <body>
        <nav>Navigation Bar</nav>
        <main>
          <h1>Main Article Heading</h1>
          <p>This is the important content of the article.</p>
        </main>
        <footer>Copyright 2026</footer>
      </body>
    </html>
    """
    mock_get.return_value = MagicMock(status_code=200, text=sample_page_html)

    ddg = DuckDuckGoSearchProvider()
    content = ddg.fetch_page("https://example.com/article")
    assert content is not None
    assert "Main Article Heading" in content
    assert "important content" in content
    # Verify script, style, nav, and footer were cleanly stripped
    assert "alert('bad')" not in content
    assert "Navigation Bar" not in content
    assert "Copyright 2026" not in content
