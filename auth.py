"""Authentication blueprint for AssetFlow.

This module owns the first user-facing security flows: login, logout, signup,
and the admin-only promotion action. It stays self-contained so the auth slice
can be introduced without adding template files too early in the hackathon
build.
"""

from __future__ import annotations

from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user
from flask_wtf import FlaskForm
from sqlalchemy import select
from wtforms import BooleanField, PasswordField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Length, Optional

from extensions import db
from models import Department, Employee, Role, User
from security import (
    ROLE_ADMIN,
    ROLE_EMPLOYEE,
    hash_password,
    normalize_email,
    require_admin,
    verify_password,
)


auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


class LoginForm(FlaskForm):
    """Collect credentials for an existing user session."""

    email = StringField("Email", validators=[DataRequired(), Length(max=255)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=8, max=128)])
    remember_me = BooleanField("Remember me")
    submit = SubmitField("Sign in")


class SignupForm(FlaskForm):
    """Collect the information needed to create a new employee account."""

    full_name = StringField("Full name", validators=[DataRequired(), Length(max=150)])
    email = StringField("Email", validators=[DataRequired(), Length(max=255)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=10, max=128)])
    employee_number = StringField("Employee number", validators=[DataRequired(), Length(max=50)])
    job_title = StringField("Job title", validators=[DataRequired(), Length(max=150)])
    phone_number = StringField("Phone number", validators=[Optional(), Length(max=50)])
    department_id = SelectField("Department", coerce=int, validators=[DataRequired()])
    submit = SubmitField("Create employee account")


class PromoteUserForm(FlaskForm):
    """Allow an administrator to assign a higher role."""

    role_id = SelectField("Role", coerce=int, validators=[DataRequired()])
    submit = SubmitField("Promote user")


def _ensure_employee_role() -> Role:
    """Return the Employee role, creating it if the database is still empty."""

    employee_role = db.session.scalar(select(Role).where(Role.name == ROLE_EMPLOYEE))
    if employee_role is None:
        employee_role = Role(name=ROLE_EMPLOYEE, description="Default role for newly registered staff members.")
        db.session.add(employee_role)
        db.session.flush()
    return employee_role


def _ensure_default_department() -> Department:
    """Provide a fallback department for first-run signup flows."""

    department = db.session.scalar(select(Department).where(Department.code == "GENERAL"))
    if department is None:
        department = Department(
            code="GENERAL",
            name="General Administration",
            description="Default onboarding department for the first employee accounts.",
        )
        db.session.add(department)
        db.session.flush()
    return department


def _build_signup_department_choices() -> list[tuple[int, str]]:
    """Return the department options shown on the signup form."""

    departments = db.session.scalars(select(Department).order_by(Department.name.asc())).all()
    if not departments:
        departments = [_ensure_default_department()]
    return [(department.id, f"{department.name} ({department.code})") for department in departments]


def _build_promote_role_choices() -> list[tuple[int, str]]:
    """Return role options available to administrators."""

    roles = db.session.scalars(select(Role).order_by(Role.name.asc())).all()
    return [(role.id, role.name) for role in roles if role.name != ROLE_EMPLOYEE]


@auth_bp.route("/login", methods=["GET", "POST"])
def login() -> str:
    """Authenticate a user and start a session."""

    form = LoginForm()
    if form.validate_on_submit():
        email_address = normalize_email(form.email.data)
        user = db.session.scalar(select(User).where(User.email == email_address))

        if user is None or not verify_password(form.password.data, user.password_hash):
            flash("Invalid email or password.", "danger")
        elif not user.is_active_account:
            flash("This account is disabled. Contact an administrator.", "warning")
        else:
            user.last_login_at = datetime.utcnow()
            db.session.commit()
            login_user(user, remember=form.remember_me.data)
            flash("Welcome back to AssetFlow.", "success")
            return redirect(url_for("dashboard"))

    return render_template(
      "auth/login.html",
      form=form,
      page_title="Sign in",
      page_subtitle="Access the AssetFlow workspace.",
      current_year=datetime.utcnow().year,
    )


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup() -> str:
    """Create a new employee account using the default employee role."""

    form = SignupForm()
    form.department_id.choices = _build_signup_department_choices()

    if form.validate_on_submit():
        normalized_email = normalize_email(form.email.data)
        existing_user = db.session.scalar(select(User).where(User.email == normalized_email))

        if existing_user is not None:
            flash("An account with that email already exists.", "warning")
        else:
            employee_role = _ensure_employee_role()
            selected_department = db.session.get(Department, form.department_id.data)

            if selected_department is None:
                selected_department = _ensure_default_department()

            user = User(
                email=normalized_email,
                password_hash=hash_password(form.password.data),
                full_name=form.full_name.data.strip(),
                role=employee_role,
                department=selected_department,
            )
            db.session.add(user)
            db.session.flush()

            employee = Employee(
                employee_number=form.employee_number.data.strip(),
                job_title=form.job_title.data.strip(),
                phone_number=form.phone_number.data.strip() or None,
                department=selected_department,
                user=user,
            )
            db.session.add(employee)
            db.session.commit()

            flash("Employee account created. Sign in to continue.", "success")
            return redirect(url_for("auth.login"))

    return render_template(
      "auth/signup.html",
      form=form,
      page_title="Create account",
      page_subtitle="Register a new employee profile.",
      current_year=datetime.utcnow().year,
    )


@auth_bp.route("/logout", methods=["POST"])
def logout() -> str:
    """Terminate the current session safely."""

    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/users/<int:user_id>/promote", methods=["GET", "POST"])
@require_admin
def promote_user(user_id: int) -> str:
    """Allow an administrator to promote a user to a higher role."""

    user = db.session.get(User, user_id)
    if user is None:
        flash("User not found.", "danger")
        return redirect(url_for("dashboard"))

    form = PromoteUserForm()
    form.role_id.choices = _build_promote_role_choices()

    if not form.role_id.choices:
        flash("No promotable roles are configured yet.", "warning")
        return redirect(url_for("dashboard"))

    if form.validate_on_submit():
        selected_role = db.session.get(Role, form.role_id.data)
        if selected_role is None or selected_role.name == ROLE_EMPLOYEE:
            flash("Please select a valid elevated role.", "warning")
        else:
            user.role = selected_role
            db.session.commit()
            flash(f"{user.full_name} was promoted to {selected_role.name}.", "success")
            return redirect(url_for("dashboard"))

    return render_template(
      "auth/promote.html",
      form=form,
      user=user,
      page_title="Promote user",
      page_subtitle="Admin-only role assignment.",
      current_year=datetime.utcnow().year,
    )


AUTH_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ page_title }} | AssetFlow</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    body {
      margin: 0;
      min-height: 100vh;
      font-family: "Inter", system-ui, sans-serif;
      background: linear-gradient(135deg, #07111f 0%, #0f172a 55%, #111827 100%);
      color: #e5eefc;
      display: grid;
      place-items: center;
      padding: 1.5rem;
    }

    .auth-shell {
      width: min(1120px, 100%);
      display: grid;
      grid-template-columns: minmax(0, 0.95fr) minmax(360px, 420px);
      gap: 1.5rem;
      align-items: center;
    }

    .hero-panel,
    .form-panel {
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 28px;
      background: rgba(8, 15, 29, 0.76);
      box-shadow: 0 28px 80px rgba(0, 0, 0, 0.32);
      backdrop-filter: blur(18px);
    }

    .hero-panel {
      padding: 2.25rem;
      min-height: 540px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      background:
        radial-gradient(circle at top right, rgba(15, 98, 254, 0.35), transparent 30%),
        radial-gradient(circle at bottom left, rgba(14, 165, 233, 0.2), transparent 28%),
        rgba(8, 15, 29, 0.76);
    }

    .brand-pill {
      display: inline-flex;
      align-items: center;
      gap: 0.65rem;
      padding: 0.55rem 0.85rem;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.06);
      width: fit-content;
    }

    .brand-mark {
      width: 42px;
      height: 42px;
      border-radius: 14px;
      display: grid;
      place-items: center;
      background: linear-gradient(135deg, #0f62fe, #0ea5e9);
      font-weight: 800;
    }

    .hero-panel h1 {
      font-size: clamp(2rem, 4vw, 3.6rem);
      font-weight: 800;
      line-height: 1.02;
      margin: 1.5rem 0 1rem;
      max-width: 12ch;
    }

    .hero-panel p {
      color: rgba(229, 238, 252, 0.8);
      max-width: 58ch;
      font-size: 1rem;
      line-height: 1.7;
    }

    .feature-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 0.85rem;
      margin-top: 1.5rem;
    }

    .feature-card {
      padding: 1rem;
      border-radius: 20px;
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid rgba(255, 255, 255, 0.06);
    }

    .feature-card strong {
      display: block;
      margin-bottom: 0.35rem;
    }

    .feature-card span {
      color: rgba(229, 238, 252, 0.72);
      font-size: 0.9rem;
    }

    .form-panel {
      padding: 1.5rem;
    }

    .form-panel h2 {
      font-size: 1.45rem;
      font-weight: 800;
      margin-bottom: 0.4rem;
    }

    .form-panel .text-muted {
      color: rgba(229, 238, 252, 0.68) !important;
    }

    .form-control,
    .form-select {
      background: rgba(255, 255, 255, 0.04);
      border-color: rgba(255, 255, 255, 0.12);
      color: #fff;
      border-radius: 14px;
      padding: 0.8rem 0.95rem;
    }

    .form-control:focus,
    .form-select:focus {
      border-color: #0f62fe;
      box-shadow: 0 0 0 0.2rem rgba(15, 98, 254, 0.2);
      background: rgba(255, 255, 255, 0.06);
      color: #fff;
    }

    .form-check-input {
      background-color: rgba(255, 255, 255, 0.15);
      border-color: rgba(255, 255, 255, 0.2);
    }

    .btn-primary {
      background: linear-gradient(135deg, #0f62fe, #0ea5e9);
      border: 0;
      border-radius: 14px;
      padding: 0.85rem 1rem;
      font-weight: 700;
    }

    .helper-links a {
      color: #8cc4ff;
      text-decoration: none;
    }

    .flash-list .alert {
      border-radius: 14px;
    }

    @media (max-width: 992px) {
      .auth-shell {
        grid-template-columns: 1fr;
      }

      .hero-panel {
        min-height: auto;
      }
    }
  </style>
</head>
<body>
  <div class="auth-shell">
    <section class="hero-panel">
      <div>
        <div class="brand-pill">
          <div class="brand-mark">AF</div>
          <div>
            <div class="fw-bold">AssetFlow</div>
            <small class="text-white-50">Enterprise Asset & Resource Management System</small>
          </div>
        </div>
        <h1>{{ page_title }}</h1>
        <p>{{ page_subtitle }}</p>
        <div class="feature-grid">
          <div class="feature-card">
            <strong>Role-driven access</strong>
            <span>Every action is constrained by user role and session state.</span>
          </div>
          <div class="feature-card">
            <strong>Audit-ready</strong>
            <span>Authentication events can be extended into activity logs.</span>
          </div>
          <div class="feature-card">
            <strong>Employee signup</strong>
            <span>Public registration creates employee accounts only.</span>
          </div>
          <div class="feature-card">
            <strong>Admin promotion</strong>
            <span>Only administrators can elevate a user's role.</span>
          </div>
        </div>
      </div>
      <small class="text-white-50">Secure session handling for {{ current_year }}.</small>
    </section>

    <section class="form-panel">
      <div class="flash-list mb-3">
        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}
            {% for category, message in messages %}
              <div class="alert alert-{{ category }} mb-2" role="alert">{{ message }}</div>
            {% endfor %}
          {% endif %}
        {% endwith %}
      </div>
      {{ body_html | safe }}
    </section>
  </div>
</body>
</html>
"""


LOGIN_FORM_TEMPLATE = """
<h2>Sign in</h2>
<p class="text-muted mb-4">Use your AssetFlow credentials to access the dashboard.</p>
<form method="post" novalidate>
  {{ form.hidden_tag() }}
  <div class="mb-3">
    {{ form.email.label(class_="form-label") }}
    {{ form.email(class_="form-control", placeholder="name@company.com") }}
  </div>
  <div class="mb-3">
    {{ form.password.label(class_="form-label") }}
    {{ form.password(class_="form-control", placeholder="Enter your password") }}
  </div>
  <div class="d-flex align-items-center justify-content-between mb-4">
    <div class="form-check">
      {{ form.remember_me(class_="form-check-input") }}
      {{ form.remember_me.label(class_="form-check-label") }}
    </div>
    <a class="helper-links" href="{{ url_for('auth.signup') }}">Create account</a>
  </div>
  {{ form.submit(class_="btn btn-primary w-100") }}
</form>
"""


SIGNUP_FORM_TEMPLATE = """
<h2>Create employee account</h2>
<p class="text-muted mb-4">Public signup provisions an employee profile and default role.</p>
<form method="post" novalidate>
  {{ form.hidden_tag() }}
  <div class="mb-3">
    {{ form.full_name.label(class_="form-label") }}
    {{ form.full_name(class_="form-control", placeholder="Full name") }}
  </div>
  <div class="mb-3">
    {{ form.email.label(class_="form-label") }}
    {{ form.email(class_="form-control", placeholder="name@company.com") }}
  </div>
  <div class="mb-3">
    {{ form.password.label(class_="form-label") }}
    {{ form.password(class_="form-control", placeholder="Minimum 10 characters") }}
  </div>
  <div class="mb-3">
    {{ form.employee_number.label(class_="form-label") }}
    {{ form.employee_number(class_="form-control", placeholder="EMP-0001") }}
  </div>
  <div class="mb-3">
    {{ form.job_title.label(class_="form-label") }}
    {{ form.job_title(class_="form-control", placeholder="Job title") }}
  </div>
  <div class="mb-3">
    {{ form.phone_number.label(class_="form-label") }}
    {{ form.phone_number(class_="form-control", placeholder="Optional phone number") }}
  </div>
  <div class="mb-4">
    {{ form.department_id.label(class_="form-label") }}
    {{ form.department_id(class_="form-select") }}
  </div>
  <div class="d-grid gap-2">
    {{ form.submit(class_="btn btn-primary") }}
    <a class="btn btn-outline-light" href="{{ url_for('auth.login') }}">Back to sign in</a>
  </div>
</form>
"""


PROMOTE_FORM_TEMPLATE = """
<h2>Promote {{ user.full_name }}</h2>
<p class="text-muted mb-4">Assign a higher role to this employee account.</p>
<form method="post" novalidate>
  {{ form.hidden_tag() }}
  <div class="mb-4">
    {{ form.role_id.label(class_="form-label") }}
    {{ form.role_id(class_="form-select") }}
  </div>
  <div class="d-grid gap-2">
    {{ form.submit(class_="btn btn-primary") }}
    <a class="btn btn-outline-light" href="{{ url_for('dashboard') }}">Cancel</a>
  </div>
</form>
"""
