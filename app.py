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


def build_dashboard_metrics() -> list[DashboardMetric]:
    """Return the KPI cards for the current enterprise snapshot.

    In the next files this data will be sourced from SQLAlchemy models and
    PostgreSQL queries. For now it is deterministic demo data that keeps the
    UI interactive and the app runnable.
    """

    return [
        DashboardMetric("Assets Available", "1,284", "+8.2%", "fa-boxes-stacked", "primary"),
        DashboardMetric("Assets Allocated", "932", "+4.1%", "fa-sitemap", "success"),
        DashboardMetric("Maintenance Today", "17", "+2", "fa-screwdriver-wrench", "warning"),
        DashboardMetric("Upcoming Returns", "48", "Due in 7 days", "fa-clock-rotate-left", "info"),
        DashboardMetric("Pending Transfers", "23", "Requires approval", "fa-right-left", "danger"),
        DashboardMetric("Bookings", "61", "12 active now", "fa-calendar-check", "secondary"),
    ]


def build_recent_tasks() -> list[DashboardTask]:
    """Return the recent activity and workflow queue shown on the dashboard."""

    return [
        DashboardTask("Laptop allocation", "Waiting for department head approval", "Pending"),
        DashboardTask("Printer maintenance", "Assigned to facilities technician", "In Progress"),
        DashboardTask("Transfer request", "Marketing to Finance", "Review"),
        DashboardTask("Quarterly audit", "Cycle scheduled for next Monday", "Planned"),
    ]


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

        return render_template("dashboard.html", metrics=metrics, tasks=tasks)

    @app.route("/health")
    def health_check() -> tuple[dict[str, str], int]:
        """Expose a lightweight health endpoint for deployment platforms."""

        return {"status": "ok", "service": "assetflow"}, 200

    return app
app = create_app()


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=os.getenv("FLASK_DEBUG", "0") == "1")