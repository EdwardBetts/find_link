import re
import urllib

# util functions that don't access the network

namespaces = {ns.casefold() for ns in ('Special', 'Media', 'Talk', 'Template',
              'Portal', 'Portal talk', 'Book', 'Book talk', 'Template talk',
              'Draft', 'Draft talk', 'Help', 'Help talk',
              'Category', 'Category talk', 'User', 'Gadget', 'Gadget talk',
              'Gadget definition', 'Gadget definition talk', 'Topic',
              'User talk', 'Wikipedia',
              'Education Program', 'Education Program talk', 'Wikipedia talk',
              'File', 'File talk', 'TimedText', 'TimedText talk', 'MediaWiki',
              'Module', 'Module talk', 'MediaWiki talk')}

re_space_or_dash = re.compile('[ -]')
def is_title_case(phrase):
    '''Detected if a given phrase is in Title Case.'''
    return all(term[0].isupper() and term[1:].islower()
               for term in re_space_or_dash.split(phrase)
               if term and term[0].isalpha())

def urlquote(value):
    '''prepare string for use in URL param'''
    return urllib.parse.quote_plus(value.encode('utf-8'))


re_end_parens = re.compile(r' \(.*\)$')
def strip_parens(q):
    m = re_end_parens.search(q)
    return q[:m.start()] if m else q

def starts_with_namespace(title):
    return ':' in title and title.split(':', 1)[0].casefold() in namespaces

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
