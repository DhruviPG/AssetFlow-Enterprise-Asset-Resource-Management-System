"""Core SQLAlchemy models for AssetFlow.

This file establishes the first normalized persistence layer for the platform.
It focuses on identity, organization, employees, and the first asset tables so
the rest of the application can grow around a stable schema foundation.
"""

from __future__ import annotations

from datetime import datetime

from flask_login import UserMixin
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from extensions import db, login_manager


class TimestampMixin:
    """Provide created and updated timestamps for audited records."""

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class Role(db.Model, TimestampMixin):
    """Represents a security role used for authorization checks."""

    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(255))
    default_email: Mapped[str | None] = mapped_column(String(255))
    default_password_hash: Mapped[str | None] = mapped_column(String(255))

    users: Mapped[list["User"]] = relationship(back_populates="role")


class Department(db.Model, TimestampMixin):
    """Represents a business department or cost center."""

    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(255))
    manager_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    employees: Mapped[list["Employee"]] = relationship(back_populates="department", foreign_keys="Employee.department_id")
    manager: Mapped[User | None] = relationship(foreign_keys=[manager_user_id])


class User(db.Model, UserMixin, TimestampMixin):
    """Represents an authenticated application user."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    is_active_account: Mapped[bool] = mapped_column(nullable=False, default=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    role: Mapped[Role] = relationship(back_populates="users")
    department: Mapped[Department | None] = relationship(foreign_keys=[department_id])
    employee_profile: Mapped[Employee | None] = relationship(back_populates="user", uselist=False)
    allocations: Mapped[list["AssetAllocation"]] = relationship(
        back_populates="allocated_to", foreign_keys="AssetAllocation.allocated_to_user_id"
    )
    issued_allocations: Mapped[list["AssetAllocation"]] = relationship(
        back_populates="allocated_by", foreign_keys="AssetAllocation.allocated_by_user_id"
    )
    approved_allocations: Mapped[list["AssetAllocation"]] = relationship(
        back_populates="approved_by", foreign_keys="AssetAllocation.approved_by_user_id"
    )
    requested_transfers: Mapped[list["TransferRequest"]] = relationship(
        back_populates="requested_by", foreign_keys="TransferRequest.requested_by_user_id"
    )
    bookings: Mapped[list["Booking"]] = relationship(back_populates="booked_by", foreign_keys="Booking.booked_by_user_id")
    maintenance_requests: Mapped[list["MaintenanceRequest"]] = relationship(
        back_populates="requested_by", foreign_keys="MaintenanceRequest.requested_by_user_id"
    )
    assigned_maintenance: Mapped[list["MaintenanceRequest"]] = relationship(
        back_populates="assigned_technician", foreign_keys="MaintenanceRequest.assigned_technician_user_id"
    )
    audit_items: Mapped[list["AuditItem"]] = relationship(back_populates="audited_by", foreign_keys="AuditItem.audited_by_user_id")
    notifications: Mapped[list["Notification"]] = relationship(back_populates="recipient", foreign_keys="Notification.recipient_user_id")
    activity_logs: Mapped[list["ActivityLog"]] = relationship(back_populates="actor", foreign_keys="ActivityLog.actor_user_id")


@login_manager.user_loader
def load_user(user_id: str) -> User | None:
    """Return the user record required by Flask-Login."""

    if not user_id:
        return None
    return db.session.get(User, int(user_id))


class Employee(db.Model, TimestampMixin):
    """Stores employee-specific organizational details."""

    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employee_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    job_title: Mapped[str] = mapped_column(String(150), nullable=False)
    phone_number: Mapped[str | None] = mapped_column(String(50))
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    reports_to_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"))

    department: Mapped[Department] = relationship(back_populates="employees", foreign_keys=[department_id])
    user: Mapped[User] = relationship(back_populates="employee_profile", foreign_keys=[user_id])
    manager: Mapped[Employee | None] = relationship(remote_side="Employee.id", foreign_keys=[reports_to_employee_id])


class AssetCategory(db.Model, TimestampMixin):
    """Defines a normalized asset classification."""

    __tablename__ = "asset_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))

    assets: Mapped[list["Asset"]] = relationship(back_populates="category")


class Asset(db.Model, TimestampMixin):
    """Represents a tracked enterprise asset."""

    __tablename__ = "assets"
    __table_args__ = (
        CheckConstraint("current_value >= 0", name="ck_assets_current_value_non_negative"),
        Index("ix_assets_asset_tag", "asset_tag"),
        Index("ix_assets_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_tag: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    serial_number: Mapped[str | None] = mapped_column(String(120), index=True)
    barcode_value: Mapped[str | None] = mapped_column(String(120), unique=True, index=True)
    qr_code_value: Mapped[str | None] = mapped_column(String(120), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="available")
    condition: Mapped[str] = mapped_column(String(40), nullable=False, default="good")
    current_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    category_id: Mapped[int] = mapped_column(ForeignKey("asset_categories.id", ondelete="RESTRICT"), nullable=False)
    custodian_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    category: Mapped[AssetCategory] = relationship(back_populates="assets")
    custodian: Mapped[User | None] = relationship(foreign_keys=[custodian_user_id])
    allocations: Mapped[list["AssetAllocation"]] = relationship(back_populates="asset")
    transfer_requests: Mapped[list["TransferRequest"]] = relationship(back_populates="asset")
    bookings: Mapped[list["Booking"]] = relationship(back_populates="asset")
    maintenance_requests: Mapped[list["MaintenanceRequest"]] = relationship(back_populates="asset")
    audit_items: Mapped[list["AuditItem"]] = relationship(back_populates="asset")


class AssetAllocation(db.Model, TimestampMixin):
    """Tracks allocation history for an asset assigned to a user."""

    __tablename__ = "asset_allocations"
    __table_args__ = (
        Index("ix_asset_allocations_status", "status"),
        Index("ix_asset_allocations_due_return_at", "due_return_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="RESTRICT"), nullable=False)
    allocated_to_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    allocated_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    approved_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    allocated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    due_return_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    returned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    condition_on_issue: Mapped[str] = mapped_column(String(40), nullable=False, default="good")
    condition_on_return: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="allocated")
    notes: Mapped[str | None] = mapped_column(Text)

    asset: Mapped[Asset] = relationship(back_populates="allocations")
    allocated_to: Mapped[User] = relationship(back_populates="allocations", foreign_keys=[allocated_to_user_id])
    allocated_by: Mapped[User] = relationship(back_populates="issued_allocations", foreign_keys=[allocated_by_user_id])
    approved_by: Mapped[User | None] = relationship(back_populates="approved_allocations", foreign_keys=[approved_by_user_id])


class TransferRequest(db.Model, TimestampMixin):
    """Represents a workflow request to transfer an asset between owners."""

    __tablename__ = "transfer_requests"
    __table_args__ = (
        Index("ix_transfer_requests_status", "status"),
        Index("ix_transfer_requests_requested_at", "requested_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="RESTRICT"), nullable=False)
    requested_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    source_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    target_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    approved_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    decision_notes: Mapped[str | None] = mapped_column(Text)

    asset: Mapped[Asset] = relationship(back_populates="transfer_requests")
    requested_by: Mapped[User] = relationship(back_populates="requested_transfers", foreign_keys=[requested_by_user_id])
    source_user: Mapped[User | None] = relationship(foreign_keys=[source_user_id])
    target_user: Mapped[User | None] = relationship(foreign_keys=[target_user_id])
    approved_by: Mapped[User | None] = relationship(foreign_keys=[approved_by_user_id])


class Booking(db.Model, TimestampMixin):
    """Tracks time-bound asset reservations."""

    __tablename__ = "bookings"
    __table_args__ = (
        Index("ix_bookings_asset_id_start_at", "asset_id", "start_at"),
        Index("ix_bookings_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="RESTRICT"), nullable=False)
    booked_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    approved_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    purpose: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="requested")
    notes: Mapped[str | None] = mapped_column(Text)

    asset: Mapped[Asset] = relationship(back_populates="bookings")
    booked_by: Mapped[User] = relationship(back_populates="bookings", foreign_keys=[booked_by_user_id])
    approved_by: Mapped[User | None] = relationship(foreign_keys=[approved_by_user_id])


class MaintenanceRequest(db.Model, TimestampMixin):
    """Represents a request to inspect or repair an asset."""

    __tablename__ = "maintenance_requests"
    __table_args__ = (
        Index("ix_maintenance_requests_status", "status"),
        Index("ix_maintenance_requests_priority", "priority"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="RESTRICT"), nullable=False)
    requested_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    assigned_technician_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="open")
    issue_summary: Mapped[str] = mapped_column(String(200), nullable=False)
    issue_details: Mapped[str | None] = mapped_column(Text)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    asset: Mapped[Asset] = relationship(back_populates="maintenance_requests")
    requested_by: Mapped[User] = relationship(back_populates="maintenance_requests", foreign_keys=[requested_by_user_id])
    assigned_technician: Mapped[User | None] = relationship(back_populates="assigned_maintenance", foreign_keys=[assigned_technician_user_id])
    history_entries: Mapped[list["MaintenanceHistory"]] = relationship(back_populates="request")


class MaintenanceHistory(db.Model, TimestampMixin):
    """Captures workflow changes and status updates for maintenance requests."""

    __tablename__ = "maintenance_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("maintenance_requests.id", ondelete="CASCADE"), nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    actioned_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    actioned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    request: Mapped[MaintenanceRequest] = relationship(back_populates="history_entries")
    actioned_by: Mapped[User | None] = relationship(foreign_keys=[actioned_by_user_id])


class AuditCycle(db.Model, TimestampMixin):
    """Represents a time-boxed audit run for a department or site."""

    __tablename__ = "audit_cycles"
    __table_args__ = (Index("ix_audit_cycles_status", "status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="open")
    scheduled_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scheduled_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    closed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_by: Mapped[User] = relationship(foreign_keys=[created_by_user_id])
    closed_by: Mapped[User | None] = relationship(foreign_keys=[closed_by_user_id])
    items: Mapped[list["AuditItem"]] = relationship(back_populates="cycle")


class AuditItem(db.Model, TimestampMixin):
    """Stores the result of auditing a single asset within a cycle."""

    __tablename__ = "audit_items"
    __table_args__ = (
        UniqueConstraint("audit_cycle_id", "asset_id", name="uq_audit_items_cycle_asset"),
        Index("ix_audit_items_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    audit_cycle_id: Mapped[int] = mapped_column(ForeignKey("audit_cycles.id", ondelete="CASCADE"), nullable=False)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="RESTRICT"), nullable=False)
    audited_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="present")
    condition_found: Mapped[str | None] = mapped_column(String(40))
    remarks: Mapped[str | None] = mapped_column(Text)
    audited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    cycle: Mapped[AuditCycle] = relationship(back_populates="items")
    asset: Mapped[Asset] = relationship(back_populates="audit_items")
    audited_by: Mapped[User | None] = relationship(back_populates="audit_items", foreign_keys=[audited_by_user_id])


class Notification(db.Model, TimestampMixin):
    """Stores in-app and email-ready notifications for a user."""

    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_recipient_is_read", "recipient_user_id", "is_read"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recipient_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False, default="info")
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    action_url: Mapped[str | None] = mapped_column(String(255))

    recipient: Mapped[User] = relationship(back_populates="notifications", foreign_keys=[recipient_user_id])


class ActivityLog(db.Model):
    """Records security-sensitive actions across the application."""

    __tablename__ = "activity_logs"
    __table_args__ = (
        Index("ix_activity_logs_actor_created_at", "actor_user_id", "created_at"),
        Index("ix_activity_logs_entity_type_entity_id", "entity_type", "entity_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(80), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(255))
    details: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    actor: Mapped[User | None] = relationship(back_populates="activity_logs", foreign_keys=[actor_user_id])
