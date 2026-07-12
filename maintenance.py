"""Maintenance workflow blueprint for AssetFlow.

This module lets users raise maintenance requests against existing assets and
provides a management list for operations staff. It is intentionally compact so
we can deliver a working service workflow before adding technician assignment
and richer lifecycle automation.
"""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user
from flask_wtf import FlaskForm
from sqlalchemy import select
from wtforms import SelectField, SubmitField, TextAreaField, StringField
from wtforms.validators import DataRequired, Length, Optional

from extensions import db
from models import Asset, MaintenanceRequest
from security import ROLE_ADMIN, ROLE_ASSET_MANAGER, ROLE_DEPARTMENT_HEAD, ROLE_EMPLOYEE, require_roles


maintenance_bp = Blueprint("maintenance", __name__, url_prefix="/maintenance")


class MaintenanceRequestForm(FlaskForm):
    """Collect the information needed to open a maintenance ticket."""

    asset_id = SelectField("Asset", coerce=int, validators=[DataRequired()])
    priority = SelectField(
        "Priority",
        choices=[
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
            ("critical", "Critical"),
        ],
        validators=[DataRequired()],
    )
    issue_summary = StringField("Issue summary", validators=[DataRequired(), Length(max=200)])
    issue_details = TextAreaField("Issue details", validators=[Optional(), Length(max=5000)])
    submit = SubmitField("Submit request")


def _build_asset_choices() -> list[tuple[int, str]]:
    """Return the selectable assets for the request form."""

    assets = db.session.scalars(select(Asset).order_by(Asset.asset_tag.asc())).all()
    return [(asset.id, f"{asset.asset_tag} - {asset.name}") for asset in assets]


@maintenance_bp.route("/", methods=["GET"])
@require_roles(ROLE_ADMIN, ROLE_ASSET_MANAGER, ROLE_DEPARTMENT_HEAD, ROLE_EMPLOYEE)
def maintenance_index() -> str:
    """Render a service queue showing all maintenance requests."""

    requests = db.session.scalars(select(MaintenanceRequest).order_by(MaintenanceRequest.requested_at.desc())).all()
    open_requests = sum(1 for request in requests if request.status == "open")
    in_progress_requests = sum(1 for request in requests if request.status == "in_progress")
    resolved_requests = sum(1 for request in requests if request.status == "resolved")

    return render_template(
        "maintenance/index.html",
        requests=requests,
        open_requests=open_requests,
        in_progress_requests=in_progress_requests,
        resolved_requests=resolved_requests,
    )


@maintenance_bp.route("/new", methods=["GET", "POST"])
@require_roles(ROLE_ADMIN, ROLE_ASSET_MANAGER, ROLE_DEPARTMENT_HEAD, ROLE_EMPLOYEE)
def maintenance_create() -> str:
    """Raise a new maintenance request for an asset."""

    form = MaintenanceRequestForm()
    form.asset_id.choices = _build_asset_choices()

    if not form.asset_id.choices:
        flash("Register at least one asset before creating a maintenance request.", "warning")

    if form.validate_on_submit():
        asset = db.session.get(Asset, form.asset_id.data)
        if asset is None:
            flash("The selected asset was not found.", "danger")
        else:
            maintenance_request = MaintenanceRequest(
                asset=asset,
                requested_by_user_id=current_user.id,
                priority=form.priority.data,
                issue_summary=form.issue_summary.data.strip(),
                issue_details=form.issue_details.data.strip() or None,
            )
            db.session.add(maintenance_request)
            db.session.flush()
            db.session.commit()
            flash("Maintenance request submitted successfully.", "success")
            return redirect(url_for("maintenance.maintenance_index"))

    return render_template("maintenance/form.html", form=form)
