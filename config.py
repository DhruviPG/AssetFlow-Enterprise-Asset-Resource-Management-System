"""Application configuration for AssetFlow.

The configuration layer keeps environment-specific settings out of the Flask
entrypoint so the project can evolve cleanly into development, staging, and
production deployments.
"""

from __future__ import annotations

import os
from datetime import timedelta


class BaseConfig:
    """Base settings shared by every runtime environment."""

    SECRET_KEY = os.getenv("ASSETFLOW_SECRET_KEY", "assetflow-dev-secret-key")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(days=14)
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///assetflow.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_TIME_LIMIT = 3600


class DevelopmentConfig(BaseConfig):
    """Development defaults that favor fast local iteration."""

    DEBUG = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///assetflow.db"


class ProductionConfig(BaseConfig):
    """Production defaults that favor stable, explicit runtime behavior."""

    DEBUG = False


def get_config() -> type[BaseConfig]:
    """Return the config class that matches the current environment."""

    environment_name = os.getenv("FLASK_ENV", "development").strip().lower()
    if environment_name == "production":
        return ProductionConfig
    return DevelopmentConfig
