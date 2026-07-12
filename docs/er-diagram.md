# AssetFlow ER Diagram

This diagram reflects the current normalized schema slice implemented in `models.py`.
It covers identity, organizational structure, asset lifecycle, allocation, transfer,
booking, maintenance, audit, notifications, and activity logging.

```mermaid
erDiagram
    ROLES ||--o{ USERS : assigns
    DEPARTMENTS ||--o{ USERS : owns
    DEPARTMENTS ||--o{ EMPLOYEES : includes
    USERS ||--o| EMPLOYEES : profiles
    DEPARTMENTS ||--o{ DEPARTMENTS : manages
    USERS ||--o{ DEPARTMENTS : manages

    ASSET_CATEGORIES ||--o{ ASSETS : classifies
    USERS ||--o{ ASSETS : custodies
    ASSETS ||--o{ ASSET_ALLOCATIONS : allocates
    USERS ||--o{ ASSET_ALLOCATIONS : receives
    USERS ||--o{ ASSET_ALLOCATIONS : issues
    USERS ||--o{ ASSET_ALLOCATIONS : approves

    ASSETS ||--o{ TRANSFER_REQUESTS : transfers
    USERS ||--o{ TRANSFER_REQUESTS : requests
    USERS ||--o{ TRANSFER_REQUESTS : sources
    USERS ||--o{ TRANSFER_REQUESTS : targets
    USERS ||--o{ TRANSFER_REQUESTS : approves

    ASSETS ||--o{ BOOKINGS : reserves
    USERS ||--o{ BOOKINGS : books
    USERS ||--o{ BOOKINGS : approves

    ASSETS ||--o{ MAINTENANCE_REQUESTS : needs
    USERS ||--o{ MAINTENANCE_REQUESTS : requests
    USERS ||--o{ MAINTENANCE_REQUESTS : assigned_to
    MAINTENANCE_REQUESTS ||--o{ MAINTENANCE_HISTORY : tracks
    USERS ||--o{ MAINTENANCE_HISTORY : acts_on

    USERS ||--o{ AUDIT_CYCLES : creates
    USERS ||--o{ AUDIT_CYCLES : closes
    AUDIT_CYCLES ||--o{ AUDIT_ITEMS : contains
    ASSETS ||--o{ AUDIT_ITEMS : audited
    USERS ||--o{ AUDIT_ITEMS : audits

    USERS ||--o{ NOTIFICATIONS : receives
    USERS ||--o{ ACTIVITY_LOGS : performs
```

## Notes

- The model is intentionally normalized so workflow tables keep their own history instead of embedding state into `assets` or `users`.
- Indexes are added on commonly filtered fields such as `status`, `asset_tag`, `recipient_user_id`, and time-based workflow columns.
- The next natural step is adding migrations and seed/bootstrap routines so the schema can be created and initialized consistently across environments.
