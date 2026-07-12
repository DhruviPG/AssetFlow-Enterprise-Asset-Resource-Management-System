"""Shared Flask extensions for AssetFlow.

Keeping Flask integrations in one module prevents circular imports and makes it
easy for the application factory, models, forms, and blueprints to share the
same configured instances.
"""

from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect


db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
