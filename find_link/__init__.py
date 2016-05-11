from __future__ import unicode_literals
from flask import Flask
import find_link.view

def create_app():
    app = Flask(__name__)
    app.config.from_pyfile('config')
    find_link.view.init_app(app)
    return app
