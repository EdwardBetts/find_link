"""Util functions."""

import re
import urllib
from typing import Any

# util functions that don't access the network

namespaces = {
    ns.casefold()
    for ns in (
        "Special",
        "Media",
        "Talk",
        "Template",
        "Portal",
        "Portal talk",
        "Book",
        "Book talk",
        "Template talk",
        "Draft",
        "Draft talk",
        "Help",
        "Help talk",
        "Category",
        "Category talk",
        "User",
        "Gadget",
        "Gadget talk",
        "Gadget definition",
        "Gadget definition talk",
        "Topic",
        "User talk",
        "Wikipedia",
        "Education Program",
        "Education Program talk",
        "Wikipedia talk",
        "File",
        "File talk",
        "TimedText",
        "TimedText talk",
        "MediaWiki",
        "Module",
        "Module talk",
        "MediaWiki talk",
    )
}

re_space_or_dash = re.compile("[ -]")


def is_title_case(phrase: str) -> bool:
    """Is a given phrase is in Title Case."""
    return all(
        term[0].isupper() and term[1:].islower()
        for term in re_space_or_dash.split(phrase)
        if term and term[0].isalpha()
    )


def urlquote(value: str) -> str:
    """Prepare string for use in URL param."""
    return urllib.parse.quote_plus(value.encode("utf-8"))


def strip_parens(q: str) -> str:
    """Remove a word in parenthesis from the end of a string."""
    m = re.search(r" \(.*?\)$", q)
    return q[: m.start()] if m else q


def starts_with_namespace(title: str) -> bool:
    """Check if a title starts with a namespace."""
    return ":" in title and title.split(":", 1)[0].casefold() in namespaces


def is_disambig(doc: dict[str, Any]) -> bool:
    """Is a this a disambiguation page."""
    return any(
        "disambig" in t
        or t.endswith("dis")
        or "given name" in t
        or t == "template:surname"
        for t in (t["title"].lower() for t in doc.get("templates", []))
    )


def norm(s: str) -> str:
    """Normalise string."""
    s = re.sub(r"\W", "", s).lower()
    return s[:-1] if s and s[-1] == "s" else s


def case_flip(s: str) -> str:
    """Switch case of character."""
    if s.islower():
        return s.upper()
    if s.isupper():
        return s.lower()
    return s


def case_flip_first(s: str) -> str:
    """Switch case of first character in string."""
    return case_flip(s[0]) + s[1:]


def lc_alpha(s: str) -> str:
    """Lower case alphabetic characters in string."""
    return "".join(c.lower() for c in s if c.isalpha())


def wiki_space_norm(s: str) -> str:
    """Normalise article title."""
    return s.replace("_", " ").strip()
