# coding=utf-8
import urllib
import json
import re
from time import time
from datetime import datetime
from pprint import pprint

from flask import Flask, render_template, request, Markup, redirect, url_for

app = Flask(__name__)
app.config.from_pyfile('config')

query_url = 'https://en.wikipedia.org/w/api.php?format=json&action=query&'
#srprop = 'size|wordcount|timestamp|score|snippet|titlesnippet|sectionsnippet|sectiontitle|redirectsnippet|redirecttitle|hasrelated'
search_params          = 'list=search' '&srwhat=text' '&srlimit=50&srsearch='
new_page_params        = 'list=recentchanges' '&rclimit=50' '&rctype=new' '&rcnamespace=0' '&rcshow=!redirect'
backlink_params        = 'list=backlinks' '&bllimit=500' '&blnamespace=0' '&bltitle='
redirect_params        = 'list=backlinks' '&blfilterredir=redirects' '&bllimit=500' '&blnamespace=0' '&bltitle='
content_params         = 'prop=revisions|info' '&rvprop=content|timestamp' '&titles='
link_params            = 'prop=links' '&pllimit=500' '&plnamespace=0' '&titles='
templates_params       = 'prop=templates' '&tllimit=500' '&tlnamespace=10' '&titles='
allpages_params        = 'list=allpages' '&apnamespace=0' '&apfilterredir=nonredirects' '&aplimit=500' '&apprefix='
info_params            = 'action=query' '&prop=info' '&redirects' '&titles='
categorymembers_params = 'action=query' '&list=categorymembers' '&cmnamespace=0' '&cmlimit=500' '&cmtitle='
cat_start_params       = 'list=allpages' '&apnamespace=14' '&apfilterredir=nonredirects' '&aplimit=500' '&apprefix='

save_to_cache = False

def commify(amount):
    "return a number with commas, use for word count"
    return '{:,}'.format(int(amount))

def test_commify():
    "test commify"
    assert commify(1) == '1'
    assert commify(2222) == '2,222'
    assert commify('3333') == '3,333'

re_space_or_dash = re.compile('[ -]')
def is_title_case(phrase):
    return all(term[0].isupper() and term[1:].islower() 
               for term in re_space_or_dash.split(phrase))

def test_is_title_case():
    assert is_title_case('Test')
    assert is_title_case('Test Test')
    assert not is_title_case('test')
    assert not is_title_case('TEST TEST')
    assert not is_title_case('test test')
    assert not is_title_case('tEst Test')

class AppURLopener(urllib.FancyURLopener):
    version = "find-link/2.0 (contact: edward@4angle.com)"

urllib._urlopener = AppURLopener()

def urlquote(value):
    '''prepare string for use in URL param'''
    return urllib.quote_plus(value.encode('utf-8'))

def test_urlquote():
    '''test urlquote'''
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
    try:
        return json.loads(data)
    except ValueError:
        print data
        raise
orig_web_get = web_get

def web_post(params):
    '''POST to Wikipedia API'''
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
    web_get = orig_web_get

def cat_start(q):
    ret = web_get(cat_start_params + urlquote(q))
    return [doc['title'] for doc in ret['query']['allpages'] if doc['title'] != q]

def test_cat_start():
    global web_get
    web_get = lambda params: {"query":{"allpages":[]}}
    assert cat_start('test123') == []
    web_get = orig_web_get

def all_pages(q):
    ret = web_get(allpages_params + urlquote(q))
    return [doc['title'] for doc in ret['query']['allpages'] if doc['title'] != q]

def test_all_pages():
    global web_get
    web_get = lambda params: {"query":{"allpages":[{"pageid":312605,"ns":0,"title":"Government budget deficit"}]}}
    assert all_pages('Government budget deficit') == []
    web_get = orig_web_get

def categorymembers(q):
    ret = web_get(categorymembers_params + urlquote(q[0].upper()) + urlquote(q[1:]))
    return [doc['title'] for doc in ret['query']['categorymembers'] if doc['title'] != q]

def test_categorymembers():
    global web_get
    web_get = lambda params: {"query":{"categorymembers":[]}}
    assert categorymembers('test123') == []
    web_get = orig_web_get

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
    if 'query' not in ret:
        print 'backlink'
        pprint(ret)
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
    (c, r) = find_link_in_content(title, content)
    assert r == title
    assert c == u'This is a [[obsessive\u2013compulsive disorder]] test'

    (c, r) = find_link_in_text(title, content)
    assert r == title
    assert c == u'This is a [[obsessive\u2013compulsive disorder]] test'

    content = 'This is a [[obsessive-compulsive]] disorder test'

    (c, r) = find_link_in_content(title, content)
    assert r == title
    assert c == u'This is a [[obsessive\u2013compulsive disorder]] test'

    (c, r) = find_link_in_text(title, content)
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


re_cite = re.compile(r'<ref( [^>]*?)?>\s*({{cite.*?}}|\[https?://[^]]*?\])\s*</ref>', re.I | re.S)
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
    global web_get
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

    sample = '[[Retriever]]s are typically used when [[waterfowl]] hunting. Since a majority of waterfowl hunting employs the use of small boats'

    for func in find_link_in_content, find_link_in_text:
        (c, r) = func('waterfowl hunting', sample)
        assert c == sample.replace(']] hunting', ' hunting]]')
        assert r == 'waterfowl hunting'

    sample = 'abc [[File:Lufschiffhafen Jambol.jpg|thumb|right|Jamboli airship hangar in Bulgaria]] abc'
    q = 'airship hangar'
    for func in find_link_in_content, find_link_in_text:
        (c, r) = func(q, sample)
        assert c == sample.replace(q, '[[' + q + ']]')
        assert r == q

    sample = 'It is relatively easy for insiders to capture insider-trading like gains through the use of "open market repurchases."  Such transactions are legal and generally encouraged by regulators through safeharbours against insider trading liability.'
    q = 'insider trading'

    q = 'ski mountaineering' # Germán Cerezo Alonso 
    sample = 'started ski mountaineering in 1994 and competed first in the 1997 Catalunyan Championship. He finished fifth in the relay event of the [[2005 European Championship of Ski Mountaineering]].'

    for func in find_link_in_content, find_link_in_text:
        (c, r) = func(q, sample)
        assert c == sample.replace(q, '[[' + q + ']]')
        assert r == q

    q = 'two-factor authentication'
    sample = "Two factor authentication is a 'strong authentication' method as it"

    for func in find_link_in_content, find_link_in_text:
        (c, r) = func(q, sample)
        assert c == "[[Two-factor authentication]] is a 'strong authentication' method as it"
        assert r == q[0].upper() + q[1:]

    q = 'post-World War II baby boom'
    sample = 'huge boost during the post World War II [[Baby Boomer|Baby Boom]].'
    for func in find_link_in_content, find_link_in_text:
        (c, r) = func(q, sample)
        assert c == 'huge boost during the [[post-World War II baby boom]].'
        assert r == q

    q = 'existence of God'
    sample = 'with "je pense donc je suis" or "[[cogito ergo sum]]" or "I think, therefore I am", argued that "the self" is something that we can know exists with [[epistemology|epistemological]] certainty. Descartes argued further that this knowledge could lead to a proof of the certainty of the existence of [[God]], using the [[ontological argument]] that had been formulated first by [[Anselm of Canterbury]].{{Citation needed|date=January 2012}}'
    for func in find_link_in_content, find_link_in_text:
        (c, r) = func(q, sample)
        assert c == sample.replace('existence of [[God', '[[existence of God')
        assert r == q

    q = 'existence of God'
    sample = '[[Intelligent design]] is an [[Teleological argument|argument for the existence of God]],'
    for func in find_link_in_content, find_link_in_text:
        with py.test.raises(LinkReplace):
            func(q, sample)

    q = 'correlation does not imply causation'
    sample = 'Indeed, an important axiom that social scientists cite, but often forget, is that "[[correlation]] does not imply [[Causality|causation]]."'
    for func in find_link_in_content, find_link_in_text:
        (c, r) = func(q, sample)
        assert c == 'Indeed, an important axiom that social scientists cite, but often forget, is that "[[correlation does not imply causation]]."'
        assert r == q

    pseudocode1 = 'These languages are typically [[Dynamic typing|dynamically typed]], meaning that variable declarations and other [[Boilerplate_(text)#Boilerplate_code|boilerplate code]] can be omitted.'

    for func in find_link_in_content, find_link_in_text:
        (c, r) = func('boilerplate code', pseudocode1)
        assert c == pseudocode1.replace('Boilerplate_(text)#Boilerplate_code|', '')
        assert r == 'boilerplate code'

    pseudocode2 = 'Large amounts of [[boilerplate (text)#Boilerplate code|boilerplate]] code.'
    for func in find_link_in_content, find_link_in_text:
        (c, r) = func('boilerplate code', pseudocode2)
        assert c == pseudocode2.replace('(text)#Boilerplate code|boilerplate]] code', 'code]]')
        assert r == 'boilerplate code'

    sample = 'particularly to handle the peak volumes of work generated by Payment Protection Insurance complaints.'
    (c, r) = find_link_in_content('payment protection insurance', sample)
    assert 'payment protection insurance' in c
    (c, r) = find_link_in_text('payment protection insurance', sample)
    assert 'payment protection insurance' in c

    if False:
        sample = 'further investigations on [[Extrajudicial punishment|extrajudicial killings]] by police forces.'
        q = 'extrajudicial killing'
        (c, r) = find_link_in_content(q, sample)
        assert q in c
        (c, r) = find_link_in_text(q, sample)
        assert q in c

    sample = 'units formed with [[SI prefix|metric prefixes]], such as kiloseconds'
    find_link_in_content('metric prefix', sample)

    sample = u"==Geography==\nA gem of Bermuda's coastline, it is surrounded by [[St. George's Parish, Bermuda|St. George's Parish]] in the north, east, south (Tucker's Town), and [[Hamilton Parish, Bermuda|Hamilton Parish]] in the west. A chain of islands and rocks stretches across the main opening to the [[Atlantic Ocean]], in the east, notably [[Cooper's Island, Bermuda|Cooper's Island]] (which was made a landmass contiguous to St. David's Island and Longbird Island in the 1940s), and [[Nonsuch Island, Bermuda|Nonsuch Island]]. The only channel suitable for large vessels to enter the harbour from the open Atlantic is [[Castle Roads, Bermuda|Castle Roads]], which was historically guarded by a number of fortifications, on [[Castle Island, Bermuda|Castle Island]], Brangman's Island, and Goat Island. Forts were also placed nearby on other small islands, and on the Tucker's Town peninsula of the Main Island. In the west, [[The Causeway, Bermuda|The Causeway]] crosses from the main island to St. David's Island, and beyond this a stretch of water known as [[Ferry Reach, Bermuda|Ferry Reach]] connects the harbour with [[St. George's Harbor, Bermuda|St. George's Harbour]] to the north, where Bermuda's first permanent settlement, [[St. George's, Bermuda|St. George's Town]], was founded in 1612. An unincorporated settlement, [[Tucker's Town, Bermuda|Tucker's Town]], was established on the [[peninsula]] of the [[Main Island, Bermuda|Main Island]] at the south-west of the harbour. The settlement was cleared by compulsory purchase order in the 1920s in order to create a luxury enclave where homes could be purchased by wealthy foreigners, and the attendant Mid Ocean Golf Club. In [[Hamilton Parish, Bermuda|Hamilton Parish]], on the western shore of the harbour, lies [[Walsingham Bay, Bermuda|Walsingham Bay]], the site where, in 1609-10, the crew of the wrecked [[Sea Venture]] built the ''[[Patience]]'', one of two ships built, which carried most of the survivors of the wrecking to [[Jamestown, Virginia|Jamestown]], [[Virginia]], in 1610. The ''Patience'' returned to Bermuda with [[George Somers|Admiral Sir George Somers]], who died in Bermuda later that year."
    find_link_in_content('compulsory purchase order', sample)

    if False:
        yard = "primary [[Hump yard|hump classification yards]] are located in Allentown."
        for func in find_link_in_content, find_link_in_text:
            (c, r) = func('classification yard', yard)
            assert c == yard.replace('[[Hump yard|hump classification yards]]', 'hump [[classification yard]]s')
            assert r == 'classification yard'

        yard2 = 'A major [[hump yard|railway classification yard]] is north of Blenheim at [[Spring Creek, New Zealand|Spring Creek]].'
        for func in find_link_in_content, find_link_in_text:
            (c, r) = func('classification yard', yard2)
            assert c == yard2.replace('[[hump yard|railway classification yard]]', 'railway [[classification yard]]')
            assert r == 'classification yard'

    yard3 = 'Five houses were destroyed and three others were damaged. A high school was also heavily damaged and railroad cars were thrown in a small freight classification yard. Four people were injured.'
    for func in find_link_in_content, find_link_in_text:
        (c, r) = func('classification yard', yard3)
        assert c == yard3.replace('classification yard', '[[classification yard]]')
        assert r == 'classification yard'

    #yard2 = 'For the section from [[Rotterdam]] to the large [[Kijfhoek (classification yard)|classification yard Kijfhoek]] existing track was reconstructed, but three quarters of the line is new, from Kijfhoek to [[Zevenaar]] near the German border.'
    #(c, r) = find_link_in_text('classification yard', yard2)

    if False:
        sample = 'GEHA also has a contract with the federal government to administer benefits for the [[Pre-existing Condition Insurance Plan]], which will be a transitional program until 2014.'
        q = 'pre-existing condition'
        for func in find_link_in_content, find_link_in_text:
            with py.test.raises(NoMatch):
                func(q, sample)

    station = 'Ticket barriers control access to all platforms, although the bridge entrance has no barriers.'
    (c, r) = find_link_in_content('ticket barriers', station, linkto='turnstile')
    print 'failing'
    print c
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
    web_get = orig_web_get

class NoMatch(Exception):
    pass

class BadLinkMatch(Exception):
    pass

class LinkReplace(Exception):
    pass

re_heading = re.compile(r'^\s*(=+)\s*(.+)\s*\1(<!--.*-->|\s)*$')
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
    assert list(section_iter(text)) == [
        ('==Heading 1 ==\n', 'Paragraph 1.\n'),
        ('==Heading 2 ==\n', 'Paragraph 2.\n')
    ]

def get_subsetions(text, section_num):
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
                found += heading+body
            else:
                break
    return found

def test_get_subsections():
    text = '''==Heading 1 ==
Paragraph 1.
==Heading 2 ==
Paragraph 2.
===Level 2===
Paragraph 3.
==Heading 4==
Paragraph 4.
'''
    assert get_subsetions(text, 4) == ''

    assert get_subsetions(text, 4) == ''

en_dash = u'\u2013'
trans = { ',': ',?', ' ': ' *[-\n]? *' }
trans[en_dash] = trans[' ']

trans2 = { ' ': r"('?s?\]\])?'?s? ?(\[\[(?:.+\|)?)?", '-': '[- ]' }
trans2[en_dash] = trans2[' ']

patterns = [
    lambda q: re.compile(r'(?:\[\[(?:[^]]+\|)?)?(%s)%s(?:\]\])?' % (q[0], ''.join('-?' + trans2.get(c, c) for c in q[1:])), re.I),
    lambda q: re.compile('\[\[[^|]+\|(%s)%s\]\]' % (q[0], q[1:]), re.I),
    lambda q: re.compile('\[\[[^|]+\|(%s)%s(?:\]\])?' % (q[0], ''.join('-?' + trans2.get(c, c) for c in q[1:])), re.I),
    lambda q: re.compile('(%s)%s' % (q[0], q[1:]), re.I),
    lambda q: re.compile('(%s)%s' % (q[0], ''.join(trans.get(c, c) for c in q[1:])), re.I),
]

def test_patterns():
    q = 'San Francisco'
    assert patterns[3](q).pattern == '(S)' + q[1:]
    assert patterns[4](q).pattern == '(S)an *[-\n]? *' + q[4:]

def test_match_found():
    l = 'payment protection insurance'
    l2 = 'payment Protection Insurance'
    m = re.compile('(P)' + l[1:], re.I).match('P' + l2[1:])
    assert match_found(m, l, None) == l

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

re_link_in_text = re.compile(r'\[\[[^]]+?\]\]', re.I | re.S)
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
            if m:
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
            raise BadLinkMatch
        m = search_for_link(content)
        if m:
            replacement = match_found(m, q, linkto)
            new_content = add_link(m, replacement, content)
    return (new_content, replacement)

def find_link_in_text(q, content): 
    try:
        (new_content, replacement) = find_link_in_chunk(q, content)
    except BadLinkMatch:
        raise LinkReplace
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
                except BadLinkMatch:
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

def test_get_case_from_content(): # test is broken
    global web_get
    title = 'London congestion charge'
    web_get = lambda params: {
        'query': { 'pages': { 1: { 'revisions': [{
            '*': "'''" + title + "'''"
            }]}}
    }}
    assert get_case_from_content(title) == title
    web_get = orig_web_get

def get_case_from_content(title):
    ret = web_get(content_params + urlquote(title))
    rev = ret['query']['pages'].values()[0]['revisions'][0]
    content = rev['*']
    if title == title.lower() and title in content:
        return title
    start = content.lower().find("'''" + title.replace('_', ' ').lower() + "'''")
    if start != -1:
        return content[start+3:start+3+len(title)]

def get_diff(q, title, linkto):
    content, timestamp = get_content_and_timestamp(title)
    found = find_link_and_section(q, content, linkto)

    section_text = found['section_text'] + get_subsetions(content,
                                                          found['section_num'])

    diff_params = "prop=revisions&rvprop=timestamp&titles=%s&rvsection=%d&rvdifftotext=%s" % (urlquote(title), found['section_num'], urlquote(section_text.strip()))

    ret = web_post(diff_params)
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
    ret = web_get(content_params + urlquote(title))
    rev = ret['query']['pages'].values()[0]['revisions'][0]
    content = rev['*']
    timestamp = rev['timestamp']
    return (content, timestamp)

def get_page(title, q, linkto=None):
    content, timestamp = get_content_and_timestamp(title)
    timestamp = ''.join(c for c in timestamp if c.isdigit())

    try:
        (content, replacement) = find_link_in_content(q, content, linkto)
    except NoMatch:
        return None

    diff_url = "prop=revisions&rvprop=timestamp&titles=%s&rvdifftotext=%s" % (urlquote(title), urlquote(content))

    summary = "link [[%s]] using [[User:Edward/Find link|Find link]]" % replacement

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

def do_search(q, redirect_to):
    this_title = q[0].upper() + q[1:]

    totalhits, search = wiki_search(q)
    articles, redirects = wiki_backlink(redirect_to or q)
    cm = set()
    for cat in set(['Category:' + this_title] + cat_start(q)):
        cm.update(categorymembers(cat))

    norm_q = norm(q)
    norm_match_redirect = set(r for r in redirects if norm(r) == norm_q)
    longer_redirect = set(r for r in redirects if q.lower() in r.lower())

    articles.add(this_title)
    if redirect_to:
        articles.add(redirect_to[0].upper() + redirect_to[1:])

    longer_redirect = set(r for r in redirects if q.lower() in r.lower())
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
            more_articles, more_redirects = wiki_backlink(doc['title'])
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
            doc['snippet_without_markup'] = without_markup
    return {
        'totalhits': totalhits,
        'results': search,
        'longer': longer,
    }

@app.route("/<path:q>")
def findlink(q, title=None, message=None):
    if q and '%' in q: # double encoding
        q = urllib.unquote(q)
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

    ret = do_search(q, redirect_to)

    for doc in ret['results']:
        doc['snippet'] = Markup(doc['snippet'])

    return render_template('index.html', q=q,
        totalhits = ret['totalhits'],
        message = message,
        results = ret['results'],
        urlquote = urlquote,
        commify = commify,
        str = str,
        enumerate = enumerate,
        longer_titles = ret['longer'],
        redirect_to = redirect_to,
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
