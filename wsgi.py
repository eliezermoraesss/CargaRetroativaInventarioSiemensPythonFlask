"""
WSGI entrypoint for Apache / mod_wsgi or other WSGI servers.

This file exposes the Flask `app` instance as `application`.
"""
from app import app as application
