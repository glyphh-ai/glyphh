"""Glyphh's staff view of the platform: every org's account and usage metadata, the server's health and its errors,
and the few staff actions (Enterprise, a plan version, suspending). Reached only at /v1/admin, by staff
(admin/staff.py), on a transaction that crosses orgs on purpose (api/admin/deps.py) and writes every request to
admin_audit (admin/audit.py). Never a customer's precedents, cases, specs or files: counts and names only."""
