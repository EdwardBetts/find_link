from __future__ import unicode_literals
from .util import is_title_case, lc_alpha
from .core import get_content_and_timestamp, get_case_from_content
from .api import get_wiki_info, call_get_diff, MissingPage
import re

re_link_in_text = re.compile(r'\[\[[^]]+?\]\]', re.I | re.S)

class LinkReplace(Exception):
    pass

en_dash = u'\u2013'
trans = {',': ',?', ' ': ' *[-\n]? *'}
trans[en_dash] = trans[' ']

trans2 = {' ': r"('?s?\]\])?'?s? ?(\[\[(?:.+\|)?)?", '-': '[- ]'}
trans2[en_dash] = trans2[' ']

patterns = [
    lambda q: re.compile(r'(?<!-)(?:\[\[(?:[^]]+\|)?)?(%s)%s(?:\]\])?' % (re.escape(q[0]), ''.join('-?' + (trans2[c] if c in trans2 else re.escape(c)) for c in q[1:])), re.I),
    lambda q: re.compile(r'(?<!-)\[\[[^|]+\|(%s)%s\]\]' % (re.escape(q[0]), re.escape(q[1:])), re.I),
    lambda q: re.compile(r'(?<!-)\[\[[^|]+\|(%s)%s(?:\]\])?' % (re.escape(q[0]), ''.join('-?' + (trans2[c] if c in trans2 else re.escape(c)) for c in q[1:])), re.I),
    lambda q: re.compile(r'(?<!-)(%s)%s' % (re.escape(q[0]), re.escape(q[1:])), re.I),
    lambda q: re.compile(r'(?<!-)(%s)%s' % (re.escape(q[0]), ''.join((trans[c] if c in trans else re.escape(c)) for c in q[1:])), re.I),
]

class NoMatch(Exception):
    pass

re_cite = re.compile(r'<ref( [^>]*?)?>\s*({{cite.*?}}|\[https?://[^]]*?\])\s*</ref>', re.I | re.S)

def parse_cite(text):
    prev = 0
    for m in re_cite.finditer(text):
        yield ('text', text[prev:m.start()])
        yield ('cite', m.group(0))
        prev = m.end()
    yield ('text', text[prev:])

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
                lc_alpha_q = lc_alpha(q)

                bad_link_match = link_dest and len(link_dest) > len(q) and (lc_alpha_q not in lc_alpha(link_dest))
                if not link_dest:
                    if q in link_text and len(link_text) > len(q):
                        bad_link_match = True
                if bad_link_match and link_dest:
                    try:
                        link_dest_redirect = get_wiki_info(link_dest)
                    except MissingPage:
                        link_dest_redirect = None
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

def get_diff(q, title, linkto):
    content, timestamp = get_content_and_timestamp(title)
    found = find_link_and_section(q, content, linkto)

    section_text = found['section_text'] + get_subsections(content, found['section_num'])

    diff = call_get_diff(title, found['section_num'], section_text)
    return (diff, found['replacement'])
