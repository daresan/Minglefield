# Private Alpha: Host-Verwaltung und Mock-Lifecycle

**Lokaler Teststand; keine realen Effekte, keine GPU-Abfrage, kein Tailscale Serve.**

Die Alpha-Weboberfläche auf `http://127.0.0.1:8767/` enthält jetzt Abschnitt **5. Host-Verwaltung**. Nach Anmeldung sieht ein Benutzer ausschließlich Hosts, für die er als Host-Administrator registriert wurde. Vorhandene Regeln können geladen, bearbeitet, gespeichert, aktiviert/deaktiviert und gelöscht werden.

Konfigurierbar sind Priorität, automatisch/manuell, nur bei Leerlauf, GPU-Auslastungsgrenze, maximal parallele Effekte, IANA-Zeitzone, Wochentage und Tageszeitfenster. Mehrere Regeln pro Host sind möglich. Das ist eine echte lokale UI-Anbindung an die SQLite-Simulationsregeln, keine bloße Darstellung.

## Einmalige lokale Einrichtung

Den Gateway mit bestehender Alpha-DB starten, wie bisher:

```powershell
python server/private_alpha_gateway.py --auth-db "$env:LOCALAPPDATA\Minglefield\private-alpha-v4.sqlite"
```

Für einen **bereits in der Alpha-DB angelegten Host** und einen **bestehenden aktiven Alpha-Benutzer** kann ein lokaler Betreiber die Host-Administratorzuordnung anlegen:

```powershell
python server/sec01_host_admin_local.py --auth-db "$env:LOCALAPPDATA\Minglefield\private-alpha-v4.sqlite" --host host.example --admin user.example
```

Die Beispiel-IDs durch tatsächliche Werte ersetzen. Das CLI erstellt keinen Host und keinen Benutzer und hat absichtlich keinen HTTP-Endpunkt. Keine automatischen Host-Admin-Rechte für Agentenbesitzer.

## API (nur lokaler Auth-DB-Modus)

- `GET /api/hosts`: ausschließlich administrierbare Hosts samt Regeln und reservierten Mock-Slots.
- `POST /api/host/rules`: Regel speichern/bearbeiten/aktivieren/deaktivieren.
- `POST /api/host/rules/delete`: Regel löschen.

Alle Operationen verwenden die bestehende Alpha-Session und prüfen Host-Administratorrechte. Kein API-Pfad startet einen Effekt. Demo-Modus ohne Alpha-DB zeigt keine administrierbaren Hosts.

## Lifecycle und Recovery

`HostCommitPolicy.lifecycle(host_id,admin_id)` zeigt `reserved_mock` bzw. `finished_mock`. `restart_recovery_snapshot(host_id,admin_id)` markiert im Rückgabewert nach einem Neustart weiterhin reservierte Slots als **uncertain_after_restart**, mit `auto_retry_allowed=False`. Der persistente Slot bleibt belegt. Dies ist eine **konservative Beobachtung**, noch keine persistente Lease- oder Recovery-State-Machine. Ein Admin kann in der lokalen Simulation über die bestehende `finish_mock`-Methode einen Slot auflösen; hierfür gibt es noch keinen UI-Knopf.

**Noch ausstehend:** persistente Lease-Tokens/Generation, Heartbeats, Zeitüberschreitung, abgestürzte Worker, sichere Admin-Auflösung, Jobwarteschlange und die atomare Integration der Session-/Epoch-Prüfung in den Mock-Commit. Eine bereits erfolgte externe Wirkung darf niemals durch automatische Wiederholung verdoppelt werden.

## Validierung

```powershell
git pull --ff-only
python -B -m unittest discover -s tests/conformance -p "test_private_alpha_host_ui.py" -v
python -B -m unittest discover -s tests/conformance -p "test_sec01_host_commit_policy.py" -v
python -B -m unittest discover -s tests/conformance -p "test_*.py"
python -B tests/conformance/validate_map_v01.py
git diff --check
git status --short
```

Bestätigter Stand vor diesem Schritt: **373 Tests**. Neu: drei UI-/API-Tests. Erwartet: **376**, nach Betreiberprüfung.
