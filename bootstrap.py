"""Database bootstrap utilities for AssetFlow.

This module keeps schema initialization and reference-data seeding out of the
main application factory. It is intended to be executed explicitly during local
setup or deployment bootstrap steps, which keeps the runtime app import clean
while still supporting a production-ready initialization path.
"""

from __future__ import annotations

import os

from sqlalchemy import select

from app import create_app
from extensions import db
from models import Department, Employee, Role, User
from security import (
    ROLE_ADMIN,
    ROLE_ASSET_MANAGER,
    ROLE_DEPARTMENT_HEAD,
    ROLE_EMPLOYEE,
    hash_password,
    normalize_email,
)


DEFAULT_ROLE_NAMES = (
    ROLE_ADMIN,
    ROLE_DEPARTMENT_HEAD,
    ROLE_ASSET_MANAGER,
    ROLE_EMPLOYEE,
)


def ensure_database_schema() -> None:
    """Create all tables defined in the current SQLAlchemy metadata."""

    db.create_all()


def ensure_reference_roles() -> list[Role]:
    """Seed the canonical AssetFlow roles if they do not already exist."""

    seeded_roles: list[Role] = []
    for role_name in DEFAULT_ROLE_NAMES:
        role = db.session.scalar(select(Role).where(Role.name == role_name))
        if role is None:
            role = Role(name=role_name, description=f"{role_name} role for AssetFlow access control.")
            db.session.add(role)
        seeded_roles.append(role)

    db.session.flush()
    return seeded_roles


def ensure_default_department() -> Department:
    """Seed the default onboarding department if the database is empty."""

    department = db.session.scalar(select(Department).where(Department.code == "GENERAL"))
    if department is None:
        department = Department(
            code="GENERAL",
            name="General Administration",
            description="Default department used for first-run onboarding.",
        )
        db.session.add(department)
        db.session.flush()
    return department


def ensure_initial_admin() -> User | None:
    """Create an initial administrator if the matching environment variables exist."""

    admin_email = normalize_email(os.getenv("ASSETFLOW_ADMIN_EMAIL", "").strip())
    admin_password = os.getenv("ASSETFLOW_ADMIN_PASSWORD", "").strip()
    admin_name = os.getenv("ASSETFLOW_ADMIN_NAME", "AssetFlow Admin").strip() or "AssetFlow Admin"

    if not admin_email or not admin_password:
        return None

    existing_admin = db.session.scalar(select(User).where(User.email == admin_email))
    if existing_admin is not None:
        return existing_admin

    admin_role = db.session.scalar(select(Role).where(Role.name == ROLE_ADMIN))
    employee_role = db.session.scalar(select(Role).where(Role.name == ROLE_EMPLOYEE))
    default_department = ensure_default_department()

    if admin_role is None or employee_role is None:
        raise RuntimeError("Core roles must exist before seeding the initial admin user.")

    admin_user = User(
        email=admin_email,
        password_hash=hash_password(admin_password),
        full_name=admin_name,
        role=admin_role,
        department=default_department,
    )
    db.session.add(admin_user)
    db.session.flush()

    employee_profile = Employee(
        employee_number=os.getenv("ASSETFLOW_ADMIN_EMPLOYEE_NUMBER", "EMP-0001").strip(),
        job_title="System Administrator",
        phone_number=None,
        department=default_department,
        user=admin_user,
    )
    db.session.add(employee_profile)
    db.session.flush()

    return admin_user


def bootstrap_database() -> None:
    """Initialize schema and seed reference data in a single transactional step."""

    ensure_database_schema()
    ensure_reference_roles()
    ensure_default_department()
    ensure_initial_admin()
    db.session.commit()


if __name__ == "__main__":
    application = create_app()
    with application.app_context():
        bootstrap_database()
        print("AssetFlow database bootstrap completed successfully.")
