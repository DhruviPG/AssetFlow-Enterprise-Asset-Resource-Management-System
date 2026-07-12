"""Notification center for AssetFlow.

This module exposes the in-app notification inbox and a read action. It is a
simple but useful bridge toward email and real-time notification delivery.
"""

from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user
from flask_wtf import FlaskForm
from sqlalchemy import select
from wtforms import SubmitField

from extensions import db
from models import Notification
from security import ROLE_ADMIN, ROLE_ASSET_MANAGER, ROLE_DEPARTMENT_HEAD, ROLE_EMPLOYEE, require_roles


notifications_bp = Blueprint("notifications", __name__, url_prefix="/notifications")


class NotificationReadForm(FlaskForm):
    """Allow a user to mark a notification as read."""

    submit = SubmitField("Mark as read")


@notifications_bp.route("/", methods=["GET"])
@require_roles(ROLE_ADMIN, ROLE_ASSET_MANAGER, ROLE_DEPARTMENT_HEAD, ROLE_EMPLOYEE)
def notification_index() -> str:
    """Render the current user's notification inbox."""

    notifications = db.session.scalars(
        select(Notification)
        .where(Notification.recipient_user_id == current_user.id)
        .order_by(Notification.created_at.desc())
    ).all()
    unread_count = sum(1 for notification in notifications if not notification.is_read)

    return render_template(
        "notifications/index.html",
        notifications=notifications,
        unread_count=unread_count,
    )


@notifications_bp.route("/<int:notification_id>/read", methods=["POST"])
@require_roles(ROLE_ADMIN, ROLE_ASSET_MANAGER, ROLE_DEPARTMENT_HEAD, ROLE_EMPLOYEE)
def notification_mark_read(notification_id: int) -> str:
    """Mark a notification as read for the current user."""

    notification = db.session.get(Notification, notification_id)
    if notification is None or notification.recipient_user_id != current_user.id:
        flash("Notification not found.", "danger")
        return redirect(url_for("notifications.notification_index"))

    notification.is_read = True
    notification.read_at = datetime.now(timezone.utc)
    db.session.commit()
    flash("Notification marked as read.", "success")
    return redirect(url_for("notifications.notification_index"))
