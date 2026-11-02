# SEC-01: Persistente Host-Jobwarteschlange (Alpha, Mock)

Die lokale Alpha-Oberfläche kann einen vom Hostbesitzer definierten und aktivierten Effekt als **Mock-Job** in SQLite einreihen. `sec01_host_jobs` speichert `job_id`, `host_id`, `effect_id`, `requested_by`, `state=queued` und `created_at`. `GET /api/host/jobs?host_id=...` ist auf den angemeldeten Hostbesitzer begrenzt; höchstens 200 Einträge werden angezeigt.

Die Schaltfläche **Job in Warteschlange einreihen** ruft `POST /api/host/effects/manual` auf. Bei Erfolg liefert sie `state=queued_mock` und die generierte Job-ID im Feld `reason`. **Host-Jobs laden** zeigt die persistierten Einträge. Die Warteschlange überlebt Gateway-Neustarts mit derselben Auth-SQLite-Datenbank.

**Wichtig:** `queued` ist nur eine gespeicherte Startabsicht, **keine Autorisierung, Reservierung oder Ausführung**. Diese Phase besitzt noch keinen Worker, keine automatische Freigabe, keine Host-Telemetrie und keine effektive Durchsetzung der Regeln auf der Queue. Auch ein manueller Start umgeht keine Sicherheitsprüfung, weil er keinerlei Effekt auslöst.

Nächste zwingende Schritte vor einer Ausführung: atomare Autorisierung mit Session-/Epoch-Bindung, Host-Policy-Auswertung im finalen Commit, persistente Leasing-/Fencing-Mechanismen, eindeutige Idempotenz, Recovery für unsichere Zustände ohne Auto-Replay, hostseitig überprüfbare Executor-Identität und erneute Conformance-Tests. SEC-01 bleibt **CRITICAL/OPEN**. Keine echten Effekte und kein Tailscale Serve.

## Tests

```powershell
python -B -m unittest discover -s tests/conformance -p "test_private_alpha_host_owner_ui.py" -v
python -B -m unittest discover -s tests/conformance -p "test_*.py"
python -B tests/conformance/validate_map_v01.py
git diff --check
git status --short
```
