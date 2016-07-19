import logging
from logging.handlers import SMTPHandler
from logging import Formatter

def setup_error_mail(app):
    mail_handler = SMTPHandler(app.config['SMTP_HOST'],
                               app.config['MAIL_FROM'],
                               app.config['ADMINS'],
                               app.name + ' error')
    mail_handler.setFormatter(Formatter('''
    Message type:       %(levelname)s
    Location:           %(pathname)s:%(lineno)d
    Module:             %(module)s
    Function:           %(funcName)s
    Time:               %(asctime)s

    Message:

    %(message)s
    '''))

    mail_handler.setLevel(logging.ERROR)
    app.logger.addHandler(mail_handler)

