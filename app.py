"""AssetFlow application entrypoint.

This first file establishes a runnable Flask application with a polished
ERP-style dashboard shell. It is intentionally self-contained so the project
can start as a working MVP before the codebase is split into blueprints,
services, models, templates, and static assets.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone

from flask import Flask, flash, redirect, render_template, request, url_for
from flask_wtf.csrf import CSRFError
from sqlalchemy import select

from config import get_config
from extensions import csrf, db, login_manager


@dataclass(frozen=True)
class DashboardMetric:
    """Represents a single KPI card shown on the dashboard."""

    label: str
    value: str
    delta: str
    icon: str
    tone: str


@dataclass(frozen=True)
class DashboardTask:
    """Represents a compact operational item on the dashboard."""

    title: str
    subtitle: str
    badge: str


@dataclass(frozen=True)
class DashboardActivity:
    """Represents a recent activity row shown on the dashboard."""

    action: str
    module: str
    status: str
    time_label: str


def build_dashboard_metrics() -> list[DashboardMetric]:
    """Return live KPI cards sourced from the database."""

    from models import Asset, AuditCycle, Booking, MaintenanceRequest, Notification, TransferRequest

    assets = db.session.scalars(select(Asset)).all()
    bookings = db.session.scalars(select(Booking)).all()
    maintenance_requests = db.session.scalars(select(MaintenanceRequest)).all()
    transfer_requests = db.session.scalars(select(TransferRequest)).all()
    audit_cycles = db.session.scalars(select(AuditCycle)).all()
    unread_notifications = db.session.scalars(select(Notification).where(Notification.is_read.is_(False))).all()

    available_assets = sum(1 for asset in assets if asset.status == "available")
    allocated_assets = sum(1 for asset in assets if asset.status == "allocated")
    open_maintenance = sum(1 for request in maintenance_requests if request.status == "open")
    pending_transfers = sum(1 for request in transfer_requests if request.status == "pending")
    open_audits = sum(1 for cycle in audit_cycles if cycle.status == "open")
    active_bookings = sum(1 for booking in bookings if booking.status in {"requested", "approved", "ongoing"})

    return [
        DashboardMetric("Assets Available", str(available_assets), f"of {len(assets)} total", "fa-boxes-stacked", "primary"),
        DashboardMetric("Assets Allocated", str(allocated_assets), "currently issued", "fa-sitemap", "success"),
        DashboardMetric("Open Maintenance", str(open_maintenance), "needs attention", "fa-screwdriver-wrench", "warning"),
        DashboardMetric("Open Audits", str(open_audits), "verification cycles", "fa-clipboard-check", "info"),
        DashboardMetric("Pending Transfers", str(pending_transfers), "awaiting approval", "fa-right-left", "danger"),
        DashboardMetric("Bookings", str(active_bookings), f"{len(unread_notifications)} unread alerts", "fa-calendar-check", "secondary"),
    ]


def build_recent_tasks() -> list[DashboardTask]:
    """Return the recent workflow queue shown on the dashboard."""

    from models import Asset, AuditCycle, Booking, MaintenanceRequest, TransferRequest

    recent_assets = db.session.scalars(select(Asset).order_by(Asset.created_at.desc()).limit(1)).all()
    recent_bookings = db.session.scalars(select(Booking).order_by(Booking.created_at.desc()).limit(1)).all()
    recent_maintenance = db.session.scalars(select(MaintenanceRequest).order_by(MaintenanceRequest.requested_at.desc()).limit(1)).all()
    recent_transfers = db.session.scalars(select(TransferRequest).order_by(TransferRequest.requested_at.desc()).limit(1)).all()
    recent_audits = db.session.scalars(select(AuditCycle).order_by(AuditCycle.created_at.desc()).limit(1)).all()

    tasks: list[DashboardTask] = []

    if recent_assets:
        asset = recent_assets[0]
        tasks.append(DashboardTask(asset.asset_tag, f"New asset record: {asset.name}", asset.status.title()))
    if recent_bookings:
        booking = recent_bookings[0]
        tasks.append(DashboardTask(booking.purpose, f"Booking for {booking.asset.asset_tag}", booking.status.title()))
    if recent_maintenance:
        request = recent_maintenance[0]
        tasks.append(DashboardTask(request.issue_summary, f"Maintenance on {request.asset.asset_tag}", request.status.title()))
    if recent_transfers:
        request = recent_transfers[0]
        tasks.append(DashboardTask(request.reason, f"Transfer request for {request.asset.asset_tag}", request.status.title()))
    if recent_audits:
        cycle = recent_audits[0]
        tasks.append(DashboardTask(cycle.name, "Latest audit cycle", cycle.status.title()))

    if not tasks:
        tasks.append(DashboardTask("No activity yet", "Create assets, bookings, or requests to populate this queue.", "Idle"))

    return tasks[:4]


def build_recent_activity() -> list[DashboardActivity]:
    """Return a merged feed of recent records from operational tables."""

    from models import Asset, AuditCycle, Booking, MaintenanceRequest, Notification, TransferRequest

    activity: list[DashboardActivity] = []

    for asset in db.session.scalars(select(Asset).order_by(Asset.created_at.desc()).limit(2)).all():
        activity.append(
            DashboardActivity(
                action=f"Registered asset {asset.asset_tag}",
                module="Assets",
                status=asset.status.title(),
                time_label=asset.created_at.strftime("%d %b %Y"),
            )
        )

    for request in db.session.scalars(select(MaintenanceRequest).order_by(MaintenanceRequest.requested_at.desc()).limit(2)).all():
        activity.append(
            DashboardActivity(
                action=request.issue_summary,
                module="Maintenance",
                status=request.status.title(),
                time_label=request.requested_at.strftime("%d %b %Y"),
            )
        )

    for request in db.session.scalars(select(TransferRequest).order_by(TransferRequest.requested_at.desc()).limit(2)).all():
        activity.append(
            DashboardActivity(
                action=request.reason,
                module="Transfers",
                status=request.status.title(),
                time_label=request.requested_at.strftime("%d %b %Y"),
            )
        )

    for booking in db.session.scalars(select(Booking).order_by(Booking.created_at.desc()).limit(2)).all():
        activity.append(
            DashboardActivity(
                action=booking.purpose,
                module="Bookings",
                status=booking.status.title(),
                time_label=booking.created_at.strftime("%d %b %Y"),
            )
        )

    for cycle in db.session.scalars(select(AuditCycle).order_by(AuditCycle.created_at.desc()).limit(2)).all():
        activity.append(
            DashboardActivity(
                action=cycle.name,
                module="Audit",
                status=cycle.status.title(),
                time_label=cycle.created_at.strftime("%d %b %Y"),
            )
        )

    for notification in db.session.scalars(select(Notification).order_by(Notification.created_at.desc()).limit(2)).all():
        activity.append(
            DashboardActivity(
                action=notification.title,
                module="Notifications",
                status=("Read" if notification.is_read else "Unread"),
                time_label=notification.created_at.strftime("%d %b %Y"),
            )
        )

    return activity[:6]


def build_recent_notifications() -> list[dict[str, str]]:
    """Return the latest notifications for the dashboard side panel."""

    from models import Notification

    notifications = db.session.scalars(select(Notification).order_by(Notification.created_at.desc()).limit(3)).all()
    return [
        {
            "title": notification.title,
            "message": notification.message,
            "category": notification.category,
            "status": "Read" if notification.is_read else "Unread",
        }
        for notification in notifications
    ]


def build_asset_status_chart() -> tuple[list[str], list[int]]:
    """Return the current asset status distribution for charting."""

    from models import Asset

    statuses = ["available", "allocated", "reserved", "maintenance", "lost", "disposed", "retired"]
    label_map = {
        "available": "Available",
        "allocated": "Allocated",
        "reserved": "Reserved",
        "maintenance": "Maintenance",
        "lost": "Lost",
        "disposed": "Disposed",
        "retired": "Retired",
    }

    assets = db.session.scalars(select(Asset)).all()
    counts = [sum(1 for asset in assets if asset.status == status) for status in statuses]
    labels = [label_map[status] for status in statuses]
    return labels, counts


def create_app() -> Flask:
    """Create and configure the Flask application instance."""

    app = Flask(__name__)
    app.config.from_object(get_config())
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please sign in to continue."

    import models  # noqa: F401
    from audit import audit_bp
    from auth import auth_bp
    from asset_management import assets_bp
    from bookings import bookings_bp
    from maintenance import maintenance_bp
    from notifications import notifications_bp
    from reports import reports_bp
    from transfer_workflow import transfers_bp

    app.register_blueprint(audit_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(assets_bp)
    app.register_blueprint(bookings_bp)
    app.register_blueprint(maintenance_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(transfers_bp)

    @app.errorhandler(CSRFError)
    def handle_csrf_error(error: CSRFError):
        """Redirect form submissions back to the originating page with a clear message."""

        flash(error.description or "Your form session expired. Please try again.", "warning")
        target = request.referrer or request.path or url_for("dashboard")
        return redirect(target)

    @app.context_processor
    def inject_global_navigation_state() -> dict[str, str]:
        """Provide shared values used by the base UI chrome."""

        return {
            "app_name": "AssetFlow",
            "app_tagline": "Enterprise Asset & Resource Management System",
            "current_year": str(datetime.now(timezone.utc).year),
        }

    @app.route("/")
    def dashboard() -> str:
        """Render the main executive dashboard.

        This initial view acts as the shell for the larger ERP experience and
        already demonstrates the layout patterns we will reuse across modules.
        """

        metrics = build_dashboard_metrics()
        tasks = build_recent_tasks()
        recent_activity = build_recent_activity()
        recent_notifications = build_recent_notifications()
        chart_labels, chart_values = build_asset_status_chart()

        return render_template(
            "dashboard.html",
            metrics=metrics,
            tasks=tasks,
            recent_activity=recent_activity,
            recent_notifications=recent_notifications,
            chart_labels=chart_labels,
            chart_values=chart_values,
        )

    @app.route("/health")
    def health_check() -> tuple[dict[str, str], int]:
        """Expose a lightweight health endpoint for deployment platforms."""

        return {"status": "ok", "service": "assetflow"}, 200

    return app
app = create_app()


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=os.getenv("FLASK_DEBUG", "0") == "1")