"""Security helpers for AssetFlow.

This module centralizes password handling and authorization checks so the rest
of the application can apply consistent security rules without duplicating
logic across blueprints and services.
"""

from __future__ import annotations

from functools import wraps
from typing import Callable, TypeVar

from flask import abort
from flask_login import current_user, login_required
from werkzeug.security import check_password_hash, generate_password_hash


ROLE_ADMIN = "Admin"
ROLE_DEPARTMENT_HEAD = "Department Head"
ROLE_ASSET_MANAGER = "Asset Manager"
ROLE_EMPLOYEE = "Employee"

F = TypeVar("F", bound=Callable[..., object])


def hash_password(raw_password: str) -> str:
    """Return a salted hash for a plain-text password."""

    return generate_password_hash(raw_password, method="scrypt")


def verify_password(raw_password: str, password_hash: str) -> bool:
    """Check whether a password matches the stored hash."""

    return check_password_hash(password_hash, raw_password)


def normalize_email(email_address: str) -> str:
    """Normalize email addresses before persistence or lookup."""

    return email_address.strip().lower()


def require_roles(*allowed_roles: str) -> Callable[[F], F]:
    """Restrict a view to the supplied role names."""

    def decorator(view_function: F) -> F:
        @wraps(view_function)
        @login_required
        def wrapped_view(*args: object, **kwargs: object):
            if not getattr(current_user, "role", None):
                abort(403)

            if current_user.role.name not in allowed_roles:
                abort(403)

            return view_function(*args, **kwargs)

        return wrapped_view  # type: ignore[return-value]

    return decorator


def require_admin(view_function: F) -> F:
    """Restrict a view to the Admin role only."""

    @wraps(view_function)
    @login_required
    def wrapped_view(*args: object, **kwargs: object):
        if not getattr(current_user, "role", None) or current_user.role.name != ROLE_ADMIN:
            abort(403)

        return view_function(*args, **kwargs)

    return wrapped_view  # type: ignore[return-value]
