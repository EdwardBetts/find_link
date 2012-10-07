# coding=utf-8
from flask import Flask, render_template, request, Markup, redirect, url_for
from time import time
from datetime import datetime
from pprint import pprint
import urllib, json, re, os, sys

app = Flask(__name__)
last_slash = __file__.rfind('/')
key = open(__file__[:last_slash+1] + 'key').read()
if key[-1] == '\n':
    key = key[:-1]
Flask.secret_key = key
query_url = 'https://en.wikipedia.org/w/api.php?format=json&action=query&'
#srprop = 'size|wordcount|timestamp|score|snippet|titlesnippet|sectionsnippet|sectiontitle|redirectsnippet|redirecttitle|hasrelated'
search_params = 'list=search&srwhat=text&srlimit=50&srsearch='
new_page_params = 'list=recentchanges&rclimit=50&rctype=new&rcnamespace=0&rcshow=!redirect'
backlink_params = 'list=backlinks&bllimit=500&blnamespace=0&bltitle='
redirect_params = 'list=backlinks&blfilterredir=redirects&bllimit=500&blnamespace=0&bltitle='
content_params = 'prop=revisions&rvprop=content|timestamp&titles='
content_params2 = 'prop=revisions|info&rvprop=content|timestamp&titles='
link_params = 'prop=links&pllimit=500&plnamespace=0&titles='
templates_params = 'prop=templates&tllimit=500&tlnamespace=10&titles='
allpages_params = 'list=allpages&apnamespace=0&apfilterredir=nonredirects&aplimit=500&apprefix='
info_params = 'action=query&prop=info&redirects&titles='
categorymembers_params = 'action=query&list=categorymembers&cmnamespace=0&cmlimit=500&cmtitle='
cat_start_params = 'list=allpages&apnamespace=14&apfilterredir=nonredirects&aplimit=500&apprefix='

save_to_cache = False

def commify(amount):
    amount = str(amount)
    firstcomma = len(amount)%3 or 3  # set to 3 if would make a leading comma
    first, rest = amount[:firstcomma], amount[firstcomma:]
    segments = [first] + [rest[i:i+3] for i in range(0, len(rest), 3)]
    return ",".join(segments)

def test_commify():
    assert commify(1) == '1'
    assert commify(2222) == '2,222'
    assert commify('3333') == '3,333'

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

def test_urlquote():
    assert urlquote('test') == 'test'
    assert urlquote('test test') == 'test+test'
    assert urlquote(u'na\xefve') == 'na%C3%AFve'

def web_get(params):
    data = urllib.urlopen(query_url + params).read()
    if save_to_cache:
        out = open('cache/' + str(time()), 'w')
        print >> out, params
        print >> out, data
        out.close()
    return json.loads(data)

def web_post(params):
    data = urllib.urlopen('https://en.wikipedia.org/w/api.php', 'format=json&action=query&' + params).read()
    if save_to_cache:
        out = open('cache/' + str(time()), 'w')
        print >> out, params
        print >> out, data
        out.close()
    return json.loads(data)

re_end_parens = re.compile(r' \(.*\)$')
def wiki_search(q):
    m = re_end_parens.search(q)
    if m:
        q = q[:m.start()]
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

class Missing (Exception):
    pass

def get_wiki_info(q):
    ret = web_get(info_params + urlquote(q))
    redirects = []
    if ret['query'].get('redirects'):
        redirects = ret['query']['redirects']
        assert len(redirects) == 1
    if 'missing' in ret['query']['pages'].values()[0]:
        raise Missing
    return redirects[0]['to'] if redirects else None

def test_get_wiki_info():
    global web_get
    web_get = lambda(param): {
        "query":{
            "normalized":[{
                "from":"government budget deficit",
                "to":"Government budget deficit"
            }],
            "pages":{
                "312605":{
                    "pageid":312605,"ns":0,"title":"Government budget deficit","touched":"2011-11-24T22:06:21Z","lastrevid":462258859,"counter":"","length":14071
                }
            }
        }
    }

    redirects = get_wiki_info('government budget deficit')
    assert redirects == None

    web_get = lambda(param): {
        "query":{
            "normalized":[{"from":"government budget deficits","to":"Government budget deficits"}],
            "pages":{"-1":{"ns":0,"title":"Government budget deficits","missing":""}}
        }
    }
    is_missing = False
    try:
        redirects = get_wiki_info('government budget deficits')
    except Missing:
        is_missing = True
    assert is_missing

def cat_start(q):
    ret = web_get(cat_start_params + urlquote(q))
    return [doc['title'] for doc in ret['query']['allpages'] if doc['title'] != q]

def test_cat_start():
    global web_get
    web_get = lambda params: {"query":{"allpages":[]}}
    assert cat_start('test123') == []

def all_pages(q):
    ret = web_get(allpages_params + urlquote(q))
    return [doc['title'] for doc in ret['query']['allpages'] if doc['title'] != q]

def test_all_pages():
    global web_get
    web_get = lambda params: {"query":{"allpages":[{"pageid":312605,"ns":0,"title":"Government budget deficit"}]}}
    assert all_pages('Government budget deficit') == []

def categorymembers(q):
    ret = web_get(categorymembers_params + urlquote(q[0].upper()) + urlquote(q[1:]))
    return [doc['title'] for doc in ret['query']['categorymembers'] if doc['title'] != q]

def test_categorymembers():
    global web_get
    web_get = lambda params: {"query":{"categorymembers":[]}}
    assert categorymembers('test123') == []

def page_links(titles):
    titles = list(titles)
    assert titles
    ret = web_get(link_params + urlquote('|'.join(titles)))
    return dict((doc['title'], set(l['title'] for l in doc['links'])) for doc in ret['query']['pages'].itervalues() if 'links' in doc)

def is_disambig(doc):
    return any('disambig' in t or t.endswith('dis') or 'given name' in t or t == 'template:surname' for t in (t['title'].lower() for t in doc.get('templates', [])))

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
    return s[:-1] if s and s[-1] == 's' else s

re_redirect = re.compile(r'#REDIRECT \[\[(.)([^#]*?)(#.*)?\]\]')

def is_redirect_to(title_from, title_to):
    title_from = title_from.replace('_', ' ')
    ret = web_get('prop=info&titles=' + urlquote(title_from))
    print query_url + 'prop=info&titles=' + urlquote(title_from)
    if 'redirect' not in ret['query']['pages'].values()[0]:
        return False

    params = 'prop=revisions&rvprop=content&titles='
    ret = web_get(params + urlquote(title_from))
    page_text = ret['query']['pages'].values()[0]['revisions'][0]['*']
    m = re_redirect.match(page_text)
    title_to = title_to[0].upper() + title_to[1:]
    return m.group(1).upper() + m.group(2) == title_to

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
    while 'query-continue' in ret:
        blcontinue = ret['query-continue']['backlinks']['blcontinue']
        ret = web_get(backlink_params + urlquote(q) + '&blcontinue=' + urlquote(blcontinue))
        docs += ret['query']['backlinks']

    articles = set(doc['title'] for doc in docs if 'redirect' not in doc)
    redirects = set(doc['title'] for doc in docs if 'redirect' in doc)
    return (articles, redirects)

def test_en_dash():
    title = u'obsessive\u2013compulsive disorder'
    content = 'This is a obsessive-compulsive disorder test'
    for func in find_link_in_content, find_link_in_text:
        (c, r) = func(title, content)
        assert r == title
        assert c == u'This is a [[obsessive\u2013compulsive disorder]] test'

    content = 'This is a [[obsessive-compulsive]] disorder test'
    for func in find_link_in_content, find_link_in_text:
        (c, r) = func(title, content)
        assert r == title
        assert c == u'This is a [[obsessive\u2013compulsive disorder]] test'

def test_avoid_link_in_heading():
    tp = 'test phrase'
    content = '''
=== Test phrase ===

This sentence contains the test phrase.'''

    (c, r) = find_link_in_content(tp, content)
    assert c == content.replace(tp, '[[' + tp + ']]')
    assert r == tp

def test_parse_cite():
    sample = open('cite_parse_error').read().decode('utf-8')
    found_duty = False
    for a, b in parse_cite(sample):
        if 'duty' in b.lower():
            print (a, b)
            found_duty = True
    assert found_duty


re_cite = re.compile('<ref>\s*{{cite.*?}}\s*</ref>', re.I | re.S)
def parse_cite(text):
    prev = 0
    for m in re_cite.finditer(text):
        yield ('text', text[prev:m.start()])
        yield ('cite', m.group(0))
        prev = m.end()
    yield ('text', text[prev:])

def test_avoid_link_in_cite():
    tp = 'magic'
    content = 'test <ref>{{cite web|title=Magic|url=http://magic.com}}</ref>'
    (c, r) = find_link_in_content(tp, content + ' ' + tp)
    assert c == content + ' [[' + tp + ']]' 
    assert r == tp

    import py.test
    with py.test.raises(NoMatch):
        find_link_in_content(tp, content)

    tp = 'abc'
    content = '==Early life==\n<ref>{{cite news|}}</ref>abc'
    (c, r) = find_link_in_content(tp, content)
    assert c == content.replace(tp, '[[' + tp + ']]')
    assert r == tp

def test_find_link_in_content():
    get_case_from_content = lambda s: None
    import py.test
    with py.test.raises(NoMatch):
        find_link_in_content('foo', 'bar')

    with py.test.raises(NoMatch):
        input_content = 'Able to find this test\n\nphrase in an article.'
        find_link_in_content('test phrase', input_content)

    with py.test.raises(NoMatch):
        input_content = 'Able to find this test  \n  \n  phrase in an article.'
        find_link_in_content('test phrase', input_content)

    otrain = 'Ticketing on the O-Train works entirely on a proof-of-payment basis; there are no ticket barriers or turnstiles, and the driver does not check fares.'
    (c, r) = find_link_in_content('ticket barriers', otrain, linkto='turnstile')
    assert c == otrain.replace('turnstile', '[[turnstile]]')
    assert r == 'turnstile'

    sample = """On April 26, 2006, Snoop Dogg and members of his entourage were arrested after being turned away from [[British Airways]]' first class lounge at [[Heathrow Airport]]. Snoop and his party were not allowed to enter the lounge because some of the entourage were flying first class, other members in economy class. After the group was escorted outside, they vandalized a duty-free shop by throwing whiskey bottles. Seven police officers were injured in the midst of the disturbance. After a night in prison, Snoop and the other men were released on bail on April 27, but he was unable to perform at the Premier Foods People's Concert in [[Johannesburg]] on the same day. As part of his bail conditions, he had to return to the police station in May. The group has been banned by British Airways for "the foreseeable future."<ref>{{cite news|url=http://news.bbc.co.uk/1/hi/entertainment/4949430.stm |title=Rapper Snoop Dogg freed on bail |publisher=BBC News  |date=April 27, 2006 |accessdate=January 9, 2011}}</ref><ref>{{cite news|url=http://news.bbc.co.uk/1/hi/entertainment/4953538.stm |title=Rap star to leave UK after arrest |publisher=BBC News  |date=April 28, 2006 |accessdate=January 9, 2011}}</ref> When Snoop Dogg appeared at a London police station on May 11, he was cautioned for [[affray]] under [[Fear or Provocation of Violence|Section 4]] of the [[Public Order Act 1986|Public Order Act]] for use of threatening words or behavior.<ref>{{cite news|url=http://newsvote.bbc.co.uk/1/hi/entertainment/4761553.stm|title=Rap star is cautioned over brawl |date=May 11, 2006|publisher=BBC News |accessdate=July 30, 2009}}</ref> On May 15, the [[Home Office]] decided that Snoop Dogg should be denied entry to the United Kingdom for the foreseeable future due to the incident at Heathrow as well as his previous convictions in the United States for drugs and firearms offenses.<ref>{{cite web|url=http://soundslam.com/articles/news/news.php?news=060516_snoopb |title=Soundslam News |publisher=Soundslam.com |date=May 16, 2006 |accessdate=January 9, 2011}}</ref><ref>{{cite web|url=http://uk.news.launch.yahoo.com/dyna/article.html?a=/060516/340/gbrj1.html&e=l_news_dm |title=Snoop 'banned from UK' |publisher=Uk.news.launch.yahoo.com |accessdate=January 9, 2011}}</ref> Snoop Dogg's visa card was rejected by local authorities on March 24, 2007 because of the Heathrow incident.<ref>{{cite news |first=VOA News |title=Rapper Snoop Dogg Arrested in UK |date=April 27, 2006 |publisher=Voice of America |url=http://classic-web.archive.org/web/20060603120934/http://voanews.com/english/archive/2006-04/2006-04-27-voa17.cfm |work=VOA News |accessdate=December 31, 2008}}</ref> A concert at London's Wembley Arena on March 27 went ahead with Diddy (with whom he toured Europe) and the rest of the show."""

    (c, r) = find_link_in_content('duty-free shop', sample)
    assert c == sample.replace('duty-free shop', '[[duty-free shop]]')
    assert r == 'duty-free shop'

    pseudocode1 = 'These languages are typically [[Dynamic typing|dynamically typed]], meaning that variable declarations and other [[Boilerplate_(text)#Boilerplate_code|boilerplate code]] can be omitted.'

    for func in find_link_in_content, find_link_in_text:
        (c, r) = func('boilerplate code', pseudocode1)
        assert c == pseudocode1.replace('Boilerplate_(text)#Boilerplate_code|', '')
        assert r == 'boilerplate code'

    pseudocode2 = 'Large amounts of [[boilerplate (text)#Boilerplate code|boilerplate]] code, such as manual definitions of type casting macros and obscure type registration incantations, are necessary to create a new class.'
    for func in find_link_in_content, find_link_in_text:
        (c, r) = func('boilerplate code', pseudocode2)
        assert c == pseudocode2.replace('(text)#Boilerplate code|boilerplate]] code', 'code]]')
        assert r == 'boilerplate code'

    yard = "primary [[Hump yard|hump classification yards]] are located in Allentown."
    for func in find_link_in_content, find_link_in_text:
        (c, r) = func('classification yard', yard)
        assert c == yard.replace('[[Hump yard|hump classification yards]]', 'hump [[classification yard]]s')
        assert r == 'classification yard'

    #yard2 = 'For the section from [[Rotterdam]] to the large [[Kijfhoek (classification yard)|classification yard Kijfhoek]] existing track was reconstructed, but three quarters of the line is new, from Kijfhoek to [[Zevenaar]] near the German border.'
    #(c, r) = find_link_in_text('classification yard', yard2)

    station = 'Ticket barriers control access to all platforms, although the bridge entrance has no barriers.'
    (c, r) = find_link_in_content('ticket barriers', station, linkto='turnstile')
    assert c == station.replace('Ticket barriers', '[[Turnstile|Ticket barriers]]')
    assert r == 'Turnstile|Ticket barriers'

    content = [
        'Able to find this test phrase in an article.',
        'Able to find this test  phrase in an article.',
        'Able to find this test\n  phrase in an article.',
        'Able to find this test  \nphrase in an article.',
        'Able to find this test\nphrase in an article.',
        'Able to find this test-phrase in an article.', 
        'Able to find this test PHRASE in an article.', 
        'Able to find this TEST PHRASE in an article.', 
        'Able to find this test\nPhrase in an article.', 
        'Able to find this [[test]] phrase in an article.',
        'Able to find this TEST [[PHRASE]] in an article.', 
        'Able to find this [[testing|test]] phrase in an article.',
        'Able to find this testphrase in an article.']

    for input_content in content:
        for func in find_link_in_content, find_link_in_text:
            (c, r) = func('test phrase', input_content)
            assert c == 'Able to find this [[test phrase]] in an article.'
            assert r == 'test phrase'

    global web_get
    title = 'London congestion charge'
    web_get = lambda params: {
        'query': { 'pages': { 1: { 'revisions': [{
            '*': "'''" + title + "'''"
            }]}}
    }}

    article = 'MyCar is exempt from the London Congestion Charge, road tax and parking charges.'
    for func in find_link_in_content, find_link_in_text:
        (c, r) = func('London congestion charge', article)
        assert r == 'London congestion charge'

class NoMatch(Exception):
    pass

re_heading = re.compile(r'^\s*(=+)\s*(.+)\s*\1\s*$')
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

def test_section_iter():
    assert list(section_iter('test')) == [(None, 'test')]
    text = '''==Heading==
Paragraph'''
    text = '''==Heading 1 ==
Paragraph 1.
==Heading 2 ==
Paragraph 2.
'''
    assert list(section_iter(text)) == [('==Heading 1 ==\n', 'Paragraph 1.\n'), ('==Heading 2 ==\n', 'Paragraph 2.\n')]

en_dash = u'\u2013'
trans = { ',': ',?', ' ': ' *[-\n]? *' }
trans[en_dash] = trans[' ']

trans2 = { ' ': r"('?s?\]\])?'?s? ?(\[\[)?" }
trans2[en_dash] = trans2[' ']

patterns = [
    lambda q: re.compile('\[\[[^|]+\|(%s)%s\]\]' % (q[0], q[1:]), re.I),
    lambda q: re.compile('\[\[[^|]+\|(%s)%s(?:\]\])?' % (q[0], ''.join('-?' + trans2.get(c, c) for c in q[1:])), re.I),
    lambda q: re.compile('(%s)%s' % (q[0], q[1:]), re.I),
    lambda q: re.compile('(%s)%s' % (q[0], ''.join(trans.get(c, c) for c in q[1:])), re.I),
    lambda q: re.compile(r'(?:\[\[(?:[^]]+\|)?)?(%s)%s(?:\]\])?' % (q[0], ''.join('-?' + trans2.get(c, c) for c in q[1:])), re.I),
]

def test_patterns():
    q = 'San Francisco'
    assert patterns[2](q).pattern == '(S)' + q[1:]
    assert patterns[3](q).pattern == '(S)an *[-\n]? *' + q[4:]

def match_found(m, q, linkto):
    if q[1:] == m.group(0)[1:]:
        replacement = m.group(1) + q[1:]
    elif any(c.isupper() for c in q[1:]) or m.group(0) == m.group(0).upper():
        replacement = q
    elif is_title_case(m.group(0)):
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

re_link_in_text = re.compile(r'\[\[[^]]+?\]\]', re.I | re.S)
def parse_links(text):
    prev = 0
    for m in re_link_in_text.finditer(text):
        yield ('text', text[prev:m.start()])
        yield ('link', m.group(0))
        prev = m.end()
    yield ('text', text[prev:])

def find_link_in_text_old(q, text):
    for pattern in patterns:
        re_link = pattern(q)
        m = re_link.search(text)
        if m:
            replacement = match_found(m, q, None)
            text = re_link.sub(lambda m: "[[%s]]" % replacement, text, count=1)
            return (text, replacement)
    raise NoMatch

def find_link_in_text(q, content): 
    new_content = ''
    replacement = None

    re_links = [p(q) for p in patterns]

    for token_type, text in parse_links(content):
        if token_type == 'link':
            link_text = text[2:-2]
            link_dest = None
            if '|' in link_text:
                link_dest, link_text = link_text.split('|', 1)
            for re_link in re_links:
                m = re_link.search(link_text)
                if m:
                    replacement = match_found(m, q, None)
                    text = re_link.sub(lambda m: "[[%s]]" % replacement, link_text, count=1)
                    break
        new_content += text
    if replacement:
        return (new_content, replacement)

    for re_link in re_links:
        m = re_link.search(content)
        if m:
            replacement = match_found(m, q, None)
            content = re_link.sub(lambda m: "[[%s]]" % replacement, content, count=1)
            return (content, replacement)
    raise NoMatch

def find_link_in_content(q, content, linkto=None):
    if linkto:
        try:
            return find_link_in_content(linkto, content)
        except NoMatch:
            pass
    sections = list(section_iter(content))
    re_links = [p(q) for p in patterns]
    replacement = None
    new_content = ''
    for header, section_text in sections:
        if header:
            new_content += header 
        for token_type, text in parse_cite(section_text):
            if token_type == 'text' and not replacement:
                new_text = ''
                for token_type2, text2 in parse_links(content):
                    if token_type2 == 'link' and not replacement:
                        link_text = text2[2:-2]
                        if '|' in link_text:
                            link_dest, link_text = link_text.split('|', 1)
                        for re_link in re_links:
                            m = re_link.search(link_text)
                            if m:
                                replacement = match_found(m, q, None)
                                text2 = re_link.sub(lambda m: "[[%s]]" % replacement, link_text, count=1)
                                break
                    new_text += text2
                if replacement:
                    text = new_text
                else:
                    for re_link in re_links:
                        m = re_link.search(text)
                        if m:
                            replacement = match_found(m, q, linkto)
                            text = re_link.sub(lambda m: "[[%s]]" % replacement, text, count=1)
                            break
            new_content += text
    if replacement:
        return (new_content, replacement)
    raise NoMatch

def find_link_and_section(q, content, linkto=None):
    if linkto:
        try:
            return find_link_and_section(linkto, content)
        except NoMatch:
            pass
    re_link = re.compile('([%s%s])%s' % (q[0].lower(), q[0].upper(), q[1:]))
    sections = list(section_iter(content))
    replacement = None
    for pattern in patterns:
        re_link = pattern(q)
        for section_num, (header, section_text) in enumerate(sections):
            new_content = ''
            if header:
                new_content += header 
            for token_type, text in parse_cite(section_text):
                if token_type == 'text' and not replacement:
                    m = re_link.search(text)
                    if m:
                        replacement = match_found(m, q, linkto)
                        text = re_link.sub(lambda m: "[[%s]]" % replacement, text, count=1)
                new_content += text
            if replacement:
                return {
                    'section_num': section_num,
                    'section_text': new_content.strip(),
                    'replacement': replacement,
                }
    raise NoMatch

def test_get_case_from_content(): # test is broken
    global web_get
    title = 'London congestion charge'
    web_get = lambda params: {
        'query': { 'pages': { 1: { 'revisions': [{
            '*': "'''" + title + "'''"
            }]}}
    }}
    assert get_case_from_content(title) == title

def get_case_from_content(title):
    ret = web_get(content_params + urlquote(title))
    rev = ret['query']['pages'].values()[0]['revisions'][0]
    content = rev['*']
    start = content.lower().find("'''" + title.replace('_', ' ').lower() + "'''")
    if start != -1:
        return content[start+3:start+3+len(title)]

@app.route('/diff')
def diff_view():
    q = request.args.get('q')
    title = request.args.get('title')
    linkto = request.args.get('linkto')

    ret = web_get(content_params2 + urlquote(title))
    page = ret['query']['pages'].values()[0]
    #edittoken = page['edittoken']
    #print 'token:', edittoken
    rev = page['revisions'][0]
    content = rev['*']
    try:
        found = find_link_and_section(q, content, linkto)
    except NoMatch:
        return None

    #print found['section_num'], found['replacement'], len(found['section_text'])

    diff_params = "prop=revisions&rvprop=timestamp&titles=%s&rvsection=%d&rvdifftotext=%s" % (urlquote(title), found['section_num'], urlquote(found['section_text']))

    ret = web_post(diff_params)
    diff = ret['query']['pages'].values()[0]['revisions'][0]['diff']['*']
    #pprint(ret['query']['pages'].values()[0])

    return '<table>' + diff + '</table>'

def get_page(title, q, linkto=None):
    ret = web_get(content_params + urlquote(title))
    rev = ret['query']['pages'].values()[0]['revisions'][0]
    content = rev['*']
    timestamp = rev['timestamp']
    timestamp = ''.join(c for c in timestamp if c.isdigit())

    try:
        (content, replacement) = find_link_in_content(q, content, linkto)
    except NoMatch:
        return None

    diff_url = "prop=revisions&rvprop=timestamp&titles=%s&rvdifftotext=%s" % (urlquote(title), urlquote(content))
    #pprint(web_post(diff_url), stream=open('wikidiff', 'w'))

    summary = "link [[%s]] using [[User:Edward/Find link|Find link]]" % replacement
    #text = "title: %s\nq: %s\nsummary: %s\ntimestamp: %s\n\n%s" % (title, q, timestamp, summary, content)

    start_time = datetime.now().strftime("%Y%m%d%H%M%S")
    return render_template('find_link.html',
            urlquote=urlquote,
            start_time=start_time,
            content=content,
            title=title, summary=summary, timestamp=timestamp)

def case_flip(s):
    if s.islower():
        return s.upper()
    if s.isupper():
        return s.lower()
    return s
def case_flip_first(s):
    return case_flip(s[0]) + s[1:]

def match_type(q, snippet):
    q = q.replace(u'\u2013', '-')
    snippet = snippet.replace(u'\u2013', '-')
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
 
def test_match_type():
    assert match_type('foo', 'foo') == 'exact'
    assert match_type('foo', 'bar') == None
    assert match_type('bar', 'foo bar baz') == 'exact'
    assert match_type('clean coal technology', 'foo clean coal technologies baz') == 'exact'
    assert match_type('bar', 'foo Bar baz') == 'exact'
    assert match_type('bar', 'foo BAR baz') == 'case_mismatch'
    assert match_type('foo-bar', 'aa foo-bar cc') == 'exact'
    assert match_type(u'foo\u2013bar', 'aa foo-bar cc') == 'exact'

@app.route("/<path:q>")
def findlink(q, title=None, message=None):
    q_trim = q.strip('_')
    if not message and (' ' in q or q != q_trim):
        return redirect(url_for('findlink', q=q.replace(' ', '_').strip('_'), message=message))
    q = q.replace('_', ' ').strip()
    try:
        redirect_to = get_wiki_info(q)
    except Missing:
        return render_template('index.html', message=q + " isn't an article")
    #if redirect_to:
    #    return redirect(url_for('findlink', q=redirect_to.replace(' ', '_')))
    if redirect_to:
        if q[0].isupper():
            redirect_to = redirect_to[0].upper() +  redirect_to[1:]
        elif q[0].islower():
            redirect_to = redirect_to[0].lower() +  redirect_to[1:]
    this_title = q[0].upper() + q[1:]
    (totalhits, search) = wiki_search(q)
    (articles, redirects) = wiki_backlink(redirect_to or q)
    cm = set()
    for cat in set(['Category:' + this_title] + cat_start(q)):
        cm.update(categorymembers(cat))
    norm_q = norm(q)
    norm_match_redirect = set(r for r in redirects if norm(r) == norm_q)
    longer_redirect = set(r for r in redirects if q.lower() in r.lower())

    articles.add(this_title)
    if redirect_to:
        articles.add(redirect_to[0].upper() + redirect_to[1:])
    for r in norm_match_redirect | longer_redirect:
        articles.add(r)
        a2, r2 = wiki_backlink(r)
        articles.update(a2)
        redirects.update(r2)

    longer = all_pages(this_title)
    lq = q.lower()
    for doc in search:
        lt = doc['title'].lower()
        if lt != lt and lq in lt:
            articles.add(doc['title'])
            (more_articles, more_redirects) = wiki_backlink(doc['title'])
            articles.update(more_articles)
            if doc['title'] not in longer:
                longer.append(doc['title'])

    search = [doc for doc in search if doc['title'] not in articles and doc['title'] not in cm]
    if search:
        disambig = set(find_disambig([doc['title'] for doc in search]))
        search = [doc for doc in search if doc['title'] not in disambig]
    # and (doc['title'] not in links or this_title not in links[doc['title']])]
        for doc in search:
            without_markup = doc['snippet'].replace("<span class='searchmatch'>", "").replace("</span>", "").replace('  ', ' ')
            doc['match'] = match_type(q, without_markup)
            doc['snippet'] = Markup(doc['snippet'])
    return render_template('index.html', q=q,
        totalhits = totalhits,
        message = message,
        results = search,
        urlquote = urlquote,
        commify = commify,
        enumerate = enumerate,
        longer_titles = longer,
        redirect_to = redirect_to,
        norm_match_redirect = norm_match_redirect,
        case_flip_first = case_flip_first)

@app.route("/favicon.ico")
def favicon():
    return redirect(url_for('static', filename='Link_edit.png'))

@app.route("/new_pages")
def newpages():
    np = web_get(new_page_params)['query']['recentchanges']
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
        return findlink(q.replace(' ', '_'), title=title, message=q + ' not in ' + title)
    if q:
        return redirect(url_for('findlink', q=q.replace(' ', '_').strip('_')))
    return render_template('index.html')

if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=True)
