import collections
import re
import typing
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from simplejson.scanner import JSONDecodeError

from .language import get_current_language
from .util import is_disambig

ua = (
    "find-link/2.2 "
    + "(https://github.com/EdwardBetts/find_link; contact: edward@4angle.com)"
)
re_disambig = re.compile(r"^(.*) \((.*)\)$")


def get_query_url() -> str:
    """Get the wikipedia query API for the current language."""
    return f"https://{get_current_language()}.wikipedia.org/w/api.php"


sessions: dict[str, requests.Session] = {}

CallParams = dict[str, str | int]


def get_session() -> requests.Session:
    """Get requests.Session for the current language."""
    lang = get_current_language()
    if lang in sessions:
        assert sessions[lang]
        return sessions[lang]
    s = requests.Session()
    s.headers.update({"User-Agent": ua})
    s.mount("https://en.wikipedia.org", HTTPAdapter(max_retries=10))
    s.params = typing.cast(
        CallParams,
        {
            "format": "json",
            "action": "query",
            "formatversion": 2,
        },
    )
    sessions[lang] = s
    return s


class MediawikiError(Exception):
    """Mediawiki error."""


class MultipleRedirects(Exception):
    """Multiple redirects."""


class IncompleteReply(Exception):
    """Incomplete reply."""


class MissingPage(Exception):
    """Missing page."""


def check_for_error(json_data: dict[str, typing.Any]) -> None:
    """Check if JSON data contains an error."""
    if "error" in json_data:
        raise MediawikiError(json_data["error"]["info"])


webpage_error = (
    "Our servers are currently under maintenance or experiencing a technical problem."
)


def api_get(params: dict[str, typing.Any]) -> dict[str, Any]:
    """Make call to Wikipedia API."""
    s = get_session()

    r = s.get(get_query_url(), params=params)
    try:
        ret: dict[str, typing.Any] = r.json()
    except JSONDecodeError:
        if webpage_error in r.text:
            raise MediawikiError(webpage_error)
        else:
            raise MediawikiError("unknown error")
    check_for_error(ret)
    return ret


def get_first_page(params: dict[str, str]) -> dict[str, typing.Any]:
    """Run Wikipedia API query and return the first page."""
    page: dict[str, typing.Any] = api_get(params)["query"]["pages"][0]
    if page.get("missing"):
        raise MissingPage
    return page


def random_article_list(limit: int = 50) -> list[dict[str, typing.Any]]:
    """Random list of articles."""
    params = {
        "list": "random",
        "rnnamespace": "0",
        "rnlimit": limit,
    }

    return typing.cast(list[dict[str, typing.Any]], api_get(params)["query"]["random"])


def wiki_search(q: str) -> tuple[int, list[dict[str, typing.Any]]]:
    """Run search on Wikipedia."""
    m = re_disambig.match(q)
    if m:
        search = '"{}" AND "{}"'.format(*m.groups())
    else:
        search = '"{}"'.format(q)

    params = {
        "list": "search",
        "srwhat": "text",
        "srlimit": 50,
        "srsearch": search,
        "continue": "",
    }
    ret = api_get(params)
    query = ret["query"]
    totalhits = query["searchinfo"]["totalhits"]
    results = query["search"]
    for _ in range(10):
        if "continue" not in ret:
            break
        params["sroffset"] = ret["continue"]["sroffset"]
        ret = api_get(params)
        results += ret["query"]["search"]
    return (totalhits, results)


def get_wiki_info(q: str) -> str | None:
    """Get destination of redirect."""
    params = {
        "prop": "info",
        "redirects": "",
        "titles": q,
    }
    ret = api_get(params)["query"]
    if "interwiki" in ret:
        return None
    redirects = []
    if ret.get("redirects"):
        redirects = ret["redirects"]
        if len(redirects) != 1:
            # multiple redirects, we should explain to the user that this is
            # unsupported
            raise MultipleRedirects
    if ret["pages"][0].get("missing"):
        raise MissingPage(q)
    return redirects[0]["to"] if redirects else None


def cat_start(q: str) -> list[str]:
    """Find categories that start with this prefix."""
    params = {
        "list": "allpages",
        "apnamespace": 14,  # categories
        "apfilterredir": "nonredirects",
        "aplimit": 500,
        "apprefix": q,
    }
    ret = api_get(params)["query"]
    return [i["title"] for i in ret["allpages"] if i["title"] != q]


def all_pages(q: str) -> list[str]:
    """Get all article titles with a given prefix."""
    params = {
        "list": "allpages",
        "apnamespace": 0,
        "apfilterredir": "nonredirects",
        "aplimit": 500,
        "apprefix": q,
    }
    ret = api_get(params)["query"]
    return [i["title"] for i in ret["allpages"] if i["title"] != q]


def categorymembers(q: str) -> list[str]:
    """List of category members."""
    params = {
        "list": "categorymembers",
        "cmnamespace": 0,
        "cmlimit": 500,
        "cmtitle": q[0].upper() + q[1:],
    }
    ret = api_get(params)["query"]
    return [i["title"] for i in ret["categorymembers"] if i["title"] != q]


def find_disambig(titles: list[str]) -> list[str]:
    """Find disambiguation articles in the given list of titles."""
    titles = list(titles)
    assert titles
    pos = 0
    disambig: list[str] = []
    params = {
        "prop": "templates",
        "tllimit": 500,
        "tlnamespace": 10,  # templates
        "continue": "",
    }
    while pos < len(titles):
        params["titles"] = "|".join(titles[pos : pos + 50])
        ret = api_get(params)
        disambig.extend(
            doc["title"] for doc in ret["query"]["pages"] if is_disambig(doc)
        )
        for i in range(10):
            if "continue" not in ret:
                break
            tlcontinue = ret["continue"]["tlcontinue"]
            params["titles"] = "|".join(titles[pos : pos + 50])
            params["tlcontinue"] = tlcontinue
            ret = api_get(params)
            disambig.extend(
                doc["title"] for doc in ret["query"]["pages"] if is_disambig(doc)
            )
        pos += 50

    return disambig


def wiki_redirects(q: str) -> collections.abc.Iterator[str]:  # pages that link here
    """Find redirects to this article."""
    params = {
        "list": "backlinks",
        "blfilterredir": "redirects",
        "bllimit": 500,
        "blnamespace": 0,
        "bltitle": q,
    }
    docs = api_get(params)["query"]["backlinks"]
    assert all("redirect" in doc for doc in docs)
    return (doc["title"] for doc in docs)


def wiki_backlink(q: str) -> tuple[set[str], set[str]]:
    """Get backlinks for article."""
    params = {
        "list": "backlinks",
        "bllimit": 500,
        "blnamespace": 0,
        "bltitle": q,
        "continue": "",
    }
    ret = api_get(params)
    docs = ret["query"]["backlinks"]
    while "continue" in ret:
        params["blcontinue"] = ret["continue"]["blcontinue"]
        ret = api_get(params)
        docs += ret["query"]["backlinks"]

    articles = {doc["title"] for doc in docs if "redirect" not in doc}
    redirects = {doc["title"] for doc in docs if "redirect" in doc}
    return (articles, redirects)


def call_get_diff(title: str, section_num: int, section_text: str) -> str:
    """Get edit diff."""
    data = {
        "prop": "revisions",
        "rvprop": "timestamp",
        "titles": title,
        "rvsection": section_num,
        "rvdifftotext": section_text.strip(),
    }

    s = get_session()
    ret = s.post(get_query_url(), data=data).json()
    check_for_error(ret)
    diff: str = ret["query"]["pages"][0]["revisions"][0]["diff"]["body"]
    return diff
