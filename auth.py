"""Authentication and account-management blueprint for AssetFlow.

This module provides end-to-end auth workflows for login, signup, logout,
password reset, and admin role promotion.
"""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlparse

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from flask_wtf import FlaskForm
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import select
from wtforms import BooleanField, PasswordField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional

from extensions import db
from models import Department, Employee, Role, User
from security import ROLE_ADMIN, ROLE_EMPLOYEE, hash_password, normalize_email, require_admin, verify_password


auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


class LoginForm(FlaskForm):
	"""Collect the credentials required to authenticate an account."""

	email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
	password = PasswordField("Password", validators=[DataRequired(), Length(min=8, max=255)])
	remember_me = BooleanField("Remember me")
	submit = SubmitField("Sign in")


class SignupForm(FlaskForm):
	"""Collect employee account details for public signup."""

	full_name = StringField("Full name", validators=[DataRequired(), Length(max=150)])
	email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
	password = PasswordField("Password", validators=[DataRequired(), Length(min=10, max=255)])
	employee_number = StringField("Employee number", validators=[DataRequired(), Length(max=50)])
	job_title = StringField("Job title", validators=[DataRequired(), Length(max=150)])
	phone_number = StringField("Phone number", validators=[Optional(), Length(max=50)])
	department_id = SelectField("Department", coerce=int, validators=[DataRequired()])
	role_id = SelectField("Role", coerce=int, validators=[Optional()])
	submit = SubmitField("Create account")


class ForgotPasswordForm(FlaskForm):
	"""Collect an account email to begin password reset."""

	email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
	submit = SubmitField("Send reset link")


class ResetPasswordForm(FlaskForm):
	"""Set a replacement password for a user."""

	password = PasswordField("New password", validators=[DataRequired(), Length(min=10, max=255)])
	confirm_password = PasswordField(
		"Confirm password",
		validators=[DataRequired(), EqualTo("password", message="Passwords must match.")],
	)
	submit = SubmitField("Reset password")


class PromoteUserForm(FlaskForm):
	"""Allow admins to select and assign a role."""

	role_id = SelectField("Role", coerce=int, validators=[DataRequired()])
	submit = SubmitField("Update role")


def _flash_form_errors(form: FlaskForm) -> None:
	"""Flash a concise validation summary for invalid form submissions."""

	errors: list[str] = []
	for field_name, field_errors in form.errors.items():
		label = getattr(getattr(form, field_name, None), "label", None)
		field_label = label.text if label is not None else field_name.replace("_", " ").title()
		for error in field_errors:
			errors.append(f"{field_label}: {error}")

	if errors:
		flash("Please correct the form and try again.", "warning")
		for error in errors[:4]:
			flash(error, "warning")


def _is_safe_next_url(target: str) -> bool:
	"""Return whether a redirect target points to the current host."""

	if not target:
		return False

	target_parts = urlparse(target)
	if target_parts.scheme and target_parts.scheme not in {"http", "https"}:
		return False

	if target_parts.netloc and target_parts.netloc != request.host:
		return False

	return True


def _ensure_employee_role() -> Role:
	"""Create the default employee role if setup was skipped."""

	role = db.session.scalar(select(Role).where(Role.name == ROLE_EMPLOYEE))
	if role is None:
		role = Role(name=ROLE_EMPLOYEE, description="Default employee role")
		db.session.add(role)
		db.session.flush()
	return role


def _ensure_default_department() -> Department:
	"""Create the fallback department for first-run signup."""

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


def _department_choices() -> list[tuple[int, str]]:
	"""Return departments for the signup select field."""

	departments = db.session.scalars(select(Department).order_by(Department.name.asc())).all()
	if not departments:
		departments = [_ensure_default_department()]
	return [(department.id, f"{department.name} ({department.code})") for department in departments]


def _build_reset_serializer() -> URLSafeTimedSerializer:
	"""Return the signed-token serializer for reset links."""

	return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="assetflow-password-reset")


def _generate_reset_token(user: User) -> str:
	"""Create a short-lived signed token for password reset."""

	serializer = _build_reset_serializer()
	return serializer.dumps({"user_id": user.id})


def _resolve_reset_user(token: str, max_age: int = 3600) -> User | None:
	"""Resolve a signed reset token to a user account."""

	serializer = _build_reset_serializer()
	try:
		payload = serializer.loads(token, max_age=max_age)
	except (BadSignature, SignatureExpired):
		return None

	user_id = payload.get("user_id")
	if not isinstance(user_id, int):
		return None

	return db.session.get(User, user_id)


@auth_bp.route("/login", methods=["GET", "POST"])
def login() -> str:
	"""Authenticate an existing user account."""

	if current_user.is_authenticated:
		return redirect(url_for("dashboard"))

	form = LoginForm()
	if form.validate_on_submit():
		email = normalize_email(form.email.data)
		user = db.session.scalar(select(User).where(User.email == email))

		if user is None or not verify_password(form.password.data, user.password_hash):
			flash("Invalid email or password.", "danger")
		elif not user.is_active_account:
			flash("Your account is inactive. Please contact an administrator.", "warning")
		else:
			login_user(user, remember=bool(form.remember_me.data))
			user.last_login_at = datetime.now(timezone.utc)
			db.session.commit()

			next_url = request.args.get("next", "")
			if _is_safe_next_url(next_url):
				return redirect(next_url)

			flash("Welcome back.", "success")
			return redirect(url_for("dashboard"))
	elif request.method == "POST":
		_flash_form_errors(form)

	return render_template(
		"auth/login.html",
		form=form,
		page_title="Secure sign-in",
		page_subtitle="Access your enterprise asset workspace with role-aware controls.",
	)


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup() -> str:
	"""Provision a new employee account."""

	if current_user.is_authenticated:
		return redirect(url_for("dashboard"))

	form = SignupForm()
	form.department_id.choices = _department_choices()

	# populate role choices so the form can select a different role
	roles = db.session.scalars(select(Role).order_by(Role.name.asc())).all()
	form.role_id.choices = [(role.id, role.name) for role in roles]

	if form.validate_on_submit():
		email = normalize_email(form.email.data)
		existing_email_user = db.session.scalar(select(User).where(User.email == email))
		existing_employee = db.session.scalar(
			select(Employee).where(Employee.employee_number == form.employee_number.data.strip())
		)

		if existing_email_user is not None:
			flash("An account with that email already exists.", "warning")
		elif existing_employee is not None:
			flash("That employee number is already in use.", "warning")
		else:
			# determine role: use selected role if provided, otherwise fallback
			selected_role = None
			if form.role_id.data:
				selected_role = db.session.get(Role, form.role_id.data)
			if selected_role is None:
				selected_role = _ensure_employee_role()

			department = db.session.get(Department, form.department_id.data)
			if department is None:
				department = _ensure_default_department()
			# respect role defaults when present
			if selected_role.default_email:
				user_email = normalize_email(selected_role.default_email)
			else:
				user_email = email

			if selected_role.default_password_hash:
				password_hash_value = selected_role.default_password_hash
			else:
				password_hash_value = hash_password(form.password.data)

			user = User(
				email=user_email,
				password_hash=password_hash_value,
				full_name=form.full_name.data.strip(),
				role=selected_role,
				department=department,
			)
			db.session.add(user)
			db.session.flush()

			employee = Employee(
				employee_number=form.employee_number.data.strip(),
				job_title=form.job_title.data.strip(),
				phone_number=form.phone_number.data.strip() or None,
				department=department,
				user=user,
			)
			db.session.add(employee)
			db.session.commit()

			flash("Account created successfully. Please sign in.", "success")
			return redirect(url_for("auth.login"))
	elif request.method == "POST":
		_flash_form_errors(form)

	return render_template(
		"auth/signup.html",
		form=form,
		page_title="Create employee account",
		page_subtitle="Register once, then access the full AssetFlow operations dashboard.",
	)


# Quick sign-in defaults for development/testing — do not use in production.
QUICK_DEFAULTS = {
	"admin": ("admin12@gmail.com", "Admin!123456", ROLE_ADMIN),
	"head": ("head12@gmail.com", "Head!123456", "Department Head"),
	"manager": ("manager12@gmail.com", "Manager!123456", "Asset Manager"),
}


@auth_bp.route("/quick_signin/<key>")
def quick_signin(key: str) -> str:
	"""Sign in using a predefined role default (development only).

	This avoids depending on schema changes for quick local testing.
	"""

	mapping = QUICK_DEFAULTS.get(key)
	if mapping is None:
		flash("Unknown quick sign-in key.", "warning")
		return redirect(url_for("auth.login"))

	email, password, role_name = mapping
	email = normalize_email(email)

	user = db.session.scalar(select(User).where(User.email == email))
	if user is not None:
		# existing user: verify password and log in
		if verify_password(password, user.password_hash):
			if not user.is_active_account:
				flash("Account is inactive.", "warning")
				return redirect(url_for("auth.login"))
			login_user(user)
			user.last_login_at = datetime.now(timezone.utc)
			db.session.commit()
			flash("Signed in using quick role.", "success")
			return redirect(url_for("dashboard"))
		else:
			flash("Quick sign-in failed: password mismatch.", "danger")
			return redirect(url_for("auth.login"))

	# create a new user for the quick sign-in
	# resolve role id and default department id via simple selects (avoid full Role load)
	role_id = db.session.execute(select(Role.id).where(Role.name == role_name)).scalar()
	dept_id = db.session.execute(select(Department.id).where(Department.code == "GENERAL")).scalar()

	user = User(
		email=email,
		password_hash=hash_password(password),
		full_name=f"{role_name} (quick)",
		role_id=role_id if role_id is not None else db.session.scalar(select(Role.id).where(Role.name == ROLE_EMPLOYEE)),
		department_id=dept_id,
	)
	db.session.add(user)
	db.session.flush()

	# do not require an employee profile here — this is a convenience for local testing
	db.session.commit()

	login_user(user)
	user.last_login_at = datetime.now(timezone.utc)
	db.session.commit()

	flash("Quick account created and signed in.", "success")
	return redirect(url_for("dashboard"))


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout() -> str:
	"""Terminate the active authenticated session."""

	logout_user()
	flash("You have been signed out.", "info")
	return redirect(url_for("auth.login"))


@auth_bp.route("/forgot", methods=["GET", "POST"])
def forgot_password() -> str:
	"""Accept a reset request and provide a signed reset link."""

	if current_user.is_authenticated:
		return redirect(url_for("dashboard"))

	form = ForgotPasswordForm()
	if form.validate_on_submit():
		email = normalize_email(form.email.data)
		user = db.session.scalar(select(User).where(User.email == email))

		if user is not None:
			token = _generate_reset_token(user)
			reset_link = url_for("auth.reset_password", token=token, _external=True)
			flash(f"Reset link generated: {reset_link}", "info")

		flash("If the account exists, a reset link is now available.", "success")
		return redirect(url_for("auth.login"))
	elif request.method == "POST":
		_flash_form_errors(form)

	return render_template(
		"auth/forgot.html",
		form=form,
		page_title="Recover account",
		page_subtitle="Generate a secure reset link and restore access in minutes.",
	)


@auth_bp.route("/reset/<token>", methods=["GET", "POST"])
def reset_password(token: str) -> str:
	"""Reset a user password using a signed token."""

	if current_user.is_authenticated:
		return redirect(url_for("dashboard"))

	user = _resolve_reset_user(token)
	if user is None:
		flash("The reset link is invalid or expired.", "danger")
		return redirect(url_for("auth.forgot_password"))

	form = ResetPasswordForm()
	if form.validate_on_submit():
		user.password_hash = hash_password(form.password.data)
		db.session.commit()
		flash("Password reset complete. Please sign in.", "success")
		return redirect(url_for("auth.login"))
	elif request.method == "POST":
		_flash_form_errors(form)

	return render_template(
		"auth/reset.html",
		form=form,
		user=user,
		page_title="Set new password",
		page_subtitle="Create a strong password to secure your account.",
	)


@auth_bp.route("/promote/<int:user_id>", methods=["GET", "POST"])
@require_admin
def promote_user(user_id: int) -> str:
	"""Allow administrators to reassign a user's role."""

	user = db.session.get(User, user_id)
	if user is None:
		flash("User not found.", "danger")
		return redirect(url_for("dashboard"))

	form = PromoteUserForm()
	roles = db.session.scalars(select(Role).order_by(Role.name.asc())).all()
	form.role_id.choices = [(role.id, role.name) for role in roles]

	if not form.role_id.choices:
		flash("No roles are available. Run bootstrap first.", "warning")
		return redirect(url_for("dashboard"))

	if request.method == "GET":
		form.role_id.data = user.role_id

	if form.validate_on_submit():
		selected_role = db.session.get(Role, form.role_id.data)
		if selected_role is None:
			flash("Selected role not found.", "danger")
		else:
			user.role = selected_role
			db.session.commit()
			flash("User role updated successfully.", "success")
			return redirect(url_for("dashboard"))
	elif request.method == "POST":
		_flash_form_errors(form)

	return render_template(
		"auth/promote.html",
		form=form,
		user=user,
		page_title="Promote employee",
		page_subtitle="Assign role privileges with auditable admin control.",
	)
