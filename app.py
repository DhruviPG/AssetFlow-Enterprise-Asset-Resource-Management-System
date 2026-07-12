"""AssetFlow application entrypoint.

This first file establishes a runnable Flask application with a polished
ERP-style dashboard shell. It is intentionally self-contained so the project
can start as a working MVP before the codebase is split into blueprints,
services, models, templates, and static assets.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime

from flask import Flask, render_template

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
    from auth import auth_bp
    from asset_management import assets_bp
    from bookings import bookings_bp
    from maintenance import maintenance_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(assets_bp)
    app.register_blueprint(bookings_bp)
    app.register_blueprint(maintenance_bp)

    @app.context_processor
    def inject_global_navigation_state() -> dict[str, str]:
        """Provide shared values used by the base UI chrome."""

        return {
            "app_name": "AssetFlow",
            "app_tagline": "Enterprise Asset & Resource Management System",
            "current_year": str(datetime.utcnow().year),
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


DASHBOARD_TEMPLATE = """
<!doctype html>
<html lang="en" data-theme="light">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ app_name }} | {{ app_tagline }}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
  <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css" rel="stylesheet">
  <style>
    :root {
      --bg: #f5f7fb;
      --panel: rgba(255, 255, 255, 0.88);
      --panel-solid: #ffffff;
      --text: #142033;
      --muted: #65758b;
      --border: rgba(20, 32, 51, 0.08);
      --shadow: 0 18px 50px rgba(15, 23, 42, 0.08);
      --accent: #0f62fe;
      --accent-2: #0ea5e9;
      --success: #16a34a;
      --warning: #f59e0b;
      --danger: #dc2626;
      --sidebar: #0b1324;
      --sidebar-soft: #121c32;
    }

    html[data-theme="dark"] {
      --bg: #07111f;
      --panel: rgba(13, 20, 34, 0.9);
      --panel-solid: #0d1422;
      --text: #eef4ff;
      --muted: #95a3bb;
      --border: rgba(255, 255, 255, 0.08);
      --shadow: 0 22px 60px rgba(0, 0, 0, 0.32);
    }

    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      min-height: 100vh;
      font-family: "Inter", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(15, 98, 254, 0.14), transparent 28%),
        radial-gradient(circle at top right, rgba(14, 165, 233, 0.12), transparent 24%),
        linear-gradient(180deg, var(--bg), var(--bg));
    }

    .app-shell {
      display: grid;
      grid-template-columns: 280px minmax(0, 1fr);
      min-height: 100vh;
    }

    .sidebar {
      background: linear-gradient(180deg, var(--sidebar), var(--sidebar-soft));
      color: #fff;
      padding: 1.5rem;
      position: sticky;
      top: 0;
      height: 100vh;
      border-right: 1px solid rgba(255, 255, 255, 0.06);
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 0.85rem;
      padding-bottom: 1rem;
      border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    }

    .brand-mark {
      width: 44px;
      height: 44px;
      border-radius: 14px;
      display: grid;
      place-items: center;
      background: linear-gradient(135deg, var(--accent), var(--accent-2));
      box-shadow: 0 14px 28px rgba(15, 98, 254, 0.32);
      font-weight: 800;
    }

    .brand-title {
      font-size: 1rem;
      font-weight: 700;
      margin: 0;
      line-height: 1.1;
    }

    .brand-subtitle {
      margin: 0.15rem 0 0;
      color: rgba(255, 255, 255, 0.66);
      font-size: 0.82rem;
    }

    .sidebar-nav {
      margin-top: 1.5rem;
      display: grid;
      gap: 0.5rem;
    }

    .sidebar-nav a {
      color: rgba(255, 255, 255, 0.82);
      text-decoration: none;
      display: flex;
      align-items: center;
      gap: 0.85rem;
      padding: 0.85rem 1rem;
      border-radius: 14px;
      transition: 160ms ease;
    }

    .sidebar-nav a:hover,
    .sidebar-nav a.active {
      background: rgba(255, 255, 255, 0.08);
      color: #fff;
      transform: translateX(2px);
    }

    .sidebar-footer {
      margin-top: auto;
      padding-top: 1.5rem;
      color: rgba(255, 255, 255, 0.72);
      font-size: 0.9rem;
    }

    .content {
      padding: 1.25rem 1.5rem 1.5rem;
    }

    .topbar {
      background: var(--panel);
      backdrop-filter: blur(18px);
      border: 1px solid var(--border);
      border-radius: 22px;
      box-shadow: var(--shadow);
      padding: 1rem 1.15rem;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
      margin-bottom: 1.25rem;
    }

    .topbar h1 {
      margin: 0;
      font-size: 1.15rem;
      font-weight: 800;
    }

    .topbar p {
      margin: 0.2rem 0 0;
      color: var(--muted);
      font-size: 0.92rem;
    }

    .panel {
      background: var(--panel);
      backdrop-filter: blur(18px);
      border: 1px solid var(--border);
      border-radius: 22px;
      box-shadow: var(--shadow);
    }

    .metric-card {
      padding: 1.15rem;
      height: 100%;
      overflow: hidden;
      position: relative;
    }

    .metric-card::after {
      content: "";
      position: absolute;
      inset: auto -20px -20px auto;
      width: 120px;
      height: 120px;
      border-radius: 999px;
      background: radial-gradient(circle, rgba(255, 255, 255, 0.24), transparent 70%);
      pointer-events: none;
    }

    .metric-icon {
      width: 48px;
      height: 48px;
      border-radius: 16px;
      display: grid;
      place-items: center;
      color: #fff;
      margin-bottom: 1rem;
    }

    .metric-value {
      font-size: 1.85rem;
      font-weight: 800;
      line-height: 1;
      margin: 0;
    }

    .metric-label {
      color: var(--muted);
      font-size: 0.9rem;
      margin: 0.35rem 0 0;
    }

    .metric-delta {
      margin-top: 0.8rem;
      display: inline-flex;
      align-items: center;
      gap: 0.35rem;
      font-size: 0.86rem;
      font-weight: 600;
    }

    .panel-header {
      padding: 1.15rem 1.2rem 0;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
    }

    .panel-body {
      padding: 1.2rem;
    }

    .section-title {
      font-size: 0.96rem;
      font-weight: 800;
      margin: 0;
    }

    .section-subtitle {
      margin: 0.25rem 0 0;
      color: var(--muted);
      font-size: 0.88rem;
    }

    .soft-badge {
      display: inline-flex;
      align-items: center;
      padding: 0.35rem 0.7rem;
      border-radius: 999px;
      font-size: 0.78rem;
      font-weight: 700;
      background: rgba(15, 98, 254, 0.12);
      color: var(--accent);
    }

    .table thead th {
      color: var(--muted);
      font-weight: 700;
      border-bottom-width: 1px;
    }

    .table td,
    .table th {
      vertical-align: middle;
      border-color: var(--border);
    }

    .task-item {
      padding: 0.95rem 1rem;
      border: 1px solid var(--border);
      border-radius: 18px;
      background: rgba(255, 255, 255, 0.03);
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 1rem;
    }

    .task-item + .task-item {
      margin-top: 0.75rem;
    }

    .task-item h4 {
      font-size: 0.95rem;
      margin: 0 0 0.25rem;
      font-weight: 700;
    }

    .task-item p {
      margin: 0;
      color: var(--muted);
      font-size: 0.86rem;
    }

    .theme-toggle {
      border: 1px solid var(--border);
      background: var(--panel-solid);
      color: var(--text);
      border-radius: 14px;
      width: 44px;
      height: 44px;
      display: inline-grid;
      place-items: center;
    }

    .mobile-nav-toggle {
      display: none;
    }

    .chart-wrap {
      min-height: 320px;
    }

    @media (max-width: 992px) {
      .app-shell {
        grid-template-columns: 1fr;
      }

      .sidebar {
        position: relative;
        height: auto;
      }

      .mobile-nav-toggle {
        display: inline-grid;
      }

      .sidebar-nav {
        display: none;
      }

      .sidebar[data-expanded="true"] .sidebar-nav {
        display: grid;
      }
    }
  </style>
</head>
<body>
  <div class="app-shell">
    <aside class="sidebar" id="sidebar">
      <div class="brand">
        <div class="brand-mark">AF</div>
        <div>
          <p class="brand-title">AssetFlow</p>
          <p class="brand-subtitle">Enterprise resource operations</p>
        </div>
      </div>

      <nav class="sidebar-nav mt-4">
        <a href="#" class="active"><i class="fa-solid fa-chart-line"></i> Dashboard</a>
        <a href="#"><i class="fa-solid fa-box-archive"></i> Assets</a>
        <a href="#"><i class="fa-solid fa-right-left"></i> Allocations</a>
        <a href="#"><i class="fa-solid fa-calendar-days"></i> Bookings</a>
        <a href="#"><i class="fa-solid fa-screwdriver-wrench"></i> Maintenance</a>
        <a href="#"><i class="fa-solid fa-clipboard-check"></i> Audit</a>
        <a href="#"><i class="fa-solid fa-chart-pie"></i> Reports</a>
        <a href="#"><i class="fa-solid fa-gears"></i> Administration</a>
      </nav>

      <div class="sidebar-footer">
        <div class="d-flex align-items-center gap-2 mb-2">
          <i class="fa-solid fa-shield-halved"></i>
          <span>Secure by design</span>
        </div>
        <div>Session, role and workflow controls will be added in the next files.</div>
      </div>
    </aside>

    <main class="content">
      <div class="topbar">
        <div>
          <div class="d-flex align-items-center gap-2 flex-wrap">
            <button class="btn theme-toggle mobile-nav-toggle" type="button" id="sidebarToggle" aria-label="Toggle navigation">
              <i class="fa-solid fa-bars"></i>
            </button>
            <div>
              <h1>Executive Dashboard</h1>
              <p>Operational overview for assets, bookings, maintenance, and audit readiness.</p>
            </div>
          </div>
        </div>

        <div class="d-flex align-items-center gap-2">
          <button class="btn theme-toggle" type="button" id="themeToggle" aria-label="Toggle theme">
            <i class="fa-solid fa-moon" id="themeIcon"></i>
          </button>
          {% if current_user.is_authenticated %}
          <div class="text-end d-none d-md-block">
            <div class="fw-bold">{{ current_user.full_name }}</div>
            <small class="text-secondary-emphasis">{{ current_user.role.name }}</small>
          </div>
          <form method="post" action="{{ url_for('auth.logout') }}" class="d-inline">
            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
            <button class="btn btn-outline-primary" type="submit">Sign out</button>
          </form>
          {% else %}
          <a class="btn btn-outline-primary" href="{{ url_for('auth.login') }}">Sign in</a>
          <a class="btn btn-primary" href="{{ url_for('auth.signup') }}">Sign up</a>
          {% endif %}
        </div>
      </div>

      <div class="row g-3 mb-3">
        {% for metric in metrics %}
        <div class="col-12 col-sm-6 col-xl-4">
          <div class="panel metric-card h-100">
            <div class="metric-icon bg-{{ metric.tone }}">
              <i class="fa-solid {{ metric.icon }}"></i>
            </div>
            <p class="metric-label">{{ metric.label }}</p>
            <h2 class="metric-value">{{ metric.value }}</h2>
            <div class="metric-delta text-{{ metric.tone }}">
              <i class="fa-solid fa-arrow-trend-up"></i>
              <span>{{ metric.delta }}</span>
            </div>
          </div>
        </div>
        {% endfor %}
      </div>

      <div class="row g-3 mb-3">
        <div class="col-12 col-xl-8">
          <section class="panel h-100">
            <div class="panel-header">
              <div>
                <h3 class="section-title">Asset utilization trend</h3>
                <p class="section-subtitle">Weekly movement across allocation, maintenance, and reservation demand.</p>
              </div>
              <span class="soft-badge"><i class="fa-solid fa-arrow-up-right-dots me-1"></i>Live view</span>
            </div>
            <div class="panel-body chart-wrap">
              <canvas id="utilizationChart" aria-label="Asset utilization chart" role="img"></canvas>
            </div>
          </section>
        </div>

        <div class="col-12 col-xl-4">
          <section class="panel h-100">
            <div class="panel-header">
              <div>
                <h3 class="section-title">Operational queue</h3>
                <p class="section-subtitle">Workflow items that need attention.</p>
              </div>
            </div>
            <div class="panel-body">
              {% for task in tasks %}
              <div class="task-item">
                <div>
                  <h4>{{ task.title }}</h4>
                  <p>{{ task.subtitle }}</p>
                </div>
                <span class="badge text-bg-light border">{{ task.badge }}</span>
              </div>
              {% endfor %}
            </div>
          </section>
        </div>
      </div>

      <div class="row g-3">
        <div class="col-12 col-lg-7">
          <section class="panel h-100">
            <div class="panel-header">
              <div>
                <h3 class="section-title">Recent activity</h3>
                <p class="section-subtitle">Security-sensitive actions are recorded for auditability.</p>
              </div>
            </div>
            <div class="panel-body table-responsive">
              <table class="table align-middle mb-0">
                <thead>
                  <tr>
                    <th>Action</th>
                    <th>Module</th>
                    <th>Status</th>
                    <th>Time</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>Allocated laptop AF-1021</td>
                    <td>Asset Management</td>
                    <td><span class="badge text-bg-success">Completed</span></td>
                    <td>2 mins ago</td>
                  </tr>
                  <tr>
                    <td>Approved transfer request TR-203</td>
                    <td>Allocation</td>
                    <td><span class="badge text-bg-warning">Pending pickup</span></td>
                    <td>16 mins ago</td>
                  </tr>
                  <tr>
                    <td>Logged maintenance request MR-118</td>
                    <td>Maintenance</td>
                    <td><span class="badge text-bg-info">Assigned</span></td>
                    <td>38 mins ago</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
        </div>

        <div class="col-12 col-lg-5">
          <section class="panel h-100">
            <div class="panel-header">
              <div>
                <h3 class="section-title">Notifications</h3>
                <p class="section-subtitle">In-app and email-ready alerts for operational teams.</p>
              </div>
            </div>
            <div class="panel-body">
              <div class="alert alert-primary mb-3" role="alert">
                <strong>Audit cycle scheduled:</strong> Department audits will open on Monday at 09:00.
              </div>
              <div class="alert alert-warning mb-3" role="alert">
                <strong>Overdue return detected:</strong> 4 assets are beyond their expected return date.
              </div>
              <div class="alert alert-success mb-0" role="alert">
                <strong>Backup status:</strong> Nightly database backup completed successfully.
              </div>
            </div>
          </section>
        </div>
      </div>
    </main>
  </div>

  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"></script>
  <script>
    const savedTheme = localStorage.getItem('assetflow-theme') || 'light';
    const root = document.documentElement;
    const themeIcon = document.getElementById('themeIcon');
    const themeToggle = document.getElementById('themeToggle');
    const sidebar = document.getElementById('sidebar');
    const sidebarToggle = document.getElementById('sidebarToggle');

    function applyTheme(theme) {
      root.setAttribute('data-theme', theme);
      themeIcon.className = theme === 'dark' ? 'fa-solid fa-sun' : 'fa-solid fa-moon';
      localStorage.setItem('assetflow-theme', theme);
    }

    applyTheme(savedTheme);

    themeToggle.addEventListener('click', () => {
      const nextTheme = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
      applyTheme(nextTheme);
    });

    if (sidebarToggle) {
      sidebarToggle.addEventListener('click', () => {
        const expanded = sidebar.getAttribute('data-expanded') === 'true';
        sidebar.setAttribute('data-expanded', String(!expanded));
      });
    }

    new Chart(document.getElementById('utilizationChart'), {
      type: 'line',
      data: {
        labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
        datasets: [
          {
            label: 'Allocated',
            data: [680, 715, 740, 782, 820, 860, 932],
            borderColor: '#0f62fe',
            backgroundColor: 'rgba(15, 98, 254, 0.12)',
            tension: 0.35,
            fill: true,
          },
          {
            label: 'Available',
            data: [1120, 1108, 1091, 1075, 1058, 1038, 1022],
            borderColor: '#16a34a',
            backgroundColor: 'rgba(22, 163, 74, 0.08)',
            tension: 0.35,
            fill: true,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            labels: {
              color: getComputedStyle(document.documentElement).getPropertyValue('--muted').trim(),
              usePointStyle: true,
            },
          },
        },
        scales: {
          x: {
            grid: { color: 'rgba(128, 128, 128, 0.08)' },
            ticks: {
              color: getComputedStyle(document.documentElement).getPropertyValue('--muted').trim(),
            },
          },
          y: {
            grid: { color: 'rgba(128, 128, 128, 0.08)' },
            ticks: {
              color: getComputedStyle(document.documentElement).getPropertyValue('--muted').trim(),
            },
          },
        },
      },
    });
  </script>
</body>
</html>
"""


app = create_app()


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=os.getenv("FLASK_DEBUG", "0") == "1")