# coding=utf-8
import os
import re
import sys
sys.path.append('..')
import find_link
import unittest


class TestFindLink(unittest.TestCase):
    @unittest.skip('broken')
    def test_get_case_from_content(self):
        orig_web_get = find_link.web_get
        title = 'London congestion charge'
        find_link.web_get = lambda params: {
            'query': { 'pages': { 1: { 'revisions': [{
                '*': "'''" + title + "'''"
                }]}}
        }}
        self.assertEqual(find_link.get_case_from_content(title), title)

        article = 'MyCar is exempt from the London Congestion Charge, road tax and parking charges.'
        for func in find_link.find_link_in_content, find_link.find_link_in_text:
            (c, r) = func('London congestion charge', article)
            self.assertEqual(r, 'London congestion charge')
        find_link.web_get = orig_web_get

    def test_get_wiki_info(self):
        orig_web_get = find_link.web_get
        find_link.web_get = lambda(param): {
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

        redirect = find_link.get_wiki_info('government budget deficit')
        self.assertIsNone(redirect)

        find_link.web_get = lambda(param): {
            "query":{
                "normalized":[{"from":"government budget deficits","to":"Government budget deficits"}],
                "pages":{"-1":{"ns":0,"title":"Government budget deficits","missing":""}}
            }
        }
        is_missing = False
        self.assertRaises(find_link.Missing,
                          find_link.get_wiki_info,
                          'government budget deficits')
        find_link.web_get = orig_web_get

    def test_cat_start(self):
        orig_web_get = find_link.web_get
        find_link.web_get = lambda params: {"query": {"allpages": []}}
        self.assertEqual(find_link.cat_start('test123'), [])
        find_link.web_get = orig_web_get

    def test_all_pages(self):
        orig_web_get = find_link.web_get
        find_link.web_get = lambda params: {"query": {"allpages": [{"pageid": 312605,"ns":0,"title":"Government budget deficit"}]}}
        result = find_link.all_pages('Government budget deficit')
        self.assertListEqual(result, [])
        find_link.web_get = orig_web_get

    def test_categorymembers(self):
        orig_web_get = find_link.web_get
        find_link.web_get = lambda params: {"query": {"categorymembers": []}}
        self.assertListEqual(find_link.categorymembers('test123'), [])
        find_link.web_get = orig_web_get

    def test_is_redirect_to(self):
        title_from = 'Bread maker'
        title_to = 'Bread machine'
        self.assertTrue(find_link.is_redirect_to(title_from, title_to))

        title_from = 'Sugarlump'
        title_to = 'Sugar'
        self.assertFalse(find_link.is_redirect_to(title_from, title_to))

    def test_wiki_redirects(self):
        result = find_link.wiki_redirects('market town')
        self.assertTrue(all(isinstance(title, basestring) for title in result))

    def test_en_dash(self):
        title = u'obsessive\u2013compulsive disorder'
        content = 'This is a obsessive-compulsive disorder test'
        (c, r) = find_link.find_link_in_content(title, content)
        self.assertEqual(r, title)
        self.assertEqual(c, u'This is a [[obsessive\u2013compulsive disorder]] test')

        (c, r) = find_link.find_link_in_content(title, content)
        self.assertEqual(r, title)
        self.assertEqual(c, u'This is a [[obsessive\u2013compulsive disorder]] test')

        content = 'This is a [[obsessive-compulsive]] disorder test'

        (c, r) = find_link.find_link_in_content(title, content)
        self.assertEqual(r, title)
        self.assertEqual(c, u'This is a [[obsessive\u2013compulsive disorder]] test')

        (c, r) = find_link.find_link_in_content(title, content)
        self.assertEqual(r, title)
        self.assertEqual(c, u'This is a [[obsessive\u2013compulsive disorder]] test')

    def test_wiki_search(self):
        totalhits, results = find_link.wiki_search('coaching inn')
        self.assertGreater(totalhits, 0)
        totalhits, results = find_link.wiki_search('hedge (finance)')
        self.assertGreater(totalhits, 0)

    #@unittest.skip('broken')
    def test_do_search(self):
        reply = find_link.do_search('market town', None)
        self.assertIsInstance(reply, dict)
        self.assertSetEqual(set(reply.keys()), {'totalhits', 'results', 'longer'})
        self.assertGreater(reply['totalhits'], 0)
        self.assertIsInstance(reply['results'], list)
        self.assertGreater(len(reply['results']), 0)
        self.assertTrue(any(title.startswith('Market towns of') for title in reply['longer']))

    def test_parse_cite(self):
        bindir = os.path.abspath(os.path.dirname(__file__))
        filename = os.path.join(bindir, 'cite_parse_error')
        sample = open(filename).read().decode('utf-8')
        found_duty = False
        for a, b in find_link.parse_cite(sample):
            if 'duty' in b.lower():
                found_duty = True
        self.assertTrue(found_duty)

    def test_avoid_link_in_cite(self):
        tp = 'magic'
        content = 'test <ref>{{cite web|title=Magic|url=http://magic.com}}</ref>'
        (c, r) = find_link.find_link_in_content(tp, content + ' ' + tp)
        self.assertEqual(c, content + ' [[' + tp + ']]')
        self.assertEqual(r, tp)

        self.assertRaises(find_link.NoMatch, find_link.find_link_in_content, tp, content) 
        tp = 'abc'
        content = '==Early life==\n<ref>{{cite news|}}</ref>abc'
        (c, r) = find_link.find_link_in_content(tp, content)
        self.assertEqual(c, content.replace(tp, '[[' + tp + ']]'))
        self.assertEqual(r, tp)

    def test_coastal_sage_scrub(self):
        sample = '''Depend on a [[habitat]] that has shown substantial historical or recent declines in size. This criterion infers the population viability of a species based on trends in the habitats upon which it specializes. Coastal [[wetland]]s, particularly in the urbanized [[San Francisco Bay]] and south-coastal areas, alluvial fan [[sage (plant)|sage]] [[scrubland|scrub]] and coastal sage scrub in the southern coastal basins, and arid scrub in the [[San Joaquin Valley]], are examples of California habitats that have seen dramatic reductions in size in recent history. Species that specialize in these habitats generally meet the criteria for Threatened or Endangered status or Special Concern status;'''
        (c, r) = find_link.find_link_in_chunk('coastal sage scrub', sample)
        self.assertEqual(c, sample.replace('coastal sage scrub', '[[coastal sage scrub]]'))
        self.assertEqual(r, 'coastal sage scrub')

    def test_section_iter(self):
        result = list(find_link.section_iter('test'))
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

        self.assertListEqual(list(find_link.section_iter(text)), expect)

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
        self.assertEqual(find_link.get_subsetions(text, 4), '')

    def test_match_found(self):
        l = 'payment protection insurance'
        l2 = 'payment Protection Insurance'
        m = re.compile('(P)' + l[1:], re.I).match('P' + l2[1:])
        self.assertEqual(find_link.match_found(m, l, None), l)

    def test_avoid_link_in_heading(self):
        tp = 'test phrase'
        content = '''
=== Test phrase ===

This sentence contains the test phrase.'''

        (c, r) = find_link.find_link_in_content(tp, content)
        self.assertEqual(c, content.replace(tp, '[[' + tp + ']]'))
        self.assertEqual(r, tp)

    def test_find_link_in_content(self): # this test is slow
        orig_get_case_from_content = find_link.get_case_from_content
        find_link.get_case_from_content = lambda s: None

        self.assertRaises(find_link.NoMatch, find_link.find_link_in_content, 'foo', 'bar')

        input_content = 'Able to find this test\n\nphrase in an article.'
        self.assertRaises(find_link.NoMatch,
                          find_link.find_link_in_content,
                          'test phrase', input_content)

        input_content = 'Able to find this test  \n  \n  phrase in an article.'
        self.assertRaises(find_link.NoMatch,
                          find_link.find_link_in_content,
                          'test phrase', input_content)

        otrain = 'Ticketing on the O-Train works entirely on a proof-of-payment basis; there are no ticket barriers or turnstiles, and the driver does not check fares.'
        (c, r) = find_link.find_link_in_content('ticket barriers', otrain, linkto='turnstile')
        self.assertEqual(c, otrain.replace('turnstile', '[[turnstile]]'))
        self.assertEqual(r, 'turnstile')

        sample = """On April 26, 2006, Snoop Dogg and members of his entourage were arrested after being turned away from [[British Airways]]' first class lounge at [[Heathrow Airport]]. Snoop and his party were not allowed to enter the lounge because some of the entourage were flying first class, other members in economy class. After the group was escorted outside, they vandalized a duty-free shop by throwing whiskey bottles. Seven police officers were injured in the midst of the disturbance. After a night in prison, Snoop and the other men were released on bail on April 27, but he was unable to perform at the Premier Foods People's Concert in [[Johannesburg]] on the same day. As part of his bail conditions, he had to return to the police station in May. The group has been banned by British Airways for "the foreseeable future."<ref>{{cite news|url=http://news.bbc.co.uk/1/hi/entertainment/4949430.stm |title=Rapper Snoop Dogg freed on bail |publisher=BBC News  |date=April 27, 2006 |accessdate=January 9, 2011}}</ref><ref>{{cite news|url=http://news.bbc.co.uk/1/hi/entertainment/4953538.stm |title=Rap star to leave UK after arrest |publisher=BBC News  |date=April 28, 2006 |accessdate=January 9, 2011}}</ref> When Snoop Dogg appeared at a London police station on May 11, he was cautioned for [[affray]] under [[Fear or Provocation of Violence|Section 4]] of the [[Public Order Act 1986|Public Order Act]] for use of threatening words or behavior.<ref>{{cite news|url=http://newsvote.bbc.co.uk/1/hi/entertainment/4761553.stm|title=Rap star is cautioned over brawl |date=May 11, 2006|publisher=BBC News |accessdate=July 30, 2009}}</ref> On May 15, the [[Home Office]] decided that Snoop Dogg should be denied entry to the United Kingdom for the foreseeable future due to the incident at Heathrow as well as his previous convictions in the United States for drugs and firearms offenses.<ref>{{cite web|url=http://soundslam.com/articles/news/news.php?news=060516_snoopb |title=Soundslam News |publisher=Soundslam.com |date=May 16, 2006 |accessdate=January 9, 2011}}</ref><ref>{{cite web|url=http://uk.news.launch.yahoo.com/dyna/article.html?a=/060516/340/gbrj1.html&e=l_news_dm |title=Snoop 'banned from UK' |publisher=Uk.news.launch.yahoo.com |accessdate=January 9, 2011}}</ref> Snoop Dogg's visa card was rejected by local authorities on March 24, 2007 because of the Heathrow incident.<ref>{{cite news |first=VOA News |title=Rapper Snoop Dogg Arrested in UK |date=April 27, 2006 |publisher=Voice of America |url=http://classic-web.archive.org/web/20060603120934/http://voanews.com/english/archive/2006-04/2006-04-27-voa17.cfm |work=VOA News |accessdate=December 31, 2008}}</ref> A concert at London's Wembley Arena on March 27 went ahead with Diddy (with whom he toured Europe) and the rest of the show."""

        (c, r) = find_link.find_link_in_content('duty-free shop', sample)
        self.assertEqual(c, sample.replace('duty-free shop', '[[duty-free shop]]'))
        self.assertEqual(r, 'duty-free shop')

        sample = '[[Retriever]]s are typically used when [[waterfowl]] hunting. Since a majority of waterfowl hunting employs the use of small boats'

        for func in find_link.find_link_in_content, find_link.find_link_in_text:
            (c, r) = func('waterfowl hunting', sample)
            self.assertEqual(c, sample.replace(']] hunting', ' hunting]]'))
            self.assertEqual(r, 'waterfowl hunting')

        sample = 'abc [[File:Lufschiffhafen Jambol.jpg|thumb|right|Jamboli airship hangar in Bulgaria]] abc'
        q = 'airship hangar'
        for func in find_link.find_link_in_content, find_link.find_link_in_text:
            (c, r) = func(q, sample)
            self.assertEqual(c, sample.replace(q, '[[' + q + ']]'))
            self.assertEqual(r, q)

        sample = 'It is relatively easy for insiders to capture insider-trading like gains through the use of "open market repurchases."  Such transactions are legal and generally encouraged by regulators through safeharbours against insider trading liability.'
        q = 'insider trading'

        q = 'ski mountaineering' # Germán Cerezo Alonso 
        sample = 'started ski mountaineering in 1994 and competed first in the 1997 Catalunyan Championship. He finished fifth in the relay event of the [[2005 European Championship of Ski Mountaineering]].'

        for func in find_link.find_link_in_content, find_link.find_link_in_text:
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

        (c, r) = find_link.find_link_in_chunk(q, sample, linkto=linkto)
        self.assertEqual(c, sample.replace('fall of the [[', '[[revolutions of 1989|fall of the '))
        self.assertEqual(r, 'revolutions of 1989|fall of the Iron Curtain')

        q = 'religious conversion'
        sample = 'There were no reports of [[forced religious conversion]], including of minor U.S. citizens'
        self.assertRaises(find_link.LinkReplace, find_link.find_link_in_chunk, q, sample)

        q = 'two-factor authentication'
        sample = "Two factor authentication is a 'strong authentication' method as it"

        for func in find_link.find_link_in_content, find_link.find_link_in_text:
            (c, r) = func(q, sample)
            self.assertEqual(c, "[[Two-factor authentication]] is a 'strong authentication' method as it")
            self.assertEqual(r, q[0].upper() + q[1:])


        q = 'spherical trigonometry'
        sample = 'also presents the spherical trigonometrical formulae'

        (c, r) = find_link.find_link_in_content('spherical trig', sample, linkto=q)
        self.assertEqual(c, 'also presents the [[spherical trigonometry|spherical trigonometrical]] formulae')
        self.assertEqual(r, 'spherical trigonometry|spherical trigonometrical')

        q = 'post-World War II baby boom'
        sample = 'huge boost during the post World War II [[Baby Boomer|Baby Boom]].'
        for func in find_link.find_link_in_content, find_link.find_link_in_text:
            (c, r) = func(q, sample)
            self.assertEqual(c, 'huge boost during the [[post-World War II baby boom]].')
            self.assertEqual(r, q)

        q = 'existence of God'
        sample = 'with "je pense donc je suis" or "[[cogito ergo sum]]" or "I think, therefore I am", argued that "the self" is something that we can know exists with [[epistemology|epistemological]] certainty. Descartes argued further that this knowledge could lead to a proof of the certainty of the existence of [[God]], using the [[ontological argument]] that had been formulated first by [[Anselm of Canterbury]].{{Citation needed|date=January 2012}}'
        for func in find_link.find_link_in_content, find_link.find_link_in_text:
            (c, r) = func(q, sample)
            self.assertEqual(c, sample.replace('existence of [[God', '[[existence of God'))
            self.assertEqual(r, q)

        q = 'virtual machine'
        sample = 'It compiles Python programs into intermediate bytecode, which is executed by the virtual machine. Jython compiles into Java byte code, which can then be executed by every [[Java Virtual Machine]] implementation. This also enables the use of Java class library functions from the Python program.'
        for func in find_link.find_link_in_content, find_link.find_link_in_text:
            (c, r) = func(q, sample)
            self.assertEqual(c, sample.replace('virtual machine', '[[virtual machine]]'))
            self.assertEqual(r, q)

        q = 'existence of God'
        sample = '[[Intelligent design]] is an [[Teleological argument|argument for the existence of God]],'
        for func in find_link.find_link_in_content, find_link.find_link_in_text:
            self.assertRaises(find_link.LinkReplace, func, q, sample)

        q = 'correlation does not imply causation'
        sample = 'Indeed, an important axiom that social scientists cite, but often forget, is that "[[correlation]] does not imply [[Causality|causation]]."'
        for func in find_link.find_link_in_content, find_link.find_link_in_text:
            (c, r) = func(q, sample)
            self.assertEqual(c, 'Indeed, an important axiom that social scientists cite, but often forget, is that "[[correlation does not imply causation]]."')
            self.assertEqual(r, q)

        sample = "A '''pedestal desk''' is usually a large free-standing [[desk]]"
        self.assertRaises(find_link.NoMatch, find_link.find_link_in_content, 'standing desk', sample)

        pseudocode1 = 'These languages are typically [[Dynamic typing|dynamically typed]], meaning that variable declarations and other [[Boilerplate_(text)#Boilerplate_code|boilerplate code]] can be omitted.'

        for func in find_link.find_link_in_content, find_link.find_link_in_text:
            (c, r) = func('boilerplate code', pseudocode1)
            self.assertEqual(c, pseudocode1.replace('Boilerplate_(text)#Boilerplate_code|', ''))
            self.assertEqual(r, 'boilerplate code')

        pseudocode2 = 'Large amounts of [[boilerplate (text)#Boilerplate code|boilerplate]] code.'
        for func in find_link.find_link_in_content, find_link.find_link_in_text:
            (c, r) = func('boilerplate code', pseudocode2)
            self.assertEqual(c, pseudocode2.replace('(text)#Boilerplate code|boilerplate]] code', 'code]]'))
            self.assertEqual(r, 'boilerplate code')

        sample = 'particularly to handle the peak volumes of work generated by Payment Protection Insurance complaints.'
        (c, r) = find_link.find_link_in_content('payment protection insurance', sample)
        self.assertIn('payment protection insurance', c)
        (c, r) = find_link.find_link_in_text('payment protection insurance', sample)
        self.assertIn('payment protection insurance', c)

        if False:
            sample = 'further investigations on [[Extrajudicial punishment|extrajudicial killings]] by police forces.'
            q = 'extrajudicial killing'
            (c, r) = find_link.find_link_in_content(q, sample)
            self.assertIn(q, c)
            (c, r) = find_link.find_link_in_text(q, sample)
            self.assertIn(q, c)

        sample = 'units formed with [[SI prefix|metric prefixes]], such as kiloseconds'
        find_link.find_link_in_content('metric prefix', sample)

        sample = u"==Geography==\nA gem of Bermuda's coastline, it is surrounded by [[St. George's Parish, Bermuda|St. George's Parish]] in the north, east, south (Tucker's Town), and [[Hamilton Parish, Bermuda|Hamilton Parish]] in the west. A chain of islands and rocks stretches across the main opening to the [[Atlantic Ocean]], in the east, notably [[Cooper's Island, Bermuda|Cooper's Island]] (which was made a landmass contiguous to St. David's Island and Longbird Island in the 1940s), and [[Nonsuch Island, Bermuda|Nonsuch Island]]. The only channel suitable for large vessels to enter the harbour from the open Atlantic is [[Castle Roads, Bermuda|Castle Roads]], which was historically guarded by a number of fortifications, on [[Castle Island, Bermuda|Castle Island]], Brangman's Island, and Goat Island. Forts were also placed nearby on other small islands, and on the Tucker's Town peninsula of the Main Island. In the west, [[The Causeway, Bermuda|The Causeway]] crosses from the main island to St. David's Island, and beyond this a stretch of water known as [[Ferry Reach, Bermuda|Ferry Reach]] connects the harbour with [[St. George's Harbor, Bermuda|St. George's Harbour]] to the north, where Bermuda's first permanent settlement, [[St. George's, Bermuda|St. George's Town]], was founded in 1612. An unincorporated settlement, [[Tucker's Town, Bermuda|Tucker's Town]], was established on the [[peninsula]] of the [[Main Island, Bermuda|Main Island]] at the south-west of the harbour. The settlement was cleared by compulsory purchase order in the 1920s in order to create a luxury enclave where homes could be purchased by wealthy foreigners, and the attendant Mid Ocean Golf Club. In [[Hamilton Parish, Bermuda|Hamilton Parish]], on the western shore of the harbour, lies [[Walsingham Bay, Bermuda|Walsingham Bay]], the site where, in 1609-10, the crew of the wrecked [[Sea Venture]] built the ''[[Patience]]'', one of two ships built, which carried most of the survivors of the wrecking to [[Jamestown, Virginia|Jamestown]], [[Virginia]], in 1610. The ''Patience'' returned to Bermuda with [[George Somers|Admiral Sir George Somers]], who died in Bermuda later that year."
        find_link.find_link_in_content('compulsory purchase order', sample)

        if False:
            yard = "primary [[Hump yard|hump classification yards]] are located in Allentown."
            for func in find_link.find_link_in_content, find_link.find_link_in_text:
                (c, r) = func('classification yard', yard)
                self.assertEqual(c, yard.replace('[[Hump yard|hump classification yards]]', 'hump [[classification yard]]s'))
                self.assertEqual(r, 'classification yard')

            yard2 = 'A major [[hump yard|railway classification yard]] is north of Blenheim at [[Spring Creek, New Zealand|Spring Creek]].'
            for func in find_link.find_link_in_content, find_link.find_link_in_text:
                (c, r) = func('classification yard', yard2)
                self.assertEqual(c, yard2.replace('[[hump yard|railway classification yard]]', 'railway [[classification yard]]'))
                self.assertEqual(r, 'classification yard')

        yard3 = 'Five houses were destroyed and three others were damaged. A high school was also heavily damaged and railroad cars were thrown in a small freight classification yard. Four people were injured.'
        for func in find_link.find_link_in_content, find_link.find_link_in_text:
            (c, r) = func('classification yard', yard3)
            self.assertEqual(c, yard3.replace('classification yard', '[[classification yard]]'))
            self.assertEqual(r, 'classification yard')

        #yard2 = 'For the section from [[Rotterdam]] to the large [[Kijfhoek (classification yard)|classification yard Kijfhoek]] existing track was reconstructed, but three quarters of the line is new, from Kijfhoek to [[Zevenaar]] near the German border.'
        #(c, r) = find_link.find_link_in_text('classification yard', yard2)

        if False:
            sample = 'GEHA also has a contract with the federal government to administer benefits for the [[Pre-existing Condition Insurance Plan]], which will be a transitional program until 2014.'
            q = 'pre-existing condition'
            for func in find_link.find_link_in_content, find_link.find_link_in_text:
                self.assertRaises(find_link.LinkReplace, func, q, sample)

        station = 'Ticket barriers control access to all platforms, although the bridge entrance has no barriers.'
        (c, r) = find_link.find_link_in_content('ticket barriers', station, linkto='turnstile')
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
            for func in find_link.find_link_in_content, find_link.find_link_in_text:
                (c, r) = func('test phrase', input_content)
                self.assertEqual(c, 'Able to find this [[test phrase]] in an article.')
                self.assertEqual(r, 'test phrase')

        q = 'recoil operation'
        article = 'pattern of long-recoil operation as the 25mm and 40mm guns.'

        search_for_link = find_link.mk_link_matcher(q)
        self.assertFalse(search_for_link(article))

        q = 'after-dinner speaker'
        linkto = 'public speaking'
        sample = 'in demand as an [[Public speaker|after-dinner speaker]].'

        (c, r) = find_link.find_link_in_chunk(q, sample, linkto=linkto)
        self.assertEqual(c, sample.replace('Public speaker', 'public speaking'))

        find_link.get_case_from_content = orig_get_case_from_content
