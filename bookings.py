"""Resource booking blueprint for AssetFlow.

This module introduces the first scheduling workflow with overlap validation for
asset reservations. It gives the application a practical booking surface while
remaining small enough for hackathon delivery.
"""

from __future__ import annotations

from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user
from flask_wtf import FlaskForm
from sqlalchemy import select
from wtforms import DateTimeLocalField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional

from extensions import db
from models import Asset, Booking
from security import ROLE_ADMIN, ROLE_ASSET_MANAGER, ROLE_DEPARTMENT_HEAD, ROLE_EMPLOYEE, require_roles


bookings_bp = Blueprint("bookings", __name__, url_prefix="/bookings")


class BookingForm(FlaskForm):
    """Collect the information required to reserve an asset."""

    asset_id = SelectField("Asset", coerce=int, validators=[DataRequired()])
    start_at = DateTimeLocalField("Start time", format="%Y-%m-%dT%H:%M", validators=[DataRequired()])
    end_at = DateTimeLocalField("End time", format="%Y-%m-%dT%H:%M", validators=[DataRequired()])
    purpose = StringField("Purpose", validators=[DataRequired(), Length(max=255)])
    notes = TextAreaField("Notes", validators=[Optional(), Length(max=5000)])
    submit = SubmitField("Create booking")


def _build_asset_choices() -> list[tuple[int, str]]:
    """Return the assets available for reservation."""

    assets = db.session.scalars(select(Asset).order_by(Asset.asset_tag.asc())).all()
    return [(asset.id, f"{asset.asset_tag} - {asset.name}") for asset in assets]


def _booking_has_overlap(asset_id: int, start_at: datetime, end_at: datetime) -> bool:
    """Check for an overlapping active booking on the same asset."""

    existing_bookings = db.session.scalars(
        select(Booking).where(Booking.asset_id == asset_id, Booking.status != "cancelled")
    ).all()
    for booking in existing_bookings:
        if booking.start_at < end_at and start_at < booking.end_at:
            return True
    return False


@bookings_bp.route("/", methods=["GET"])
@require_roles(ROLE_ADMIN, ROLE_ASSET_MANAGER, ROLE_DEPARTMENT_HEAD, ROLE_EMPLOYEE)
def booking_index() -> str:
    """Render the current booking queue and history."""

    bookings = db.session.scalars(select(Booking).order_by(Booking.start_at.desc())).all()
    upcoming_bookings = sum(1 for booking in bookings if booking.status in {"requested", "approved"})
    ongoing_bookings = sum(1 for booking in bookings if booking.status == "ongoing")
    completed_bookings = sum(1 for booking in bookings if booking.status == "completed")

    return render_template(
        "bookings/index.html",
        bookings=bookings,
        upcoming_bookings=upcoming_bookings,
        ongoing_bookings=ongoing_bookings,
        completed_bookings=completed_bookings,
    )


@bookings_bp.route("/new", methods=["GET", "POST"])
@require_roles(ROLE_ADMIN, ROLE_ASSET_MANAGER, ROLE_DEPARTMENT_HEAD, ROLE_EMPLOYEE)
def booking_create() -> str:
    """Create a reservation after validating the requested time window."""

    form = BookingForm()
    form.asset_id.choices = _build_asset_choices()

    if not form.asset_id.choices:
        flash("Register at least one asset before creating bookings.", "warning")

    if form.validate_on_submit():
        if form.end_at.data <= form.start_at.data:
            flash("The booking end time must be after the start time.", "warning")
        elif _booking_has_overlap(form.asset_id.data, form.start_at.data, form.end_at.data):
            flash("That asset already has a booking in the selected time window.", "warning")
        else:
            asset = db.session.get(Asset, form.asset_id.data)
            if asset is None:
                flash("The selected asset was not found.", "danger")
            else:
                booking = Booking(
                    asset=asset,
                    booked_by_user_id=current_user.id,
                    start_at=form.start_at.data,
                    end_at=form.end_at.data,
                    purpose=form.purpose.data.strip(),
                    notes=form.notes.data.strip() or None,
                )
                db.session.add(booking)
                db.session.commit()
                flash("Booking created successfully.", "success")
                return redirect(url_for("bookings.booking_index"))

    return render_template("bookings/form.html", form=form)
