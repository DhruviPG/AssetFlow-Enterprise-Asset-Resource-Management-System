"""WSGI entrypoint for AssetFlow.

Gunicorn and other WSGI servers import the Flask application from this file
so the runtime entrypoint stays explicit and deployment friendly.
"""

from app import app
