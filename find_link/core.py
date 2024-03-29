"""Core functions."""

import html
import re
import typing
from typing import Any

from .api import (
    MediawikiError,
    all_pages,
    cat_start,
    categorymembers,
    find_disambig,
    get_first_page,
    wiki_backlink,
    wiki_search,
)
from .util import case_flip_first, norm

re_redirect = re.compile(r"#REDIRECT \[\[(.)([^#]*?)(#.*)?\]\]")


def get_content_and_timestamp(title: str) -> tuple[str, str]:
    """Get article content and timestamp of last update."""
    params = {
        "prop": "revisions|info",
        "rvprop": "content|timestamp",
        "titles": title,
    }
    json_data: dict[str, Any] = get_first_page(params)
    if json_data.get("invalid"):
        raise MediawikiError(json_data["invalidreason"])
    rev = json_data["revisions"][0]
    return (rev["content"], rev["timestamp"])


def is_redirect_to(title_from: str, title_to: str) -> bool:
    title_from = title_from.replace("_", " ")
    params = {"prop": "info", "titles": title_from}
    if "redirect" not in get_first_page(params):
        return False

    params = {"prop": "revisions", "rvprop": "content", "titles": title_from}
    page_text = get_first_page(params)["revisions"][0]["content"]
    m = re_redirect.match(page_text)
    assert m
    title_to = title_to[0].upper() + title_to[1:]
    return m.group(1).upper() + m.group(2) == title_to


def find_longer(q: str, search: list[dict[str, Any]], articles: set[str]) -> list[str]:
    """Find other articles with titles that are longer."""
    this_title = q[0].upper() + q[1:]
    longer: list[str] = all_pages(this_title)
    lq = q.lower()
    for doc in search:
        lt = doc["title"].lower()
        if lq == lt or lq not in lt:
            continue
        articles.add(doc["title"])
        more_articles, more_redirects = wiki_backlink(doc["title"])
        articles.update(more_articles)
        if doc["title"] not in longer:
            longer.append(doc["title"])

    return longer


def tidy_snippet(snippet: str) -> str:
    """Remove HTML from snippet."""
    snippet = snippet.replace("\u2013", "-")
    snippet = snippet.replace("</span>", "")
    snippet = snippet.replace('<span class="searchmatch">', "")
    return html.unescape(snippet)


def match_type(q: str, snippet: str) -> str | None:
    """Discover match type, ''exact', 'case_mismatch' or None.

    >>> match_type('foo', 'foo')
    'exact'
    >>> match_type('foo', 'bar') is None
    True
    >>> match_type('bar', 'foo bar baz')
    'exact'
    >>> match_type('clean coal technology', 'foo clean coal technologies baz')
    'exact'
    >>> match_type('bar', 'foo Bar baz')
    'exact'
    >>> match_type('bar', 'foo BAR baz')
    'case_mismatch'
    >>> match_type('foo-bar', 'aa foo-bar cc')
    'exact'
    >>> match_type(u'foo\u2013bar', 'aa foo-bar cc')
    'exact'
    """
    q = q.replace("\u2013", "-")
    snippet = tidy_snippet(snippet)

    if q in snippet or case_flip_first(q) in snippet:
        return "exact"
    match = None
    if q.lower() in snippet.lower():
        match = "case_mismatch"
    if match != "exact" and q.endswith("y"):
        if q[:-1] in snippet or case_flip_first(q[:-1]) in snippet:
            return "exact"
    elif match is None:
        if q[:-1].lower() in snippet.lower():
            match = "case_mismatch"
    return match


def do_search(q: str, redirect_to: str | None) -> dict[str, typing.Any]:
    """Run search."""
    this_title = q[0].upper() + q[1:]

    totalhits, search = wiki_search(q)
    articles, redirects = wiki_backlink(redirect_to or q)
    cm = set()
    start = cat_start(q)
    if len(start) > 5:
        start = []  # big categories take too long
    for cat in set(["Category:" + this_title] + start):
        cm.update(categorymembers(cat))

    norm_q = norm(q)
    norm_match_redirect = {r for r in redirects if norm(r) == norm_q}
    longer_redirect = {r for r in redirects if q.lower() in r.lower()}

    articles.add(this_title)
    if redirect_to:
        articles.add(redirect_to[0].upper() + redirect_to[1:])

    longer_redirect = {r for r in redirects if q.lower() in r.lower()}
    for r in norm_match_redirect | longer_redirect:
        articles.add(r)
        a2, r2 = wiki_backlink(r)
        articles.update(a2)
        redirects.update(r2)

    longer = find_longer(q, search, articles) if len(q) > 6 else None

    search = [
        doc for doc in search if doc["title"] not in articles and doc["title"] not in cm
    ]
    if search:
        disambig = set(find_disambig([doc["title"] for doc in search]))
        search = [doc for doc in search if doc["title"] not in disambig]
        # and (doc['title'] not in links or this_title not in links[doc['title']])]
        for doc in search:
            without_markup = (
                doc["snippet"]
                .replace("<span class='searchmatch'>", "")
                .replace("</span>", "")
                .replace("  ", " ")
            )
            doc["match"] = match_type(q, without_markup)
            doc["snippet_without_markup"] = without_markup
    return {
        "totalhits": totalhits,
        "results": search,
        "longer": longer,
    }


def get_case_from_content(title: str) -> str | None:
    """Check article content to find the case of the article title."""
    content, timestamp = get_content_and_timestamp(title)
    if title == title.lower() and title in content:
        return title
    start = content.lower().find("'''" + title.replace("_", " ").lower() + "'''")
    if start != -1:
        return content[start + 3 : start + 3 + len(title)]

    return None  # article doesn't contain the title
