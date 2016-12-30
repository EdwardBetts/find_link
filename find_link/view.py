from __future__ import unicode_literals
import urllib.parse
from .api import wiki_redirects, get_wiki_info, api_get, MissingPage, MediawikiError, MultipleRedirects
from .util import urlquote, case_flip_first, wiki_space_norm, starts_with_namespace
from .core import do_search, get_content_and_timestamp
from .match import NoMatch, find_link_in_content, get_diff, LinkReplace
from flask import Blueprint, Markup, redirect, request, url_for, render_template, session, flash
from datetime import datetime
from cProfile import Profile
from .language import get_langs, get_current_language
import re

bp = Blueprint('view', __name__)

re_lang = re.compile('^(' + '|'.join(l['code'] for l in get_langs()) + '):(.*)$')

def init_app(app):
    app.register_blueprint(bp)

def get_page(title, q, linkto=None):
    content, timestamp = get_content_and_timestamp(title)
    timestamp = ''.join(c for c in timestamp if c.isdigit())
    current_lang = get_current_language()

    try:
        (content, replacement, replaced_text) = find_link_in_content(q, content, linkto)
    except NoMatch:
        return None
    except LinkReplace:
        return link_replace(title, q, linkto)

    summary = "link [[%s]] using [[:en:User:Edward/Find link|Find link]]" % replacement

    start_time = datetime.now().strftime("%Y%m%d%H%M%S")
    return render_template('find_link.html', urlquote=urlquote,
                           start_time=start_time, content=content, title=title,
                           summary=summary, timestamp=timestamp,
                           current_lang=current_lang)

@bp.route('/diff')
def diff_view():
    q = request.args.get('q')
    title = request.args.get('title')
    linkto = request.args.get('linkto')

    if not q or not title:
        return redirect(url_for('.index'))

    try:
        diff, replacement = get_diff(q, title, linkto)
    except NoMatch:
        return "can't generate diff"

    return '<table>' + diff + '</table>'

def lang_from_q(q):
    m = re_lang.match(q)
    if not m:
        return q
    session['current_lang'] = m.group(1)
    return m.group(2)

@bp.route("/<path:q>")
def findlink(q, title=None, message=None):
    q = lang_from_q(q)
    langs = get_langs()
    current_lang = get_current_language()
    if q and '%' in q:  # double encoding
        q = urllib.parse.unquote(q)
    q_trim = q.strip('_')
    if not message and (' ' in q or q != q_trim):
        return redirect(url_for('.findlink', q=q.replace(' ', '_').strip('_'),
                        message=message))
    q = q.replace('_', ' ').strip()

    if starts_with_namespace(q):
        return render_template('index.html',
                               message="'{}' isn't in the article namespace".format(q),
                               langs=langs, current_lang=current_lang)

    try:
        redirect_to = get_wiki_info(q)
    except MissingPage:
        return render_template('index.html', message=q + " isn't an article",
                               langs=langs, current_lang=current_lang)
    except MultipleRedirects:
        return render_template('index.html', message=q + " is a redirect to a redirect, this isn't supported",
                               langs=langs, current_lang=current_lang)
    # if redirect_to:
    #     return redirect(url_for('findlink', q=redirect_to.replace(' ', '_')))
    if redirect_to:
        if q[0].isupper():
            redirect_to = redirect_to[0].upper() + redirect_to[1:]
        elif q[0].islower():
            redirect_to = redirect_to[0].lower() + redirect_to[1:]

    # profile
    p = Profile()
    try:
        ret = p.runcall(do_search, q, redirect_to)
    except MediawikiError as e:
        return e.args[0]

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
        case_flip_first=case_flip_first,
        langs=langs,
        current_lang=current_lang)

@bp.route("/favicon.ico")
def favicon():
    return redirect(url_for('static', filename='Link_edit.png'))

@bp.route("/new_pages")
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

@bp.route("/find_link/<q>")
def bad_url(q):
    return findlink(q)

def link_replace(title, q, linkto=None):
    current_lang = get_current_language()
    try:
        diff, replacement = get_diff(q, title, linkto)
    except NoMatch:
        diff = "can't generate diff"
        replacement = None
    except MediawikiError as e:
        diff = e.args[0]
        replacement = None

    return render_template('link_replace.html',
                           title=title,
                           q=q,
                           diff=diff,
                           replacement=replacement,
                           current_lang=current_lang)


def missing_page(title, q, linkto=None):
    return render_template('missing_page.html', title=title, q=q)

@bp.route("/set_lang/<code>")
def set_lang(code):
    session['current_lang'] = code
    flash('language updated')
    return redirect(url_for('.index', lang=code))

def lang_from_request():
    langs = get_langs()
    valid_languages = {l['code'] for l in langs}
    lang_arg = request.args.get('lang')
    if lang_arg and lang_arg.strip().lower() in valid_languages:
        session['current_lang'] = lang_arg.strip()

@bp.route("/")
def index():
    langs = get_langs()
    title = request.args.get('title')
    q = request.args.get('q')
    linkto = request.args.get('linkto')

    if q and ':' in q:
        q = lang_from_q(q)
    else:
        lang_from_request()
    current_lang = get_current_language()

    if title and q:
        if len(title) > 255:
            return findlink(q.replace(' ', '_'), title=title,
                            message='title too long: "{}"'.format(title))

        q = wiki_space_norm(q)
        title = wiki_space_norm(title)
        if linkto:
            linkto = wiki_space_norm(linkto)
        try:
            reply = get_page(title, q, linkto)
        except MediawikiError as e:
            return findlink(q.replace(' ', '_'), title=title, message=e.args[0])
        except LinkReplace:
            return link_replace(title, q, linkto)
        except MissingPage:
            return missing_page(title, q, linkto)
        if reply:
            return reply
        try:
            redirects = list(wiki_redirects(q))
        except MediawikiError as e:
            return findlink(q.replace(' ', '_'), title=title, message=e.args[0])
        for r in redirects:
            reply = get_page(title, r, linkto=q)
            if reply:
                return reply
        return findlink(q.replace(' ', '_'), title=title,
                        message=q + ' not in ' + title)
    if q:
        return redirect(url_for('.findlink', q=q.replace(' ', '_').strip('_')))
    return render_template('index.html',
                           langs=langs,
                           current_lang=current_lang)
