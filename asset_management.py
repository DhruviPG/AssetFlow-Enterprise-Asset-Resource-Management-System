"""Asset management blueprint for AssetFlow.

This module provides the first operational asset workflow: browsing assets,
registering a new asset, and exposing a lightweight JSON endpoint for API-style
consumers. It uses the shared role guards so only asset-oriented staff can
change inventory records.
"""

from __future__ import annotations

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_wtf import FlaskForm
from sqlalchemy import select
from wtforms import IntegerField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional, NumberRange

from extensions import db
from models import Asset, AssetCategory
from security import ROLE_ADMIN, ROLE_ASSET_MANAGER, ROLE_DEPARTMENT_HEAD, ROLE_EMPLOYEE, require_roles


assets_bp = Blueprint("assets", __name__, url_prefix="/assets")


class AssetForm(FlaskForm):
    """Collect the details required to register a new tracked asset."""

    asset_tag = StringField("Asset tag", validators=[DataRequired(), Length(max=60)])
    name = StringField("Asset name", validators=[DataRequired(), Length(max=150)])
    category_id = SelectField("Category", coerce=int, validators=[DataRequired()])
    serial_number = StringField("Serial number", validators=[Optional(), Length(max=120)])
    barcode_value = StringField("Barcode value", validators=[Optional(), Length(max=120)])
    qr_code_value = StringField("QR code value", validators=[Optional(), Length(max=120)])
    current_value = IntegerField("Current value", validators=[DataRequired(), NumberRange(min=0)])
    status = SelectField(
        "Status",
        choices=[
            ("available", "Available"),
            ("allocated", "Allocated"),
            ("reserved", "Reserved"),
            ("maintenance", "Maintenance"),
            ("lost", "Lost"),
            ("disposed", "Disposed"),
            ("retired", "Retired"),
        ],
        validators=[DataRequired()],
    )
    condition = SelectField(
        "Condition",
        choices=[
            ("excellent", "Excellent"),
            ("good", "Good"),
            ("fair", "Fair"),
            ("poor", "Poor"),
        ],
        validators=[DataRequired()],
    )
    description = TextAreaField("Description", validators=[Optional(), Length(max=5000)])
    submit = SubmitField("Register asset")


def _ensure_default_category() -> AssetCategory:
    """Create a fallback category when the catalog has not been initialized yet."""

    category = db.session.scalar(select(AssetCategory).where(AssetCategory.code == "GENERAL"))
    if category is None:
        category = AssetCategory(
            code="GENERAL",
            name="General Assets",
            description="Default category used until the catalog is curated.",
        )
        db.session.add(category)
        db.session.flush()
    return category


def _build_category_choices() -> list[tuple[int, str]]:
    """Return category options for the asset registration form."""

    categories = db.session.scalars(select(AssetCategory).order_by(AssetCategory.name.asc())).all()
    if not categories:
        categories = [_ensure_default_category()]
    return [(category.id, f"{category.name} ({category.code})") for category in categories]


@assets_bp.route("/", methods=["GET"])
@require_roles(ROLE_ADMIN, ROLE_ASSET_MANAGER, ROLE_DEPARTMENT_HEAD, ROLE_EMPLOYEE)
def asset_index() -> str:
    """Render the inventory list with simple operational metrics."""

    assets = db.session.scalars(select(Asset).order_by(Asset.created_at.desc())).all()
    total_assets = len(assets)
    available_assets = sum(1 for asset in assets if asset.status == "available")
    allocated_assets = sum(1 for asset in assets if asset.status == "allocated")
    maintenance_assets = sum(1 for asset in assets if asset.status == "maintenance")

    return render_template(
        "assets/index.html",
        assets=assets,
        total_assets=total_assets,
        available_assets=available_assets,
        allocated_assets=allocated_assets,
        maintenance_assets=maintenance_assets,
    )


@assets_bp.route("/new", methods=["GET", "POST"])
@require_roles(ROLE_ADMIN, ROLE_ASSET_MANAGER, ROLE_DEPARTMENT_HEAD, ROLE_EMPLOYEE)
def register_asset() -> str:
    """Create a new asset record and place it into the normalized catalog."""

    form = AssetForm()
    form.category_id.choices = _build_category_choices()

    if form.validate_on_submit():
        duplicate_asset = db.session.scalar(select(Asset).where(Asset.asset_tag == form.asset_tag.data.strip()))
        if duplicate_asset is not None:
            flash("An asset with that tag already exists.", "warning")
        else:
            selected_category = db.session.get(AssetCategory, form.category_id.data)
            if selected_category is None:
                selected_category = _ensure_default_category()

            asset = Asset(
                asset_tag=form.asset_tag.data.strip(),
                name=form.name.data.strip(),
                description=form.description.data.strip() or None,
                serial_number=form.serial_number.data.strip() or None,
                barcode_value=form.barcode_value.data.strip() or None,
                qr_code_value=form.qr_code_value.data.strip() or None,
                current_value=form.current_value.data,
                status=form.status.data,
                condition=form.condition.data,
                category=selected_category,
            )
            db.session.add(asset)
            db.session.commit()
            flash("Asset registered successfully.", "success")
            return redirect(url_for("assets.asset_index"))

    return render_template("assets/form.html", form=form, mode="register")


@assets_bp.route("/api", methods=["GET"])
@require_roles(ROLE_ADMIN, ROLE_ASSET_MANAGER, ROLE_DEPARTMENT_HEAD)
def asset_api() -> tuple[dict[str, object], int]:
    """Return a JSON payload for lightweight integrations and frontend widgets."""

    assets = db.session.scalars(select(Asset).order_by(Asset.created_at.desc())).all()
    payload = [
        {
            "asset_tag": asset.asset_tag,
            "name": asset.name,
            "status": asset.status,
            "condition": asset.condition,
            "category": asset.category.name,
            "current_value": asset.current_value,
        }
        for asset in assets
    ]
    return jsonify({"count": len(payload), "results": payload}), 200
