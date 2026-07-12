"""Transfer workflow blueprint for AssetFlow.

This module lets employees request transfers and gives operational staff a queue
for approving or rejecting them. It is the natural next step after asset
allocation because it keeps ownership changes auditable and role-controlled.
"""

from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user
from flask_wtf import FlaskForm
from sqlalchemy import select
from wtforms import SelectField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional

from extensions import db
from models import Asset, TransferRequest, User
from security import ROLE_ADMIN, ROLE_ASSET_MANAGER, ROLE_DEPARTMENT_HEAD, ROLE_EMPLOYEE, require_roles


transfers_bp = Blueprint("transfers", __name__, url_prefix="/transfers")


class TransferRequestForm(FlaskForm):
    """Collect the information required to open a transfer request."""

    asset_id = SelectField("Asset", coerce=int, validators=[DataRequired()])
    target_user_id = SelectField("Target user", coerce=int, validators=[Optional()])
    reason = TextAreaField("Reason", validators=[DataRequired(), Length(max=255)])
    submit = SubmitField("Submit request")


class TransferDecisionForm(FlaskForm):
    """Capture an approval decision for a transfer request."""

    submit_approve = SubmitField("Approve")
    submit_reject = SubmitField("Reject")


def _build_asset_choices() -> list[tuple[int, str]]:
    """Return assets that can be selected for a transfer request."""

    assets = db.session.scalars(select(Asset).order_by(Asset.asset_tag.asc())).all()
    return [(asset.id, f"{asset.asset_tag} - {asset.name}") for asset in assets]


def _build_user_choices() -> list[tuple[int, str]]:
    """Return users who can receive a transferred asset."""

    users = db.session.scalars(select(User).order_by(User.full_name.asc())).all()
    return [(user.id, f"{user.full_name} ({user.email})") for user in users]


@transfers_bp.route("/", methods=["GET"])
@require_roles(ROLE_ADMIN, ROLE_ASSET_MANAGER, ROLE_DEPARTMENT_HEAD, ROLE_EMPLOYEE)
def transfer_index() -> str:
    """Render the transfer queue and request history."""

    requests = db.session.scalars(select(TransferRequest).order_by(TransferRequest.requested_at.desc())).all()
    pending_requests = sum(1 for transfer_request in requests if transfer_request.status == "pending")
    approved_requests = sum(1 for transfer_request in requests if transfer_request.status == "approved")
    rejected_requests = sum(1 for transfer_request in requests if transfer_request.status == "rejected")

    return render_template(
        "transfers/index.html",
        requests=requests,
        pending_requests=pending_requests,
        approved_requests=approved_requests,
        rejected_requests=rejected_requests,
    )


@transfers_bp.route("/new", methods=["GET", "POST"])
@require_roles(ROLE_ADMIN, ROLE_ASSET_MANAGER, ROLE_DEPARTMENT_HEAD, ROLE_EMPLOYEE)
def transfer_create() -> str:
    """Create a new transfer request for a currently tracked asset."""

    form = TransferRequestForm()
    form.asset_id.choices = _build_asset_choices()
    form.target_user_id.choices = [(0, "Select a user")] + _build_user_choices()

    if form.validate_on_submit():
        target_user_id = form.target_user_id.data or None
        transfer_request = TransferRequest(
            asset_id=form.asset_id.data,
            requested_by_user_id=current_user.id,
            source_user_id=current_user.id,
            target_user_id=target_user_id,
            reason=form.reason.data.strip(),
        )
        db.session.add(transfer_request)
        db.session.commit()
        flash("Transfer request submitted successfully.", "success")
        return redirect(url_for("transfers.transfer_index"))

    return render_template("transfers/form.html", form=form)


@transfers_bp.route("/<int:transfer_request_id>/decision", methods=["GET", "POST"])
@require_roles(ROLE_ADMIN, ROLE_ASSET_MANAGER, ROLE_DEPARTMENT_HEAD)
def transfer_decision(transfer_request_id: int) -> str:
    """Approve or reject a transfer request."""

    transfer_request = db.session.get(TransferRequest, transfer_request_id)
    if transfer_request is None:
        flash("Transfer request not found.", "danger")
        return redirect(url_for("transfers.transfer_index"))

    form = TransferDecisionForm()
    if form.validate_on_submit():
        if form.submit_approve.data:
            transfer_request.status = "approved"
            transfer_request.approved_by_user_id = current_user.id
            transfer_request.decided_at = datetime.now(timezone.utc)
            flash("Transfer request approved.", "success")
        else:
            transfer_request.status = "rejected"
            transfer_request.approved_by_user_id = current_user.id
            transfer_request.decided_at = datetime.now(timezone.utc)
            flash("Transfer request rejected.", "warning")
        db.session.commit()
        return redirect(url_for("transfers.transfer_index"))

    return render_template("transfers/decision.html", transfer_request=transfer_request, form=form)
