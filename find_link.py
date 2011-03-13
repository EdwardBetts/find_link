from flask import Flask, render_template, request, Markup, redirect, url_for
import urllib, json, re, os
from datetime import datetime

app = Flask(__name__)
last_slash = __file__.rfind('/')
key = open(__file__[:last_slash+1] + 'key').read()
if key[-1] == '\n':
    key = key[:-1]
Flask.secret_key = key
query_url = 'http://en.wikipedia.org/w/api.php?format=json&action=query&'
search_params = 'list=search&srwhat=text&srlimit=50&srsearch='
backlink_params = 'list=backlinks&bllimit=500&blnamespace=0&bltitle='
redirect_params = 'list=backlinks&blfilterredir=redirects&bllimit=500&blnamespace=0&bltitle='
content_params = 'prop=revisions&rvprop=content|timestamp&titles='
link_params = 'prop=links&pllimit=500&plnamespace=0&titles='
templates_params = 'prop=templates&tllimit=500&tlnamespace=10&titles='
allpages_params = 'list=allpages&apnamespace=0&apfilterredir=nonredirects&aplimit=500&apprefix='
info_params = 'action=query&prop=info&redirects&titles='
categorymembers_params = 'action=query&list=categorymembers&cmnamespace=0&cmlimit=500&cmtitle=Category:'

def commify(amount):
    amount = str(amount)
    firstcomma = len(amount)%3 or 3  # set to 3 if would make a leading comma
    first, rest = amount[:firstcomma], amount[firstcomma:]
    segments = [first] + [rest[i:i+3] for i in range(0, len(rest), 3)]
    return ",".join(segments)

re_space_or_dash = re.compile('[ -]')

def is_title_case(phrase):
    return all(term[0].isupper() and term[1:].islower() for term in re_space_or_dash.split(phrase))

def test_is_title_case():
    assert is_title_case('Test')
    assert is_title_case('Test Test')
    assert not is_title_case('test')
    assert not is_title_case('TEST TEST')
    assert not is_title_case('test test')
    assert not is_title_case('tEst Test')

class AppURLopener(urllib.FancyURLopener):
    version = "find-link/2.0 (contact: edwardbetts@gmail.com)"

urllib._urlopener = AppURLopener()

def urlquote(s):
    return urllib.quote_plus(s.encode('utf-8'))

def test_is_title_case():
    assert urlquote('test') == 'test'
    assert urlquote('test test') == 'test+test'
    assert urlquote(u'na\xefve') == 'na%C3%AFve'

def web_get(params):
    return json.load(urllib.urlopen(query_url + params))

def wiki_search(q):
    search_url = search_params + urlquote('"%s"' % q)
    ret = web_get(search_url)
    totalhits = ret['query']['searchinfo']['totalhits']
    results = ret['query']['search']
    for i in range(3):
        if 'query-continue' not in ret:
            break
        sroffset = ret['query-continue']['search']['sroffset']
        ret = web_get(search_url + ('&sroffset=%d' % sroffset))
        results += ret['query']['search']
    return (totalhits, results)

def get_wiki_info(q):
    ret = web_get(info_params + urlquote(q))
    redirects = []
    if ret['query'].get('redirects'):
        redirects = ret['query']['redirects']
        assert len(redirects) == 1
    return (ret['query']['pages'].values()[0], redirects[0]['to'] if redirects else None)

def all_pages(q):
    ret = web_get(allpages_params + urlquote(q))
    return [doc['title'] for doc in ret['query']['allpages'] if doc['title'] != q]

def categorymembers(q):
    ret = web_get(categorymembers_params + urlquote(q[0].upper()) + urlquote(q[1:]))
    return [doc['title'] for doc in ret['query']['categorymembers'] if doc['title'] != q]

def page_links(titles):
    titles = list(titles)
    assert titles
    ret = web_get(link_params + urlquote('|'.join(titles)))
    return dict((doc['title'], set(l['title'] for l in doc['links'])) for doc in ret['query']['pages'].itervalues() if 'links' in doc)

def is_disambig(doc):
    return any('disambig' in t or t.endswith('dis') for t in (t['title'].lower() for t in doc.get('templates', [])))

def test_is_disambig():
    assert not is_disambig({})
    assert is_disambig({ 'templates': [ {'title': 'disambig'}, {'title': 'magic'}] })
    assert is_disambig({ 'templates': [ {'title': 'geodis'}] })
    assert is_disambig({ 'templates': [ {'title': 'Disambig'}] })

def find_disambig(titles):
    titles = list(titles)
    assert titles
    pos = 0
    disambig = []
    while pos < len(titles):
        ret = web_get(templates_params + urlquote('|'.join(titles[pos:pos+50])))
        disambig.extend(doc['title'] for doc in ret['query']['pages'].itervalues() if is_disambig(doc))
        for i in range(3):
            if 'query-continue' not in ret:
                break
            tlcontinue = ret['query-continue']['templates']['tlcontinue']
            ret = web_get(templates_params + urlquote('|'.join(titles[pos:pos+50])) + '&tlcontinue=' + urlquote(tlcontinue))
            disambig.extend(doc['title'] for doc in ret['query']['pages'].itervalues() if is_disambig(doc))
        pos += 50

    return disambig

re_non_letter = re.compile('\W', re.U)
def norm(s):
    s = re_non_letter.sub('', s).lower()
    return s[:-1] if s[-1] == 's' else s

def test_norm():
    assert norm('X') == 'x'
    assert norm('Tables') == 'table'
    assert norm('Tables!!!') == 'table'

def wiki_redirects(q): # pages that link here
    docs = web_get(redirect_params + urlquote(q))['query']['backlinks']
    assert all('redirect' in doc for doc in docs)
    return (doc['title'] for doc in docs)

def wiki_backlink(q):
    ret = web_get(backlink_params + urlquote(q))
    docs = ret['query']['backlinks']
    if 'query-continue' in ret:
        blcontinue = ret['query-continue']['backlinks']['blcontinue']
        ret = web_get(backlink_params + urlquote(q) + '&blcontinue=' + urlquote(blcontinue))
        docs += ret['query']['backlinks']

    articles = set(doc['title'] for doc in docs if 'redirect' not in doc)
    redirects = set(doc['title'] for doc in docs if 'redirect' in doc)
    return (articles, redirects)

def get_page(title, q):
    ret = web_get(content_params + urlquote(title))
    rev = ret['query']['pages'].values()[0]['revisions'][0]
    content = rev['*']
    timestamp = rev['timestamp']
    timestamp = ''.join(c for c in timestamp if c.isdigit())

    re_link = re.compile('([%s%s])%s' % (q[0].lower(), q[0].upper(), q[1:]))

    m = re_link.search(content)
    if m:
        replacement = m.group(1) + q[1:]
    else:
        re_link = re.compile('(%s)%s' % (q[0], q[1:]), re.I)
        m = re_link.search(content)
        if m:
            if any(c.isupper() for c in q[1:]):
                replacement = q
            else:
                replacement = q.lower() if is_title_case(m.group(0)) else m.group(1) + q[1:]
    if not m and ' ' in q:
        re_link = re.compile('(%s)%s' % (q[0], q[1:].replace(',', ',?').replace(' ', '[- ]?')), re.I)
        m = re_link.search(content)
        if m:
            if any(c.isupper() for c in q[1:]):
                replacement = q
            else:
                replacement = q.lower() if is_title_case(m.group(0)) else m.group(1) + q[1:]
    if not m:
        pat = r'(?:\[\[)?(%s)%s(?:\]\])?' % (q[0], ''.join('-?' + c for c in q[1:]).replace(' ', r"('?s?\]\])?'?s? ?(\[\[)?"))
        re_link = re.compile(pat, re.I)
        m = re_link.search(content)
        if m:
            if any(c.isupper() for c in q[1:]):
                replacement = q
            else:
                replacement = q.lower() if is_title_case(m.group(0)) else m.group(1) + q[1:]
    if not m:
        return None
    content = re_link.sub(lambda m: "[[%s]]" % replacement, content, count=1)
    summary = "link [[%s]] using [[User:Edward/Find link|Find link]]" % replacement
    #text = "title: %s\nq: %s\nsummary: %s\ntimestamp: %s\n\n%s" % (title, q, timestamp, summary, content)

    start_time = datetime.now().strftime("%Y%m%d%H%M%S")
    return render_template('find_link.html',
            urlquote=urlquote,
            start_time=start_time,
            content=content,
            title=title, summary=summary, timestamp=timestamp)

@app.route("/<q>")
def findlink(q, title=None, message=None):
    q_trim = q.strip('_')
    if ' ' in q or q != q_trim:
        return redirect(url_for('findlink', q=q.replace(' ', '_').strip('_'), message=message))
    q = q.replace('_', ' ').strip()
    (info, redirect_to) = get_wiki_info(q)
    if 'missing' in info:
        return render_template('index.html', message=q + " isn't an article")
    if redirect_to:
        return redirect(url_for('findlink', q=redirect_to.replace(' ', '_')))
    this_title = q[0].upper() + q[1:]
    (totalhits, search) = wiki_search(q)
    (articles, redirects) = wiki_backlink(q)
    cm = set(categorymembers(q))
    norm_q = norm(q)
    norm_match_redirect = set(r for r in redirects if norm(r) == norm_q)
    articles.add(this_title)
    for r in norm_match_redirect:
        articles.add(r)
        a2, r2 = wiki_backlink(r)
        articles.update(a2)
        redirects.update(r2)
    search = [doc for doc in search if doc['title'] not in articles and doc['title'] not in cm]
    if search:
        disambig = set(find_disambig([doc['title'] for doc in search]))
        search = [doc for doc in search if doc['title'] not in disambig]
    # and (doc['title'] not in links or this_title not in links[doc['title']])]
        for doc in search:
            doc['snippet'] = Markup(doc['snippet'])
    return render_template('index.html', q=q, totalhits=totalhits, message=message, results=search, urlquote=urlquote,
            commify=commify, longer_titles=all_pages(this_title), norm_match_redirect=norm_match_redirect)

@app.route("/favicon.ico")
def favicon():
    return redirect(url_for('static', filename='Link_edit.png'))

@app.route("/find_link/<q>")
def bad_url(q):
    return findlink(q)

@app.route("/")
def index():
    title = request.args.get('title')
    q = request.args.get('q')
    if title and q:
        q = q.replace('_', ' ').strip()
        title = title.replace('_', ' ').strip()
        reply = get_page(title, q)
        if reply is None:
            redirects = list(wiki_redirects(q))
            for r in redirects:
                reply = get_page(title, r)
                if reply:
                    return reply
            return findlink(q, title=title, message=q + ' not in ' + title)
        else:
            return reply
    if q:
        return redirect(url_for('findlink', q=q.replace(' ', '_').strip('_')))
    return render_template('index.html')

if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=True)
