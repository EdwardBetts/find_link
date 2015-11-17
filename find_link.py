# coding=utf-8
import urllib
import re
import requests
from requests.adapters import HTTPAdapter
from datetime import datetime

from flask import Flask, render_template, request, Markup, redirect, url_for

app = Flask(__name__)
app.config.from_pyfile('config')

ua = "find-link/2.1 (https://github.com/EdwardBetts/find_link; contact: edward@4angle.com)"

s = requests.Session()
s.headers = {'User-Agent': ua}
query_url = 'https://en.wikipedia.org/w/api.php'
s.mount('https://en.wikipedia.org', HTTPAdapter(max_retries=10))
s.params = {
    'format': 'json',
    'action': 'query',
}

save_to_cache = False

re_heading = re.compile(r'^\s*(=+)\s*(.+)\s*\1(<!--.*-->|\s)*$')
re_link_in_text = re.compile(r'\[\[[^]]+?\]\]', re.I | re.S)
re_space_or_dash = re.compile('[ -]')


def is_title_case(phrase):
    '''Detected if a given phrase is in Title Case.

    >>> is_title_case('Test')
    True
    >>> is_title_case('Test Test')
    True
    >>> is_title_case('test')
    False
    >>> is_title_case('TEST TEST')
    False
    >>> is_title_case('test test')
    False
    >>> is_title_case('tEst Test')
    False
    '''

    return all(term[0].isupper() and term[1:].islower()
               for term in re_space_or_dash.split(phrase))


def urlquote(value):
    '''prepare string for use in URL param

    >>> urlquote('test')
    'test'
    >>> urlquote('test test')
    'test+test'
    >>> urlquote(u'na\xefve')
    'na%C3%AFve'
    '''

    return urllib.quote_plus(value.encode('utf-8'))


re_end_parens = re.compile(r' \(.*\)$')

def api_get(params):
    return s.get(query_url, params=params).json()

def strip_parens(q):
    m = re_end_parens.search(q)
    return q[:m.start()] if m else q


def wiki_search(q):
    params = {
        'list': 'search',
        'srwhat': 'text',
        'srlimit': 50,
        'srsearch': u'"{}"'.format(strip_parens(q)),
        'continue': '',
    }
    ret = api_get(params)
    totalhits = ret['query']['searchinfo']['totalhits']
    results = ret['query']['search']
    for i in range(3):
        if 'continue' not in ret:
            break
        params['sroffset'] = ret['continue']['sroffset']
        ret = api_get(params)
        results += ret['query']['search']
    return (totalhits, results)


class Missing (Exception):
    pass


def get_wiki_info(q):
    params = {
        'prop': 'info',
        'redirects': '',
        'titles': q,
    }
    ret = api_get(params)
    redirects = []
    if ret['query'].get('redirects'):
        redirects = ret['query']['redirects']
        assert len(redirects) == 1
    if 'missing' in ret['query']['pages'].values()[0]:
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
    return [i['title'] for i in ret['query']['allpages'] if i['title'] != q]

def all_pages(q):
    params = {
        'list': 'allpages',
        'apnamespace': 0,
        'apfilterredir': 'nonredirects',
        'aplimit': 500,
        'apprefix': q,
    }
    ret = api_get(params)
    return [i['title'] for i in ret['query']['allpages'] if i['title'] != q]

def categorymembers(q):
    params = {
        'list': 'categorymembers',
        'cmnamespace': 0,
        'cmlimit': 500,
        'cmtitle': q[0].upper() + q[1:],
    }
    ret = api_get(params)
    return [i['title']
            for i in ret['query']['categorymembers']
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
                for doc in ret['query']['pages'].itervalues() if 'links' in doc)

def is_disambig(doc):
    '''Is a this a disambiguation page?
    >>> is_disambig({})
    False
    >>> is_disambig({'templates':[{'title': 'disambig'},{'title': 'magic'}]})
    True
    >>> is_disambig({ 'templates': [ {'title': 'geodis'}] })
    True
    >>> is_disambig({ 'templates': [ {'title': 'Disambig'}] })
    True
    '''
    return any('disambig' in t or t.endswith('dis') or 'given name' in t or
               t == 'template:surname' for t in
               (t['title'].lower() for t in doc.get('templates', [])))

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
        disambig.extend(doc['title'] for doc in ret['query']['pages'].itervalues() if is_disambig(doc))
        for i in range(3):
            if 'continue' not in ret:
                break
            tlcontinue = ret['continue']['tlcontinue']
            params['titles'] = '|'.join(titles[pos:pos + 50])
            params['tlcontinue'] = tlcontinue
            ret = api_get(params)
            disambig.extend(doc['title'] for doc in ret['query']['pages'].itervalues() if is_disambig(doc))
        pos += 50

    return disambig

re_non_letter = re.compile('\W', re.U)

def norm(s):
    '''Normalise string.

    >>> norm('X')
    'x'
    >>> norm('Tables')
    'table'
    >>> norm('Tables!!!')
    'table'
    '''

    s = re_non_letter.sub('', s).lower()
    return s[:-1] if s and s[-1] == 's' else s

re_redirect = re.compile(r'#REDIRECT \[\[(.)([^#]*?)(#.*)?\]\]')


def is_redirect_to(title_from, title_to):
    title_from = title_from.replace('_', ' ')
    params = {'prop': 'info', 'titles': title_from}
    ret = api_get(params)
    if 'redirect' not in ret['query']['pages'].values()[0]:
        return False

    params = {'prop': 'revisions', 'rvprop': 'content', 'titles': title_from}
    ret = api_get(params)
    page_text = ret['query']['pages'].values()[0]['revisions'][0]['*']
    m = re_redirect.match(page_text)
    title_to = title_to[0].upper() + title_to[1:]
    return m.group(1).upper() + m.group(2) == title_to

def wiki_redirects(q):  # pages that link here
    params = {
        'list': 'backlinks',
        'blfilterredir': 'redirects',
        'bllimit': 500,
        'blnamespace': 0,
        'bltitle': q,
    }
    docs = api_get(params)['query']['backlinks']
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
    docs = ret['query']['backlinks']
    while 'continue' in ret:
        params['blcontinue'] = ret['continue']['blcontinue']
        ret = api_get(params)
        docs += ret['query']['backlinks']

    articles = {doc['title'] for doc in docs if 'redirect' not in doc}
    redirects = {doc['title'] for doc in docs if 'redirect' in doc}
    return (articles, redirects)

re_cite = re.compile(r'<ref( [^>]*?)?>\s*({{cite.*?}}|\[https?://[^]]*?\])\s*</ref>', re.I | re.S)


def parse_cite(text):
    prev = 0
    for m in re_cite.finditer(text):
        yield ('text', text[prev:m.start()])
        yield ('cite', m.group(0))
        prev = m.end()
    yield ('text', text[prev:])


class NoMatch(Exception):
    pass

class LinkReplace(Exception):
    pass


def section_iter(text):
    cur_section = ''
    heading = None
    for line in text.splitlines(True):
        m = re_heading.match(line)
        if not m:
            cur_section += line
            continue
        if cur_section or heading:
            yield (heading, cur_section)
        heading = m.group()
        cur_section = ''
        continue
    yield (heading, cur_section)


def get_subsections(text, section_num):
    'retrieve the text of subsections for a given section number within an article'
    found = ''
    collection_level = None
    for num, (heading, body) in enumerate(section_iter(text)):
        if heading is None:
            level = 0
        else:
            m = re_heading.match(heading)
            level = len(m.group(1))
        if num == section_num:
            collection_level = level
            continue
        if collection_level:
            if level > collection_level:
                found += heading + body
            else:
                break
    return found

en_dash = u'\u2013'
trans = {',': ',?', ' ': ' *[-\n]? *'}
trans[en_dash] = trans[' ']

trans2 = {' ': r"('?s?\]\])?'?s? ?(\[\[(?:.+\|)?)?", '-': '[- ]'}
trans2[en_dash] = trans2[' ']

patterns = [
    lambda q: re.compile(r'(?<!-)(?:\[\[(?:[^]]+\|)?)?(%s)%s(?:\]\])?' % (q[0], ''.join('-?' + trans2.get(c, c) for c in q[1:])), re.I),
    lambda q: re.compile(r'(?<!-)\[\[[^|]+\|(%s)%s\]\]' % (q[0], q[1:]), re.I),
    lambda q: re.compile(r'(?<!-)\[\[[^|]+\|(%s)%s(?:\]\])?' % (q[0], ''.join('-?' + trans2.get(c, c) for c in q[1:])), re.I),
    lambda q: re.compile(r'(?<!-)(%s)%s' % (q[0], q[1:]), re.I),
    lambda q: re.compile(r'(?<!-)(%s)%s' % (q[0], ''.join(trans.get(c, c) for c in q[1:])), re.I),
]


def match_found(m, q, linkto):
    if q[1:] == m.group(0)[1:]:
        replacement = m.group(1) + q[1:]
    elif any(c.isupper() for c in q[1:]) or m.group(0) == m.group(0).upper():
        replacement = q
    elif is_title_case(m.group(0)):
        replacement = None
        replacement = get_case_from_content(q)
        if replacement is None:
            replacement = q.lower()
    else:
        replacement = m.group(1) + q[1:]
    assert replacement
    if linkto:
        if linkto[0].isupper() and replacement[0] == linkto[0].lower():
            linkto = linkto[0].lower() + linkto[1:]
        elif replacement[0].isupper():
            linkto = linkto[0].upper() + linkto[1:]
        replacement = linkto + '|' + replacement
    return replacement


def parse_links(text):
    prev = 0
    for m in re_link_in_text.finditer(text):
        if prev != m.start():
            yield ('text', text[prev:m.start()])
        if any(m.group().lower().startswith('[[' + prefix) for prefix in ('file:', 'image:')):
            yield ('image', m.group(0))
        else:
            yield ('link', m.group(0))
        prev = m.end()
    if prev < len(text):
        yield ('text', text[prev:])


def mk_link_matcher(q):
    re_links = [p(q) for p in patterns]

    def search_for_link(text):
        for re_link in re_links:
            m = re_link.search(text)
            if m and m.group(0).count('[[') < 4:
                return m

    return search_for_link


def add_link(m, replacement, text):
    return m.re.sub(lambda m: "[[%s]]" % replacement, text, count=1)


def find_link_in_chunk(q, content, linkto=None):
    search_for_link = mk_link_matcher(q)
    new_content = ''
    replacement = None

    match_in_non_link = False
    bad_link_match = False

    for token_type, text in parse_links(content):
        if token_type == 'text':
            if search_for_link(text):
                match_in_non_link = True
        elif token_type == 'image':
            before, sep, link_text = text[:-2].rpartition('|')
            m = search_for_link(link_text)
            if m:
                replacement = match_found(m, q, linkto)
                text = before + sep + add_link(m, replacement, link_text) + ']]'
        elif token_type == 'link' and not replacement and not match_in_non_link:
            link_text = text[2:-2]
            link_dest = None
            if '|' in link_text:
                link_dest, link_text = link_text.split('|', 1)
            m = search_for_link(link_text)
            if m:
                lc_alpha = lambda s: ''.join(c.lower() for c in s if c.isalpha())
                lc_alpha_q = lc_alpha(q)

                bad_link_match = link_dest and len(link_dest) > len(q) and (lc_alpha_q not in lc_alpha(link_dest))
                if not link_dest:
                    if q in link_text and len(link_text) > len(q):
                        bad_link_match = True
                if bad_link_match and link_dest:
                    link_dest_redirect = get_wiki_info(link_dest)
                    if link_dest_redirect and lc_alpha(link_dest_redirect) == lc_alpha_q:
                        bad_link_match = False
                if not bad_link_match:
                    replacement = match_found(m, q, linkto)
                    text = add_link(m, replacement, link_text)
        new_content += text
    if not replacement:
        if bad_link_match:
            raise LinkReplace
        m = search_for_link(content)
        if m:
            replacement = match_found(m, q, linkto)
            new_content = add_link(m, replacement, content)
            if linkto:
                m_end = m.end()
                re_extend = re.compile(m.re.pattern + r'\w*\b', re.I)
                m = re_extend.search(content)
                if m.end() > m_end:
                    replacement += content[m_end:m.end()]
                    new_content = add_link(m, replacement, content)
    return (new_content, replacement)


def find_link_in_text(q, content):
    (new_content, replacement) = find_link_in_chunk(q, content)
    if replacement:
        return (new_content, replacement)
    raise NoMatch


def find_link_in_content(q, content, linkto=None):
    if linkto:
        try:
            return find_link_in_content(linkto, content)
        except NoMatch:
            pass
    replacement = None
    new_content = ''
    link_replace = False
    for header, section_text in section_iter(content):
        if header:
            new_content += header
        for token_type, text in parse_cite(section_text):
            if token_type == 'text' and not replacement:
                try:
                    (new_text, replacement) = find_link_in_chunk(q, text, linkto=linkto)
                except LinkReplace:
                    link_replace = True
                if replacement:
                    text = new_text
            new_content += text
    if replacement:
        return (new_content, replacement)
    raise LinkReplace if link_replace else NoMatch


def find_link_and_section(q, content, linkto=None):
    if linkto:
        try:
            return find_link_and_section(linkto, content)
        except NoMatch:
            pass
    sections = list(section_iter(content))
    replacement = None

    search_for_link = mk_link_matcher(q)

    found = {}

    for section_num, (header, section_text) in enumerate(sections):
        new_content = ''
        if header:
            new_content += header
        for token_type, text in parse_cite(section_text):
            if token_type == 'text' and not replacement:
                new_text = ''
                for token_type2, text2 in parse_links(text):
                    if token_type2 == 'link' and not replacement:
                        link_text = text2[2:-2]
                        if '|' in link_text:
                            link_dest, link_text = link_text.split('|', 1)
                        else:
                            link_dest = None
                        m = search_for_link(link_text)
                        if m:
                            if link_dest:
                                found['link_dest'] = link_dest
                            found['link_text'] = link_text
                            replacement = match_found(m, q, None)
                            text2 = add_link(m, replacement, link_text)
                    new_text += text2
                if replacement:
                    text = new_text
                else:
                    m = search_for_link(text)
                    if m:
                        replacement = match_found(m, q, linkto)
                        text = add_link(m, replacement, text)
            new_content += text
        if replacement:
            found.update({
                'section_num': section_num,
                'section_text': new_content,
                'old_text': (header or '') + section_text,
                'replacement': replacement,
            })
            return found
    raise NoMatch

def get_case_from_content(title):
    content, timestamp = get_content_and_timestamp(title)
    if title == title.lower() and title in content:
        return title
    start = content.lower().find("'''" + title.replace('_', ' ').lower() + "'''")
    if start != -1:
        return content[start + 3:start + 3 + len(title)]

def get_diff(q, title, linkto):
    content, timestamp = get_content_and_timestamp(title)
    found = find_link_and_section(q, content, linkto)

    section_text = found['section_text'] + get_subsections(content, found['section_num'])
    data = {
        'prop': 'revisions',
        'rvprop': 'timestamp',
        'titles': title,
        'rvsection': found['section_num'],
        'rvdifftotext': section_text.strip(),
    }

    ret = s.post(query_url, data=data).json()
    diff = ret['query']['pages'].values()[0]['revisions'][0]['diff']['*']
    return (diff, found['replacement'])

@app.route('/diff')
def diff_view():
    q = request.args.get('q')
    title = request.args.get('title')
    linkto = request.args.get('linkto')

    try:
        diff, replacement = get_diff(q, title, linkto)
    except NoMatch:
        return "can't generate diff"

    return '<table>' + diff + '</table>'


def get_content_and_timestamp(title):
    params = {
        'prop': 'revisions|info',
        'rvprop': 'content|timestamp',
        'titles': title,
    }
    rev = api_get(params)['query']['pages'].values()[0]['revisions'][0]
    return (rev['*'], rev['timestamp'])


def get_page(title, q, linkto=None):
    content, timestamp = get_content_and_timestamp(title)
    timestamp = ''.join(c for c in timestamp if c.isdigit())

    try:
        (content, replacement) = find_link_in_content(q, content, linkto)
    except NoMatch:
        return None

    summary = "link [[%s]] using [[User:Edward/Find link|Find link]]" % replacement

    start_time = datetime.now().strftime("%Y%m%d%H%M%S")
    return render_template('find_link.html', urlquote=urlquote,
                           start_time=start_time, content=content, title=title,
                           summary=summary, timestamp=timestamp)


def case_flip(s):
    '''Switch case of character.
    >>> case_flip("a")
    'A'
    >>> case_flip("A")
    'a'
    >>> case_flip("1")
    '1'
    '''
    if s.islower():
        return s.upper()
    if s.isupper():
        return s.lower()
    return s


def case_flip_first(s):
    return case_flip(s[0]) + s[1:]


def match_type(q, snippet):
    '''Discover match type, ''exact', 'case_mismatch' or None.
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
    '''

    q = q.replace(u'\u2013', '-')
    snippet = snippet.replace(u'\u2013', '-')
    snippet = snippet.replace(u'</span>', '')
    snippet = snippet.replace(u'<span class="searchmatch">', '')
    if q in snippet or case_flip_first(q) in snippet:
        return 'exact'
    match = None
    if q.lower() in snippet.lower():
        match = 'case_mismatch'
    if match != 'exact' and q.endswith('y'):
        if q[:-1] in snippet or case_flip_first(q[:-1]) in snippet:
            return 'exact'
    elif match is None:
        if q[:-1].lower() in snippet.lower():
            match = 'case_mismatch'
    return match


def find_longer(q, search, articles):
    this_title = q[0].upper() + q[1:]
    longer = all_pages(this_title)
    lq = q.lower()
    for doc in search:
        lt = doc['title'].lower()
        if lq == lt or lq not in lt:
            continue
        articles.add(doc['title'])
        more_articles, more_redirects = wiki_backlink(doc['title'])
        articles.update(more_articles)
        if doc['title'] not in longer:
            longer.append(doc['title'])

    return longer


def do_search(q, redirect_to):
    this_title = q[0].upper() + q[1:]

    totalhits, search = wiki_search(q)
    articles, redirects = wiki_backlink(redirect_to or q)
    cm = set()
    for cat in set(['Category:' + this_title] + cat_start(q)):
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

    longer = find_longer(q, search, articles)

    search = [doc for doc in search
              if doc['title'] not in articles and doc['title'] not in cm]
    if search:
        disambig = set(find_disambig([doc['title'] for doc in search]))
        search = [doc for doc in search if doc['title'] not in disambig]
    # and (doc['title'] not in links or this_title not in links[doc['title']])]
        for doc in search:
            without_markup = doc['snippet'].replace("<span class='searchmatch'>", "").replace("</span>", "").replace('  ', ' ')
            doc['match'] = match_type(q, without_markup)
            doc['snippet_without_markup'] = without_markup
    return {
        'totalhits': totalhits,
        'results': search,
        'longer': longer,
    }


@app.route("/<path:q>")
def findlink(q, title=None, message=None):
    if q and '%' in q:  # double encoding
        q = urllib.unquote(q)
    q_trim = q.strip('_')
    if not message and (' ' in q or q != q_trim):
        return redirect(url_for('findlink', q=q.replace(' ', '_').strip('_'),
                        message=message))
    q = q.replace('_', ' ').strip()

    try:
        redirect_to = get_wiki_info(q)
    except Missing:
        return render_template('index.html', message=q + " isn't an article")
    # if redirect_to:
    #     return redirect(url_for('findlink', q=redirect_to.replace(' ', '_')))
    if redirect_to:
        if q[0].isupper():
            redirect_to = redirect_to[0].upper() + redirect_to[1:]
        elif q[0].islower():
            redirect_to = redirect_to[0].lower() + redirect_to[1:]

    ret = do_search(q, redirect_to)

    for doc in ret['results']:
        doc['snippet'] = Markup(doc['snippet'])

    return render_template('index.html', q=q,
        totalhits=ret['totalhits'],
        message=message,
        results=ret['results'],
        urlquote=urlquote,
        str=str,
        enumerate=enumerate,
        longer_titles=ret['longer'],
        redirect_to=redirect_to,
        case_flip_first=case_flip_first)


@app.route("/favicon.ico")
def favicon():
    return redirect(url_for('static', filename='Link_edit.png'))


@app.route("/new_pages")
def newpages():
    params = {
        'list': 'recentchanges',
        'rclimit': 50,
        'rctype': 'new',
        'rcnamespace': 0,
        'rcshow': '!redirect',
    }
    np = api_get(params)['query']['recentchanges']
    return render_template('new_pages.html', new_pages=np)


@app.route("/find_link/<q>")
def bad_url(q):
    return findlink(q)


def wiki_space_norm(s):
    return s.replace('_', ' ').strip()


@app.route("/")
def index():
    title = request.args.get('title')
    q = request.args.get('q')
    linkto = request.args.get('linkto')
    if title and q:
        q = wiki_space_norm(q)
        title = wiki_space_norm(title)
        if linkto:
            linkto = wiki_space_norm(linkto)
        reply = get_page(title, q, linkto)
        if reply:
            return reply
        redirects = list(wiki_redirects(q))
        for r in redirects:
            reply = get_page(title, r, linkto=q)
            if reply:
                return reply
        return findlink(q.replace(' ', '_'), title=title,
                        message=q + ' not in ' + title)
    if q:
        return redirect(url_for('findlink', q=q.replace(' ', '_').strip('_')))
    return render_template('index.html')

if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=True)
