"""Reporting views for AssetFlow.

This module provides a compact reporting dashboard for hackathon delivery.
It does not attempt to replace a full BI stack, but it gives the system a clear
place for summary views, export entrypoints, and filterable reporting surfaces.
"""

from __future__ import annotations

from flask import Blueprint, render_template

from security import ROLE_ADMIN, ROLE_ASSET_MANAGER, ROLE_DEPARTMENT_HEAD, ROLE_EMPLOYEE, require_roles


reports_bp = Blueprint("reports", __name__, url_prefix="/reports")


@reports_bp.route("/", methods=["GET"])
@require_roles(ROLE_ADMIN, ROLE_ASSET_MANAGER, ROLE_DEPARTMENT_HEAD, ROLE_EMPLOYEE)
def reports_index() -> str:
    """Render the executive reporting landing page."""

    return render_template("reports/index.html")
