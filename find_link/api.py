import requests
from requests.adapters import HTTPAdapter
from .util import strip_parens, is_disambig

ua = "find-link/2.2 (https://github.com/EdwardBetts/find_link; contact: edward@4angle.com)"

s = requests.Session()
s.headers = {'User-Agent': ua}
query_url = 'https://en.wikipedia.org/w/api.php'
s.mount('https://en.wikipedia.org', HTTPAdapter(max_retries=10))
s.params = {
    'format': 'json',
    'action': 'query',
    'formatversion': 2,
}

class Missing (Exception):
    pass

def api_get(params):
    return s.get(query_url, params=params).json()['query']

def get_first_page(params):
    return api_get(params)['pages'][0]

def wiki_search(q):
    params = {
        'list': 'search',
        'srwhat': 'text',
        'srlimit': 50,
        'srsearch': u'"{}"'.format(strip_parens(q)),
        'continue': '',
    }
    ret = api_get(params)
    totalhits = ret['searchinfo']['totalhits']
    results = ret['search']
    for i in range(3):
        if 'continue' not in ret:
            break
        params['sroffset'] = ret['continue']['sroffset']
        ret = api_get(params)
        results += ret['search']
    return (totalhits, results)

def get_wiki_info(q):
    params = {
        'prop': 'info',
        'redirects': '',
        'titles': q,
    }
    ret = api_get(params)
    redirects = []
    if ret.get('redirects'):
        redirects = ret['redirects']
        assert len(redirects) == 1
    if 'missing' in ret['pages'][0]:
        raise Missing
    return redirects[0]['to'] if redirects else None

def cat_start(q):
    params = {
        'list': 'allpages',
        'apnamespace': 14,  # categories
        'apfilterredir': 'nonredirects',
        'aplimit': 500,
        'apprefix': q,
    }
    ret = api_get(params)
    return [i['title'] for i in ret['allpages'] if i['title'] != q]

def all_pages(q):
    params = {
        'list': 'allpages',
        'apnamespace': 0,
        'apfilterredir': 'nonredirects',
        'aplimit': 500,
        'apprefix': q,
    }
    ret = api_get(params)
    return [i['title'] for i in ret['allpages'] if i['title'] != q]

def categorymembers(q):
    params = {
        'list': 'categorymembers',
        'cmnamespace': 0,
        'cmlimit': 500,
        'cmtitle': q[0].upper() + q[1:],
    }
    ret = api_get(params)
    return [i['title']
            for i in ret['categorymembers']
            if i['title'] != q]

def page_links(titles):  # unused
    titles = list(titles)
    assert titles
    params = {
        'prop': 'links',
        'pllimit': 500,
        'plnamespace': 0,
        'titles': '|'.join(titles)
    }
    ret = api_get(params)
    return dict((doc['title'], {l['title'] for l in doc['links']})
                for doc in ret['pages'].values() if 'links' in doc)

def find_disambig(titles):
    titles = list(titles)
    assert titles
    pos = 0
    disambig = []
    params = {
        'prop': 'templates',
        'tllimit': 500,
        'tlnamespace': 10,  # templates
        'continue': '',
    }
    while pos < len(titles):
        params['titles'] = '|'.join(titles[pos:pos + 50])
        ret = api_get(params)
        disambig.extend(doc['title'] for doc in ret['pages'] if is_disambig(doc))
        for i in range(3):
            if 'continue' not in ret:
                break
            tlcontinue = ret['continue']['tlcontinue']
            params['titles'] = '|'.join(titles[pos:pos + 50])
            params['tlcontinue'] = tlcontinue
            ret = api_get(params)
            disambig.extend(doc['title'] for doc in ret['pages'] if is_disambig(doc))
        pos += 50

    return disambig

def wiki_redirects(q):  # pages that link here
    params = {
        'list': 'backlinks',
        'blfilterredir': 'redirects',
        'bllimit': 500,
        'blnamespace': 0,
        'bltitle': q,
    }
    docs = api_get(params)['backlinks']
    assert all('redirect' in doc for doc in docs)
    return (doc['title'] for doc in docs)

def wiki_backlink(q):
    params = {
        'list': 'backlinks',
        'bllimit': 500,
        'blnamespace': 0,
        'bltitle': q,
        'continue': '',
    }
    ret = api_get(params)
    docs = ret['backlinks']
    while 'continue' in ret:
        params['blcontinue'] = ret['continue']['blcontinue']
        ret = api_get(params)
        docs += ret['backlinks']

    articles = {doc['title'] for doc in docs if 'redirect' not in doc}
    redirects = {doc['title'] for doc in docs if 'redirect' in doc}
    return (articles, redirects)

def call_get_diff(title, section_num, section_text):
    data = {
        'prop': 'revisions',
        'rvprop': 'timestamp',
        'titles': title,
        'rvsection': section_num,
        'rvdifftotext': section_text.strip(),
    }

    ret = s.post(query_url, data=data).json()
    return ret['pages'][0]['revisions'][0]['diff']['body']
