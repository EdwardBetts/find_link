import re
import urllib

# util functions that don't access the network

re_space_or_dash = re.compile('[ -]')
def is_title_case(phrase):
    '''Detected if a given phrase is in Title Case.'''
    return all(term[0].isupper() and term[1:].islower()
               for term in re_space_or_dash.split(phrase))

def urlquote(value):
    '''prepare string for use in URL param'''
    return urllib.parse.quote_plus(value.encode('utf-8'))

re_end_parens = re.compile(r' \(.*\)$')
def strip_parens(q):
    m = re_end_parens.search(q)
    return q[:m.start()] if m else q

def is_disambig(doc):
    '''Is a this a disambiguation page?'''
    return any('disambig' in t or t.endswith('dis') or 'given name' in t or
               t == 'template:surname' for t in
               (t['title'].lower() for t in doc.get('templates', [])))

re_non_letter = re.compile('\W', re.U)
def norm(s):
    '''Normalise string.'''
    s = re_non_letter.sub('', s).lower()
    return s[:-1] if s and s[-1] == 's' else s

def case_flip(s):
    '''Switch case of character.'''
    if s.islower():
        return s.upper()
    if s.isupper():
        return s.lower()
    return s

def case_flip_first(s):
    return case_flip(s[0]) + s[1:]

def lc_alpha(s):
    return ''.join(c.lower() for c in s if c.isalpha())

def wiki_space_norm(s):
    return s.replace('_', ' ').strip()
