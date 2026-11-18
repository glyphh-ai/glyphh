"""Glyphh's staff view of the platform: every org's account and billing as recorded, the server's health and its
errors, and the one staff action left (suspending an org). Reached only at /v1/admin, by staff (admin/staff.py), on
a transaction that crosses orgs on purpose (api/admin/deps.py) and writes every request to admin_audit
(admin/audit.py)."""
