from __future__ import unicode_literals
from flask import Flask, request
import find_link.view
from .error_mail import setup_error_mail

class MyFlask(Flask):
    def log_exception(self, exc_info):
        self.logger.error("""
Path:                 %s
HTTP Method:          %s
Client IP Address:    %s
User Agent:           %s
User Platform:        %s
User Browser:         %s
User Browser Version: %s
GET args:             %s
view args:            %s
URL:                  %s
""" % (
            request.path,
            request.method,
            request.remote_addr,
            request.user_agent.string,
            request.user_agent.platform,
            request.user_agent.browser,
            request.user_agent.version,
            dict(request.args),
            request.view_args,
            request.url
        ), exc_info=exc_info)

def create_app():
    app = MyFlask(__name__)
    app.config.from_pyfile('config')
    find_link.view.init_app(app)
    setup_error_mail(app)
    return app
