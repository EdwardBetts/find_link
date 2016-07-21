from __future__ import unicode_literals
import urllib.parse
from .api import Missing, wiki_redirects, get_wiki_info, api_get
from .util import urlquote, case_flip_first, wiki_space_norm, starts_with_namespace
from .core import do_search, get_content_and_timestamp
from .match import NoMatch, find_link_in_content, get_diff
from flask import Blueprint, Markup, redirect, request, url_for, render_template
from datetime import datetime
from cProfile import Profile

bp = Blueprint('view', __name__)

def init_app(app):
    app.register_blueprint(bp)

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

@bp.route('/diff')
def diff_view():
    q = request.args.get('q')
    title = request.args.get('title')
    linkto = request.args.get('linkto')

    try:
        diff, replacement = get_diff(q, title, linkto)
    except NoMatch:
        return "can't generate diff"

    return '<table>' + diff + '</table>'

@bp.route("/<path:q>")
def findlink(q, title=None, message=None):
    if q and '%' in q:  # double encoding
        q = urllib.parse.unquote(q)
    q_trim = q.strip('_')
    if not message and (' ' in q or q != q_trim):
        return redirect(url_for('.findlink', q=q.replace(' ', '_').strip('_'),
                        message=message))
    q = q.replace('_', ' ').strip()

    if starts_with_namespace(q):
        return render_template('index.html',
                               message="'{}' isn't in the article namespace".format(q))

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

    # profile
    p = Profile()
    ret = p.runcall(do_search, q, redirect_to)

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

@bp.route("/")
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
        return redirect(url_for('.findlink', q=q.replace(' ', '_').strip('_')))
    return render_template('index.html')
