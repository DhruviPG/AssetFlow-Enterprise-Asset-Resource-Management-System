"""Audit workflow blueprint for AssetFlow.

This module provides the first audit cycle views so administrators can create
cycles and review audit items. It gives the ERP an essential control function:
verifying whether the physical inventory matches the system record.
"""

from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user
from flask_wtf import FlaskForm
from sqlalchemy import select
from wtforms import DateTimeLocalField, SelectField, SubmitField, TextAreaField, StringField
from wtforms.validators import DataRequired, Length, Optional

from extensions import db
from models import Asset, AuditCycle, AuditItem
from security import ROLE_ADMIN, ROLE_ASSET_MANAGER, ROLE_DEPARTMENT_HEAD, ROLE_EMPLOYEE, require_roles


audit_bp = Blueprint("audit", __name__, url_prefix="/audit")


class AuditCycleForm(FlaskForm):
    """Collect the information needed to open an audit cycle."""

    name = StringField("Name", validators=[DataRequired(), Length(max=150)])
    description = TextAreaField("Description", validators=[Optional(), Length(max=5000)])
    scheduled_start_at = DateTimeLocalField("Start", format="%Y-%m-%dT%H:%M", validators=[Optional()])
    scheduled_end_at = DateTimeLocalField("End", format="%Y-%m-%dT%H:%M", validators=[Optional()])
    submit = SubmitField("Create cycle")


class AuditItemForm(FlaskForm):
    """Capture the result of auditing a single asset."""

    asset_id = SelectField("Asset", coerce=int, validators=[DataRequired()])
    status = SelectField(
        "Status",
        choices=[
            ("present", "Present"),
            ("missing", "Missing"),
            ("damaged", "Damaged"),
            ("needs_review", "Needs review"),
        ],
        validators=[DataRequired()],
    )
    condition_found = SelectField(
        "Condition found",
        choices=[
            ("excellent", "Excellent"),
            ("good", "Good"),
            ("fair", "Fair"),
            ("poor", "Poor"),
        ],
        validators=[DataRequired()],
    )
    remarks = TextAreaField("Remarks", validators=[Optional(), Length(max=5000)])
    submit = SubmitField("Save item")


class CloseAuditForm(FlaskForm):
    """Close an open audit cycle after review."""

    submit = SubmitField("Close audit")


def _build_asset_choices() -> list[tuple[int, str]]:
    """Return assets that can be attached to audit items."""

    assets = db.session.scalars(select(Asset).order_by(Asset.asset_tag.asc())).all()
    return [(asset.id, f"{asset.asset_tag} - {asset.name}") for asset in assets]


@audit_bp.route("/", methods=["GET"])
@require_roles(ROLE_ADMIN, ROLE_ASSET_MANAGER, ROLE_DEPARTMENT_HEAD, ROLE_EMPLOYEE)
def audit_index() -> str:
    """Show audit cycles and summary metrics."""

    cycles = db.session.scalars(select(AuditCycle).order_by(AuditCycle.created_at.desc())).all()
    open_cycles = sum(1 for cycle in cycles if cycle.status == "open")
    closed_cycles = sum(1 for cycle in cycles if cycle.status == "closed")
    in_progress_cycles = sum(1 for cycle in cycles if cycle.status == "in_progress")

    return render_template(
        "audit/index.html",
        cycles=cycles,
        open_cycles=open_cycles,
        closed_cycles=closed_cycles,
        in_progress_cycles=in_progress_cycles,
    )


@audit_bp.route("/cycles/new", methods=["GET", "POST"])
@require_roles(ROLE_ADMIN, ROLE_ASSET_MANAGER, ROLE_DEPARTMENT_HEAD)
def audit_cycle_create() -> str:
    """Open a new audit cycle."""

    form = AuditCycleForm()
    if form.validate_on_submit():
        cycle = AuditCycle(
            name=form.name.data.strip(),
            description=form.description.data.strip() or None,
            scheduled_start_at=form.scheduled_start_at.data,
            scheduled_end_at=form.scheduled_end_at.data,
            created_by_user_id=current_user.id,
        )
        db.session.add(cycle)
        db.session.commit()
        flash("Audit cycle created successfully.", "success")
        return redirect(url_for("audit.audit_index"))

    return render_template("audit/cycle_form.html", form=form)


@audit_bp.route("/cycles/<int:cycle_id>/items/new", methods=["GET", "POST"])
@require_roles(ROLE_ADMIN, ROLE_ASSET_MANAGER, ROLE_DEPARTMENT_HEAD)
def audit_item_create(cycle_id: int) -> str:
    """Record a single asset item inside an audit cycle."""

    cycle = db.session.get(AuditCycle, cycle_id)
    if cycle is None:
        flash("Audit cycle not found.", "danger")
        return redirect(url_for("audit.audit_index"))

    form = AuditItemForm()
    form.asset_id.choices = _build_asset_choices()

    if form.validate_on_submit():
        item = AuditItem(
            audit_cycle_id=cycle.id,
            asset_id=form.asset_id.data,
            audited_by_user_id=current_user.id,
            status=form.status.data,
            condition_found=form.condition_found.data,
            remarks=form.remarks.data.strip() or None,
        )
        db.session.add(item)
        db.session.commit()
        flash("Audit item saved.", "success")
        return redirect(url_for("audit.audit_index"))

    return render_template("audit/item_form.html", form=form, cycle=cycle)


@audit_bp.route("/cycles/<int:cycle_id>/close", methods=["POST"])
@require_roles(ROLE_ADMIN, ROLE_ASSET_MANAGER, ROLE_DEPARTMENT_HEAD)
def audit_cycle_close(cycle_id: int) -> str:
    """Close an audit cycle once review is complete."""

    cycle = db.session.get(AuditCycle, cycle_id)
    if cycle is None:
        flash("Audit cycle not found.", "danger")
        return redirect(url_for("audit.audit_index"))

    cycle.status = "closed"
    cycle.closed_by_user_id = current_user.id
    cycle.closed_at = datetime.now(timezone.utc)
    db.session.commit()
    flash("Audit cycle closed.", "success")
    return redirect(url_for("audit.audit_index"))
