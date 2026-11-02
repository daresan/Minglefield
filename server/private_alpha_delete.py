"""Transactional cleanup of Alpha metadata only; never mutate MAP ledgers."""
import json
import sqlite3

from private_alpha_auth import ident


ROUTES = {
    "/api/hosts/delete": ("host", {"host_id"}),
    "/api/agents/delete": ("agent", {"agent_id"}),
    "/api/host/effects/delete": ("effect", {"host_id", "effect_id"}),
    "/api/host/jobs/delete": ("host_job", {"host_id", "job_id"}),
    "/api/jobs/delete": ("job", {"job_id"}),
}


def delete_resource(store, authorization, kind, body):
    """Session and dependencies are checked under the same write lock as deletion.

    Parents require jobs to be explicitly removed first, including other users'
    demo jobs. Execution grants do not confer resource management permission.
    """
    expected = next(fields for resource, fields in ROUTES.values() if resource == kind)
    if type(body) is not dict or set(body) != expected or not all(ident(v) for v in body.values()):
        return 400, {"error": "invalid_delete_request"}
    try:
        with store._tx() as db:
            actor = store._active_user(db, authorization)
            if actor is None:
                return 401, {"error": "unauthorized"}
            tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}

            def exists(table, where, args):
                return table in tables and db.execute(
                    f'SELECT 1 FROM "{table}" WHERE {where} LIMIT 1', args).fetchone() is not None

            host = body.get("host_id")
            key = body.get("agent_id") or body.get("job_id") or body.get("effect_id") or host
            table, column = {"host": ("alpha_executor_hosts", "host_id"),
                "agent": ("alpha_agents", "agent_id"),
                "effect": ("sec01_host_effect_definitions", "effect_id"),
                "host_job": ("sec01_host_jobs", "job_id"),
                "job": ("alpha_jobs", "job_id")}[kind]
            where, args = f"{column}=?", (key,)
            if kind in ("effect", "host_job"):
                where += " AND host_id=?"
                args += (host,)
            if not exists(table, where, args):
                return 404, {"error": "resource_not_found"}
            owner = exists("sec01_host_owners", "host_id=? AND owner_id=?", (host, actor))
            allowed = owner if kind in ("host", "effect") else exists(
                table, where + (" AND requested_by=?" if kind == "host_job" else " AND user_id=?"), args + (actor,))
            if kind == "host_job":
                allowed = allowed or owner
            if not allowed:
                return 403, {"error": "not_resource_owner"}

            # Preserve identity and replay protection for every recorded admission.
            if "alpha_sec01_admissions" in tables:
                for (binding,) in db.execute("SELECT binding FROM alpha_sec01_admissions"):
                    try:
                        values = json.loads(binding)
                    except (ValueError, TypeError):
                        return 409, {"error": "protected_history_exists"}
                    index = {"host": 6, "agent": 3, "job": 0, "host_job": 0}.get(kind)
                    if not isinstance(values, list) or len(values) != 8 or (index is not None and values[index] == key):
                        return 409, {"error": "protected_history_exists"}
            # MAP/B1/B2 tables are read-only here, including unknown future tables
            # exposing these identity columns. No generic cascading DELETE.
            alpha_tables = {"alpha_agents", "alpha_jobs", "alpha_agent_grants",
                "alpha_agent_host_assignments", "alpha_executor_hosts",
                "sec01_host_owners", "sec01_host_admins", "sec01_host_rules",
                "sec01_host_effect_definitions", "sec01_host_jobs"}
            for protected in tables - alpha_tables:
                quoted = '"' + protected.replace('"', '""') + '"'
                columns = {r[1] for r in db.execute(f"PRAGMA table_info({quoted})")}
                reference = "effect_key" if kind == "host_job" and "effect_key" in columns else column
                if reference in columns and db.execute(
                        f'SELECT 1 FROM {quoted} WHERE "{reference}"=? LIMIT 1', (key,)).fetchone():
                    return 409, {"error": "protected_history_or_reservation_exists"}
            if kind == "host_job":
                if not exists(table, where + " AND state='cancelled'", args):
                    return 409, {"error": "cancel_job_first"}
            if kind == "job" and not exists(table, where + " AND action='demo.echo'", args):
                return 409, {"error": "not_alpha_test_job"}
            if kind in ("host", "effect"):
                job_where = "host_id=?" + (" AND effect_id=?" if kind == "effect" else "")
                job_args = (host, key) if kind == "effect" else (host,)
                if exists("sec01_host_jobs", job_where, job_args):
                    return 409, {"error": "delete_dependent_jobs_first"}
                # Slots may belong to commits without a host-job row.
                if exists("sec01_host_active_slots", "host_id=?", (host,)):
                    return 409, {"error": "active_reservation_exists"}
            if kind == "agent" and exists("alpha_jobs", "agent_id=?", (key,)):
                return 409, {"error": "delete_dependent_jobs_first"}
            dependents = []
            if kind == "host":
                dependents = ["sec01_host_effect_definitions", "sec01_host_rules",
                    "sec01_host_admins", "sec01_host_owners", "alpha_agent_host_assignments"]
            elif kind == "agent":
                dependents = ["alpha_agent_grants", "alpha_agent_host_assignments"]
            for dependent in dependents:
                if dependent in tables:
                    db.execute(f'DELETE FROM "{dependent}" WHERE {column}=?', (key,))
            db.execute(f'DELETE FROM "{table}" WHERE {where}', args)
        return 200, {"state": "deleted_alpha", "simulation_only": True}
    except sqlite3.Error:
        # The context manager rolls back every dependent change before replying.
        return 409, {"error": "delete_transaction_failed"}
