# coding=utf-8
import os
import re
import json
import unittest
import responses
import find_link
import urllib.parse
from unittest.mock import patch

def wiki_url(params):
    default = {
        'action': 'query',
        'formatversion': 2,
        'format': 'json',
    }
    base = 'https://en.wikipedia.org/w/api.php?'
    url = base + urllib.parse.urlencode({**default, **params})
    print(url)

    return url

class TestFindLink(unittest.TestCase):
    @responses.activate
    def test_get_case_from_content(self):
        title = 'London congestion charge'
        url = wiki_url({
            'prop': 'revisions|info',
            'rvprop': 'content|timestamp',
            'titles': title,
        })
        body = """{"query":{"pages":[{"revisions":[{"timestamp":"2015-08-07T15:37:03Z","content":"The '''London congestion charge''' is a fee charged on most motor vehicles operating within the Congestion Charge Zone (CCZ)"}]}]}}"""
        responses.add(responses.GET, url, body=body, match_querystring=True)
        self.assertEqual(find_link.core.get_case_from_content(title), title)

        article = 'MyCar is exempt from the London Congestion Charge, road tax and parking charges.'
        for func in find_link.match.find_link_in_content, find_link.match.find_link_in_text:
            (c, r) = func('London congestion charge', article)
            self.assertEqual(r, 'London congestion charge')

    @responses.activate
    def test_get_wiki_info(self):
        body = json.dumps({
            "query": {
                "normalized": [{
                    "from": "government budget deficit",
                    "to": "Government budget deficit"
                }],
                "pages": [{
                    "pageid": 312605,
                    "ns": 0,
                    "title": "Government budget deficit",
                    "touched": "2011-11-24T22:06:21Z",
                    "lastrevid": 462258859,
                    "counter": "",
                    "length": 14071
                }]
            }
        })

        url = wiki_url({
            'redirects': '',
            'titles': 'government budget deficit',
            'prop': 'info',
        })
        responses.add(responses.GET, url, body=body, match_querystring=True)

        redirect = find_link.api.get_wiki_info('government budget deficit')
        self.assertIsNone(redirect)

        body = json.dumps({
            'query': {
                'normalized': [{
                    'from': 'government budget deficits',
                    'to': 'Government budget deficits'
                }],
                'pages': [{
                    'ns': 0,
                    'title': 'Government budget deficits',
                    'missing': True
                }],
            }
        })
        url = wiki_url({
            'redirects': '',
            'titles': 'government budget deficits',
            'prop': 'info',
        })

        responses.add(responses.GET, url, body=body, match_querystring=True)
        self.assertRaises(find_link.api.Missing,
                          find_link.api.get_wiki_info,
                          'government budget deficits')

    @responses.activate
    def test_cat_start(self):
        body = json.dumps({"query": {"allpages": []}})
        url = 'https://en.wikipedia.org/w/api.php'
        responses.add(responses.GET, url, body=body)
        self.assertEqual(find_link.api.cat_start('test123'), [])

    @responses.activate
    def test_all_pages(self):
        title = 'Government budget deficit'
        body = json.dumps({
            "query": {
                "allpages": [{"pageid": 312605, "ns": 0, "title": title}]
            }
        })
        url = wiki_url({'apfilterredir': 'nonredirects',
                        'apprefix': title,
                        'list': 'allpages',
                        'apnamespace': 0,
                        'aplimit': 500})
        responses.add(responses.GET, url, body=body, match_querystring=True)
        result = find_link.api.all_pages(title)
        self.assertListEqual(result, [])

    @responses.activate
    def test_categorymembers(self):
        body = json.dumps({"query": {"categorymembers": []}})
        url = wiki_url({
            'cmnamespace': 0,
            'list':
            'categorymembers',
            'cmlimit': 500,
            'cmtitle': 'Test123'
        })
        responses.add(responses.GET, url, body=body, match_querystring=True)
        self.assertListEqual(find_link.core.categorymembers('test123'), [])

    @responses.activate
    def test_is_redirect_to(self):
        title_from = 'Bread maker'
        title_to = 'Bread machine'

        body = json.dumps({
            "query": {
                "pages": [{
                    "pageid": 1093444,
                    "ns": 0,
                    "title": "Bread maker",
                    "contentmodel": "wikitext",
                    "pagelanguage": "en",
                    "touched": "2015-06-21T15:12:00Z",
                    "lastrevid": 41586995,
                    "length": 27,
                    "redirect": True
                }]
            }
        })
        url = wiki_url({'titles': 'Bread maker', 'prop': 'info'})
        responses.add(responses.GET, url, body=body, match_querystring=True)

        url = wiki_url({'titles': 'Bread maker', 'prop': 'revisions', 'rvprop': 'content'})

        body = '{"query":{"pages":[{"pageid":1093444,"ns":0,"title":"Bread maker","revisions":[{"contentformat":"text/x-wiki","contentmodel":"wikitext","content":"#REDIRECT [[Bread machine]]"}]}]}}'

        responses.add(responses.GET, url, body=body, match_querystring=True)

        self.assertTrue(find_link.core.is_redirect_to(title_from, title_to))

        title_from = 'Sugarlump'
        title_to = 'Sugar'
        url = wiki_url({'prop': 'info', 'titles': 'Sugarlump'})
        body = json.dumps({
            "query": {
                "pages": [
                    {
                        "ns": 0,
                        "title": "Sugarlump",
                        "missing": True,
                        "contentmodel": "wikitext",
                    }
                ]
            }
        })
        responses.add(responses.GET, url, body=body, match_querystring=True)
        self.assertFalse(find_link.core.is_redirect_to(title_from, title_to))

    @responses.activate
    def test_wiki_redirects(self):
        url = wiki_url({
            'blfilterredir': 'redirects',
            'bllimit': 500,
            'bltitle': 'market town',
            'list': 'backlinks',
            'blnamespace': 0,
        })
        body = '{"query":{"backlinks":[{"pageid":383580,"title":"Market-town","redirect":""},{"pageid":1316024,"ns":0,"title":"Market towns","redirect":""},{"pageid":8494082,"ns":0,"title":"Marktgemeinde","redirect":""},{"pageid":15763709,"ns":0,"title":"Market right","redirect":""},{"pageid":23265231,"ns":0,"title":"Market towns in England","redirect":""},{"pageid":23386458,"ns":0,"title":"Market rights","redirect":""},{"pageid":24234988,"ns":0,"title":"Market charter","redirect":""},{"pageid":47397538,"ns":0,"title":"Market town privileges","redirect":""}]}}'
        responses.add(responses.GET, url, body=body, match_querystring=True)
        result = find_link.api.wiki_redirects('market town')
        self.assertTrue(all(isinstance(title, str) for title in result))

    def test_en_dash(self):
        title = u'obsessive\u2013compulsive disorder'
        content = 'This is a obsessive-compulsive disorder test'
        (c, r) = find_link.match.find_link_in_content(title, content)
        self.assertEqual(r, title)
        self.assertEqual(c, u'This is a [[obsessive\u2013compulsive disorder]] test')

        (c, r) = find_link.match.find_link_in_content(title, content)
        self.assertEqual(r, title)
        self.assertEqual(c, u'This is a [[obsessive\u2013compulsive disorder]] test')

        content = 'This is a [[obsessive-compulsive]] disorder test'

        (c, r) = find_link.match.find_link_in_content(title, content)
        self.assertEqual(r, title)
        self.assertEqual(c, u'This is a [[obsessive\u2013compulsive disorder]] test')

        (c, r) = find_link.match.find_link_in_content(title, content)
        self.assertEqual(r, title)
        self.assertEqual(c, u'This is a [[obsessive\u2013compulsive disorder]] test')

    @responses.activate
    def test_wiki_search(self):
        url = wiki_url({
            'list': 'search',
            'srlimit': 50,
            'srsearch': '"hedge"',
            'continue': '',
            'srwhat': 'text'
        })

        body = '{"query":{"searchinfo":{"totalhits":444},"search":[{"ns":0,"title":"Coaching inn","snippet":"approximately the mid-17th century for a period of about 200 years, the <span class=\\"searchmatch\\">coaching</span> <span class=\\"searchmatch\\">inn</span>, sometimes called a coaching house or staging inn, was a vital part of","size":4918,"wordcount":561,"timestamp":"2015-08-04T13:20:24Z"},{"ns":0,"title":"Varbuse","snippet":"Estonian Road Museum is located in the former Varbuse <span class=\\"searchmatch\\">coaching</span> <span class=\\"searchmatch\\">inn</span>.       Varbuse <span class=\\"searchmatch\\">coaching</span> <span class=\\"searchmatch\\">inn</span>          Estonian Road Museum       &quot;Population by place","size":2350,"wordcount":96,"timestamp":"2015-01-02T23:23:10Z"}]}}'
        responses.add(responses.GET, url, body=body, match_querystring=True)

        url = wiki_url({
            'continue': '',
            'srsearch': '"coaching inn"',
            'list': 'search',
            'srlimit': 50,
            'srwhat': 'text',
        })

        responses.add(responses.GET, url, body=body, match_querystring=True)
        totalhits, results = find_link.api.wiki_search('coaching inn')
        self.assertGreater(totalhits, 0)
        totalhits, results = find_link.api.wiki_search('hedge (finance)')
        self.assertGreater(totalhits, 0)

    @responses.activate
    def test_do_search(self):
        url = wiki_url({
            'continue': '',
            'action': 'query',
            'srsearch': '"market town"',
            'srwhat': 'text',
            'format': 'json',
            'list': 'search',
            'srlimit': '50',
        })
        body = '{"query":{"searchinfo":{"totalhits":3593},"search":[{"ns":0,"title":"Market town","snippet":"<span class=\\"searchmatch\\">Market</span> <span class=\\"searchmatch\\">town</span> or market right is a legal term, originating in the medieval period, for a European settlement that has the right to host markets, distinguishing","size":10527,"wordcount":1362,"timestamp":"2015-06-25T18:19:23Z"},{"ns":0,"title":"V\\u011btrn\\u00fd Jen\\u00edkov","snippet":"V\\u011btrn\\u00fd Jen\\u00edkov (Czech pronunciation: [\\u02c8vj\\u025btr\\u0329ni\\u02d0\\u02c8j\\u025b\\u0272i\\u02d0kof]) is a <span class=\\"searchmatch\\">market</span> <span class=\\"searchmatch\\">town</span> in the Jihlava District, Vyso\\u010dina Region of the Czech Republic. About 582","size":833,"wordcount":76,"timestamp":"2013-02-28T19:49:34Z"}]}}'
        responses.add(responses.GET, url, body=body, match_querystring=True)

        url = wiki_url({
            'continue': '',
            'blnamespace': '0',
            'bllimit': '500',
            'action': 'query',
            'format': 'json',
            'list': 'backlinks',
            'bltitle': 'market town'
        })
        body = '{"query":{"backlinks":[{"pageid":1038,"ns":0,"title":"Aarhus"},{"pageid":1208,"ns":0,"title":"Alan Turing"},{"pageid":2715,"ns":0,"title":"Abergavenny"},{"pageid":4856,"ns":0,"title":"Borough"},{"pageid":5391,"ns":0,"title":"City"},{"pageid":6916,"ns":0,"title":"Colony"},{"pageid":8166,"ns":0,"title":"Devon"},{"pageid":13616,"ns":0,"title":"Howard Carter"},{"pageid":13861,"ns":0,"title":"Hampshire"},{"pageid":13986,"ns":0,"title":"Hertfordshire"},{"pageid":16143,"ns":0,"title":"John Locke"},{"pageid":16876,"ns":0,"title":"Kingston upon Thames"},{"pageid":19038,"ns":0,"title":"Municipality"},{"pageid":20206,"ns":0,"title":"Manchester"},{"pageid":22309,"ns":0,"title":"Oslo"},{"pageid":22422,"ns":0,"title":"Olney Hymns"},{"pageid":23241,"ns":0,"title":"Telecommunications in China"},{"pageid":25798,"ns":0,"title":"Reykjav\\u00edk"},{"pageid":25897,"ns":0,"title":"Road"},{"pageid":26316,"ns":0,"title":"Racial segregation"}]}}'
        responses.add(responses.GET, url, body=body, match_querystring=True)

        url = wiki_url({
            'apnamespace': '14',
            'aplimit': '500',
            'format': 'json',
            'action': 'query',
            'apprefix': 'market town',
            'apfilterredir': 'nonredirects',
            'list': 'allpages'
        })
        body = '{"query":{"allpages":[{"pageid":27601242,"ns":14,"title":"Category:Market towns"}]}}'
        responses.add(responses.GET, url, body=body, match_querystring=True)

        url = wiki_url({
            'cmlimit': '500',
            'action': 'query',
            'cmtitle': 'Category:Market town',
            'cmnamespace': '0',
            'format': 'json',
            'list': 'categorymembers'
        })
        body = '{"query":{"categorymembers":[]}}'
        responses.add(responses.GET, url, body=body, match_querystring=True)

        url = wiki_url({
            'cmlimit': '500',
            'action': 'query',
            'cmtitle': 'Category:Market towns',
            'cmnamespace': '0',
            'format': 'json',
            'list': 'categorymembers'
        })
        body = '{"query":{"categorymembers":[]}}'
        responses.add(responses.GET, url, body=body, match_querystring=True)

        url = wiki_url({
            'apfilterredir': 'nonredirects',
            'apprefix': 'Market town',
            'list': 'allpages',
            'apnamespace': 0,
            'aplimit': 500,
        })

        body = '{"query":{"allpages":[{"pageid":145965,"ns":0,"title":"Market town"},{"pageid":13941316,"ns":0,"title":"Market towns of Buskerud county"}]}}'
        responses.add(responses.GET, url, body=body, match_querystring=True)

        url = wiki_url({
            'prop': 'templates',
            'continue': '',
            'tlnamespace': 10,
            'titles': 'V\u011btrn\u00fd Jen\u00edkov',
            'tllimit': 500,
        })

        body = '{"query":{"pages":[{"pageid":17087711,"ns":0,"title":"V\u011btrn\u00fd Jen\u00edkov","templates":[{"ns":10,"title":"Template:Asbox"},{"ns":10,"title":"Template:Commons"}]}]}}'

        responses.add(responses.GET, url, body=body, match_querystring=True)

        reply = find_link.core.do_search('market town', None)
        self.assertIsInstance(reply, dict)
        self.assertSetEqual(set(reply.keys()), {'totalhits', 'results', 'longer'})
        self.assertGreater(reply['totalhits'], 0)
        self.assertIsInstance(reply['results'], list)
        self.assertGreater(len(reply['results']), 0)
        self.assertTrue(any(title.startswith('Market towns of') for title in reply['longer']))

    def test_parse_cite(self):
        bindir = os.path.abspath(os.path.dirname(__file__))
        filename = os.path.join(bindir, 'cite_parse_error')
        sample = open(filename).read()
        found_duty = False
        for a, b in find_link.match.parse_cite(sample):
            if 'duty' in b.lower():
                found_duty = True
        self.assertTrue(found_duty)

    def test_avoid_link_in_cite(self):
        tp = 'magic'
        content = 'test <ref>{{cite web|title=Magic|url=http://magic.com}}</ref>'
        (c, r) = find_link.match.find_link_in_content(tp, content + ' ' + tp)
        self.assertEqual(c, content + ' [[' + tp + ']]')
        self.assertEqual(r, tp)

        self.assertRaises(find_link.match.NoMatch, find_link.match.find_link_in_content, tp, content)
        tp = 'abc'
        content = '==Early life==\n<ref>{{cite news|}}</ref>abc'
        (c, r) = find_link.match.find_link_in_content(tp, content)
        self.assertEqual(c, content.replace(tp, '[[' + tp + ']]'))
        self.assertEqual(r, tp)

    def test_coastal_sage_scrub(self):
        sample = '''Depend on a [[habitat]] that has shown substantial historical or recent declines in size. This criterion infers the population viability of a species based on trends in the habitats upon which it specializes. Coastal [[wetland]]s, particularly in the urbanized [[San Francisco Bay]] and south-coastal areas, alluvial fan [[sage (plant)|sage]] [[scrubland|scrub]] and coastal sage scrub in the southern coastal basins, and arid scrub in the [[San Joaquin Valley]], are examples of California habitats that have seen dramatic reductions in size in recent history. Species that specialize in these habitats generally meet the criteria for Threatened or Endangered status or Special Concern status;'''
        (c, r) = find_link.match.find_link_in_chunk('coastal sage scrub', sample)
        self.assertEqual(c, sample.replace('coastal sage scrub', '[[coastal sage scrub]]'))
        self.assertEqual(r, 'coastal sage scrub')

    def test_section_iter(self):
        result = list(find_link.match.section_iter('test'))
        self.assertListEqual(result, [(None, 'test')])
        text = '''==Heading 1 ==
Paragraph 1.
==Heading 2 ==
Paragraph 2.
'''
        expect = [
            ('==Heading 1 ==\n', 'Paragraph 1.\n'),
            ('==Heading 2 ==\n', 'Paragraph 2.\n')
        ]

        self.assertListEqual(list(find_link.match.section_iter(text)), expect)

    def test_get_subsections(self):
        text = '''==Heading 1 ==
Paragraph 1.
==Heading 2 ==
Paragraph 2.
===Level 2===
Paragraph 3.
==Heading 4==
Paragraph 4.
'''
        self.assertEqual(find_link.match.get_subsections(text, 4), '')

    @responses.activate
    def test_match_found(self):
        url = wiki_url({'prop': 'revisions|info', 'titles': 'payment protection insurance', 'rvprop': 'content|timestamp'})

        content = "{{multiple issues|\n{{Globalize|2=the United Kingdom|date=July 2011}}\n{{Original research|date=April 2009}}\n}}\n'''Payment protection insurance''' ('''PPI'''), also known as '''credit insurance''', '''credit protection insurance''', or '''loan repayment insurance''', is an insurance product that enables consumers to insure repayment of credit if the borrower dies, becomes ill or disabled, loses a job, or faces other circumstances that may prevent them from earning income to service the debt. It is not to be confused with [[income protection insurance]], which is not specific to a debt but covers any income. PPI was widely sold by banks and other credit providers as an add-on to the loan or overdraft product.<ref>{{cite web | url=http://www.fsa.gov.uk/consumerinformation/product_news/insurance/payment_protection_insurance_/what-is-ppi | title=What is payment protection insurance? | accessdate=17 February 2014}}</ref>"

        body = json.dumps({
            "query": {
                "pages": [
                    {
                        "title": "Payment protection insurance",
                        "revisions": [{"timestamp": "2016-03-26T17:56:25Z", "content": content}]
                    }
                ]
            }
        })

        responses.add(responses.GET, url, body=body, match_querystring=True)
        l = 'payment protection insurance'
        l2 = 'payment Protection Insurance'
        m = re.compile('(P)' + l[1:], re.I).match('P' + l2[1:])
        self.assertEqual(find_link.match.match_found(m, l, None), l)

    def test_avoid_link_in_heading(self):
        tp = 'test phrase'
        content = '''
=== Test phrase ===

This sentence contains the test phrase.'''

        (c, r) = find_link.match.find_link_in_content(tp, content)
        self.assertEqual(c, content.replace(tp, '[[' + tp + ']]'))
        self.assertEqual(r, tp)

    @responses.activate
    @patch('find_link.match.get_case_from_content', lambda s: None)
    def test_find_link_in_content(self):  # this test is slow
        # orig_get_case_from_content = find_link.core.get_case_from_content
        # find_link.core.get_case_from_content = lambda s: None

        self.assertRaises(find_link.match.NoMatch, find_link.match.find_link_in_content, 'foo', 'bar')

        input_content = 'Able to find this test\n\nphrase in an article.'
        self.assertRaises(find_link.match.NoMatch,
                          find_link.match.find_link_in_content,
                          'test phrase', input_content)

        input_content = 'Able to find this test  \n  \n  phrase in an article.'
        self.assertRaises(find_link.match.NoMatch,
                          find_link.match.find_link_in_content,
                          'test phrase', input_content)

        otrain = 'Ticketing on the O-Train works entirely on a proof-of-payment basis; there are no ticket barriers or turnstiles, and the driver does not check fares.'
        (c, r) = find_link.match.find_link_in_content('ticket barriers', otrain, linkto='turnstile')
        self.assertEqual(c, otrain.replace('turnstile', '[[turnstile]]'))
        self.assertEqual(r, 'turnstile')

        sample = """On April 26, 2006, Snoop Dogg and members of his entourage were arrested after being turned away from [[British Airways]]' first class lounge at [[Heathrow Airport]]. Snoop and his party were not allowed to enter the lounge because some of the entourage were flying first class, other members in economy class. After the group was escorted outside, they vandalized a duty-free shop by throwing whiskey bottles. Seven police officers were injured in the midst of the disturbance. After a night in prison, Snoop and the other men were released on bail on April 27, but he was unable to perform at the Premier Foods People's Concert in [[Johannesburg]] on the same day. As part of his bail conditions, he had to return to the police station in May. The group has been banned by British Airways for "the foreseeable future."<ref>{{cite news|url=http://news.bbc.co.uk/1/hi/entertainment/4949430.stm |title=Rapper Snoop Dogg freed on bail |publisher=BBC News  |date=April 27, 2006 |accessdate=January 9, 2011}}</ref><ref>{{cite news|url=http://news.bbc.co.uk/1/hi/entertainment/4953538.stm |title=Rap star to leave UK after arrest |publisher=BBC News  |date=April 28, 2006 |accessdate=January 9, 2011}}</ref> When Snoop Dogg appeared at a London police station on May 11, he was cautioned for [[affray]] under [[Fear or Provocation of Violence|Section 4]] of the [[Public Order Act 1986|Public Order Act]] for use of threatening words or behavior.<ref>{{cite news|url=http://newsvote.bbc.co.uk/1/hi/entertainment/4761553.stm|title=Rap star is cautioned over brawl |date=May 11, 2006|publisher=BBC News |accessdate=July 30, 2009}}</ref> On May 15, the [[Home Office]] decided that Snoop Dogg should be denied entry to the United Kingdom for the foreseeable future due to the incident at Heathrow as well as his previous convictions in the United States for drugs and firearms offenses.<ref>{{cite web|url=http://soundslam.com/articles/news/news.php?news=060516_snoopb |title=Soundslam News |publisher=Soundslam.com |date=May 16, 2006 |accessdate=January 9, 2011}}</ref><ref>{{cite web|url=http://uk.news.launch.yahoo.com/dyna/article.html?a=/060516/340/gbrj1.html&e=l_news_dm |title=Snoop 'banned from UK' |publisher=Uk.news.launch.yahoo.com |accessdate=January 9, 2011}}</ref> Snoop Dogg's visa card was rejected by local authorities on March 24, 2007 because of the Heathrow incident.<ref>{{cite news |first=VOA News |title=Rapper Snoop Dogg Arrested in UK |date=April 27, 2006 |publisher=Voice of America |url=http://classic-web.archive.org/web/20060603120934/http://voanews.com/english/archive/2006-04/2006-04-27-voa17.cfm |work=VOA News |accessdate=December 31, 2008}}</ref> A concert at London's Wembley Arena on March 27 went ahead with Diddy (with whom he toured Europe) and the rest of the show."""

        (c, r) = find_link.match.find_link_in_content('duty-free shop', sample)
        self.assertEqual(c, sample.replace('duty-free shop', '[[duty-free shop]]'))
        self.assertEqual(r, 'duty-free shop')

        sample = '[[Retriever]]s are typically used when [[waterfowl]] hunting. Since a majority of waterfowl hunting employs the use of small boats'

        for func in find_link.match.find_link_in_content, find_link.match.find_link_in_text:
            (c, r) = func('waterfowl hunting', sample)
            self.assertEqual(c, sample.replace(']] hunting', ' hunting]]'))
            self.assertEqual(r, 'waterfowl hunting')

        sample = 'abc [[File:Lufschiffhafen Jambol.jpg|thumb|right|Jamboli airship hangar in Bulgaria]] abc'
        q = 'airship hangar'
        for func in find_link.match.find_link_in_content, find_link.match.find_link_in_text:
            (c, r) = func(q, sample)
            self.assertEqual(c, sample.replace(q, '[[' + q + ']]'))
            self.assertEqual(r, q)

        sample = 'It is relatively easy for insiders to capture insider-trading like gains through the use of "open market repurchases."  Such transactions are legal and generally encouraged by regulators through safeharbours against insider trading liability.'
        q = 'insider trading'

        q = 'ski mountaineering' # Germán Cerezo Alonso 
        sample = 'started ski mountaineering in 1994 and competed first in the 1997 Catalunyan Championship. He finished fifth in the relay event of the [[2005 European Championship of Ski Mountaineering]].'

        for func in find_link.match.find_link_in_content, find_link.match.find_link_in_text:
            (c, r) = func(q, sample)
            self.assertEqual(c, sample.replace(q, '[[' + q + ']]'))
            self.assertEqual(r, q)

        q = 'fall of the Iron Curtain'
        linkto = 'revolutions of 1989'
        sample = 'With the fall of the [[Iron Curtain]] and the associated'

        #search_for_link = mk_link_matcher(q)
        #m = search_for_link(sample)
        #replacement = match_found(m, q, linkto)
        #self.assertEqual(replacement, 'revolutions of 1989|fall of the Iron Curtain]]')

        (c, r) = find_link.match.find_link_in_chunk(q, sample, linkto=linkto)
        self.assertEqual(c, sample.replace('fall of the [[', '[[revolutions of 1989|fall of the '))
        self.assertEqual(r, 'revolutions of 1989|fall of the Iron Curtain')

        q = 'religious conversion'
        sample = 'There were no reports of [[forced religious conversion]], including of minor U.S. citizens'
        self.assertRaises(find_link.match.LinkReplace, find_link.match.find_link_in_chunk, q, sample)

        q = 'two-factor authentication'
        sample = "Two factor authentication is a 'strong authentication' method as it"

        for func in find_link.match.find_link_in_content, find_link.match.find_link_in_text:
            (c, r) = func(q, sample)
            self.assertEqual(c, "[[Two-factor authentication]] is a 'strong authentication' method as it")
            self.assertEqual(r, q[0].upper() + q[1:])

        q = 'spherical trigonometry'
        sample = 'also presents the spherical trigonometrical formulae'

        (c, r) = find_link.match.find_link_in_content('spherical trig', sample, linkto=q)
        self.assertEqual(c, 'also presents the [[spherical trigonometry|spherical trigonometrical]] formulae')
        self.assertEqual(r, 'spherical trigonometry|spherical trigonometrical')

        q = 'post-World War II baby boom'
        sample = 'huge boost during the post World War II [[Baby Boomer|Baby Boom]].'
        for func in find_link.match.find_link_in_content, find_link.match.find_link_in_text:
            (c, r) = func(q, sample)
            self.assertEqual(c, 'huge boost during the [[post-World War II baby boom]].')
            self.assertEqual(r, q)

        q = 'existence of God'
        sample = 'with "je pense donc je suis" or "[[cogito ergo sum]]" or "I think, therefore I am", argued that "the self" is something that we can know exists with [[epistemology|epistemological]] certainty. Descartes argued further that this knowledge could lead to a proof of the certainty of the existence of [[God]], using the [[ontological argument]] that had been formulated first by [[Anselm of Canterbury]].{{Citation needed|date=January 2012}}'
        for func in find_link.match.find_link_in_content, find_link.match.find_link_in_text:
            (c, r) = func(q, sample)
            self.assertEqual(c, sample.replace('existence of [[God', '[[existence of God'))
            self.assertEqual(r, q)

        q = 'virtual machine'
        sample = 'It compiles Python programs into intermediate bytecode, which is executed by the virtual machine. Jython compiles into Java byte code, which can then be executed by every [[Java Virtual Machine]] implementation. This also enables the use of Java class library functions from the Python program.'
        for func in find_link.match.find_link_in_content, find_link.match.find_link_in_text:
            (c, r) = func(q, sample)
            self.assertEqual(c, sample.replace('virtual machine', '[[virtual machine]]'))
            self.assertEqual(r, q)

        url = wiki_url({
            'prop': 'info',
            'redirects': '',
            'titles': 'Teleological argument'
        })
        body = json.dumps({
            'query': {
                'pages': [{
                    'pageid': 30731,
                    'ns': 0,
                    'title': 'Teleological argument',
                }],
            }
        })

        q = 'existence of God'
        sample = '[[Intelligent design]] is an [[Teleological argument|argument for the existence of God]],'
        for func in find_link.match.find_link_in_content, find_link.match.find_link_in_text:
            responses.add(responses.GET, url, body=body, match_querystring=True)
            self.assertRaises(find_link.match.LinkReplace, func, q, sample)

        q = 'correlation does not imply causation'
        sample = 'Indeed, an important axiom that social scientists cite, but often forget, is that "[[correlation]] does not imply [[Causality|causation]]."'
        for func in find_link.match.find_link_in_content, find_link.match.find_link_in_text:
            (c, r) = func(q, sample)
            self.assertEqual(c, 'Indeed, an important axiom that social scientists cite, but often forget, is that "[[correlation does not imply causation]]."')
            self.assertEqual(r, q)

        sample = "A '''pedestal desk''' is usually a large free-standing [[desk]]"
        self.assertRaises(find_link.match.NoMatch, find_link.match.find_link_in_content, 'standing desk', sample)

        pseudocode1 = 'These languages are typically [[Dynamic typing|dynamically typed]], meaning that variable declarations and other [[Boilerplate_(text)#Boilerplate_code|boilerplate code]] can be omitted.'

        for func in find_link.match.find_link_in_content, find_link.match.find_link_in_text:
            (c, r) = func('boilerplate code', pseudocode1)
            self.assertEqual(c, pseudocode1.replace('Boilerplate_(text)#Boilerplate_code|', ''))
            self.assertEqual(r, 'boilerplate code')

        pseudocode2 = 'Large amounts of [[boilerplate (text)#Boilerplate code|boilerplate]] code.'
        for func in find_link.match.find_link_in_content, find_link.match.find_link_in_text:
            (c, r) = func('boilerplate code', pseudocode2)
            self.assertEqual(c, pseudocode2.replace('(text)#Boilerplate code|boilerplate]] code', 'code]]'))
            self.assertEqual(r, 'boilerplate code')

        sample = 'particularly to handle the peak volumes of work generated by Payment Protection Insurance complaints.'
        (c, r) = find_link.match.find_link_in_content('payment protection insurance', sample)
        self.assertIn('payment protection insurance', c)
        (c, r) = find_link.match.find_link_in_text('payment protection insurance', sample)
        self.assertIn('payment protection insurance', c)

        if False:
            sample = 'further investigations on [[Extrajudicial punishment|extrajudicial killings]] by police forces.'
            q = 'extrajudicial killing'
            (c, r) = find_link.match.find_link_in_content(q, sample)
            self.assertIn(q, c)
            (c, r) = find_link.match.find_link_in_text(q, sample)
            self.assertIn(q, c)

        sample = 'units formed with [[SI prefix|metric prefixes]], such as kiloseconds'
        find_link.match.find_link_in_content('metric prefix', sample)

        sample = u"==Geography==\nA gem of Bermuda's coastline, it is surrounded by [[St. George's Parish, Bermuda|St. George's Parish]] in the north, east, south (Tucker's Town), and [[Hamilton Parish, Bermuda|Hamilton Parish]] in the west. A chain of islands and rocks stretches across the main opening to the [[Atlantic Ocean]], in the east, notably [[Cooper's Island, Bermuda|Cooper's Island]] (which was made a landmass contiguous to St. David's Island and Longbird Island in the 1940s), and [[Nonsuch Island, Bermuda|Nonsuch Island]]. The only channel suitable for large vessels to enter the harbour from the open Atlantic is [[Castle Roads, Bermuda|Castle Roads]], which was historically guarded by a number of fortifications, on [[Castle Island, Bermuda|Castle Island]], Brangman's Island, and Goat Island. Forts were also placed nearby on other small islands, and on the Tucker's Town peninsula of the Main Island. In the west, [[The Causeway, Bermuda|The Causeway]] crosses from the main island to St. David's Island, and beyond this a stretch of water known as [[Ferry Reach, Bermuda|Ferry Reach]] connects the harbour with [[St. George's Harbor, Bermuda|St. George's Harbour]] to the north, where Bermuda's first permanent settlement, [[St. George's, Bermuda|St. George's Town]], was founded in 1612. An unincorporated settlement, [[Tucker's Town, Bermuda|Tucker's Town]], was established on the [[peninsula]] of the [[Main Island, Bermuda|Main Island]] at the south-west of the harbour. The settlement was cleared by compulsory purchase order in the 1920s in order to create a luxury enclave where homes could be purchased by wealthy foreigners, and the attendant Mid Ocean Golf Club. In [[Hamilton Parish, Bermuda|Hamilton Parish]], on the western shore of the harbour, lies [[Walsingham Bay, Bermuda|Walsingham Bay]], the site where, in 1609-10, the crew of the wrecked [[Sea Venture]] built the ''[[Patience]]'', one of two ships built, which carried most of the survivors of the wrecking to [[Jamestown, Virginia|Jamestown]], [[Virginia]], in 1610. The ''Patience'' returned to Bermuda with [[George Somers|Admiral Sir George Somers]], who died in Bermuda later that year."
        find_link.match.find_link_in_content('compulsory purchase order', sample)

        if False:
            yard = "primary [[Hump yard|hump classification yards]] are located in Allentown."
            for func in find_link.match.find_link_in_content, find_link.match.find_link_in_text:
                (c, r) = func('classification yard', yard)
                self.assertEqual(c, yard.replace('[[Hump yard|hump classification yards]]', 'hump [[classification yard]]s'))
                self.assertEqual(r, 'classification yard')

            yard2 = 'A major [[hump yard|railway classification yard]] is north of Blenheim at [[Spring Creek, New Zealand|Spring Creek]].'
            for func in find_link.match.find_link_in_content, find_link.match.find_link_in_text:
                (c, r) = func('classification yard', yard2)
                self.assertEqual(c, yard2.replace('[[hump yard|railway classification yard]]', 'railway [[classification yard]]'))
                self.assertEqual(r, 'classification yard')

        yard3 = 'Five houses were destroyed and three others were damaged. A high school was also heavily damaged and railroad cars were thrown in a small freight classification yard. Four people were injured.'
        for func in find_link.match.find_link_in_content, find_link.match.find_link_in_text:
            (c, r) = func('classification yard', yard3)
            self.assertEqual(c, yard3.replace('classification yard', '[[classification yard]]'))
            self.assertEqual(r, 'classification yard')

        #yard2 = 'For the section from [[Rotterdam]] to the large [[Kijfhoek (classification yard)|classification yard Kijfhoek]] existing track was reconstructed, but three quarters of the line is new, from Kijfhoek to [[Zevenaar]] near the German border.'
        #(c, r) = find_link.match.find_link_in_text('classification yard', yard2)

        if False:
            sample = 'GEHA also has a contract with the federal government to administer benefits for the [[Pre-existing Condition Insurance Plan]], which will be a transitional program until 2014.'
            q = 'pre-existing condition'
            for func in find_link.match.find_link_in_content, find_link.match.find_link_in_text:
                self.assertRaises(find_link.match.LinkReplace, func, q, sample)

        station = 'Ticket barriers control access to all platforms, although the bridge entrance has no barriers.'
        (c, r) = find_link.match.find_link_in_content('ticket barriers', station, linkto='turnstile')
        self.assertEqual(c, station.replace('Ticket barriers', '[[Turnstile|Ticket barriers]]'))
        self.assertEqual(r, 'Turnstile|Ticket barriers')

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
            for func in find_link.match.find_link_in_content, find_link.match.find_link_in_text:
                (c, r) = func('test phrase', input_content)
                self.assertEqual(c, 'Able to find this [[test phrase]] in an article.')
                self.assertEqual(r, 'test phrase')

        q = 'recoil operation'
        article = 'pattern of long-recoil operation as the 25mm and 40mm guns.'

        search_for_link = find_link.match.mk_link_matcher(q)
        self.assertFalse(search_for_link(article))

        q = 'after-dinner speaker'
        linkto = 'public speaking'
        sample = 'in demand as an [[Public speaker|after-dinner speaker]].'

        (c, r) = find_link.match.find_link_in_chunk(q, sample, linkto=linkto)
        self.assertEqual(c, sample.replace('Public speaker', 'public speaking'))

        # find_link.get_case_from_content = orig_get_case_from_content
