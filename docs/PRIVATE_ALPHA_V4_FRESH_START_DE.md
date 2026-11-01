# Private Alpha v4 — Frische Testkonten, Passwort-Login und SEC-01-Reihenfolge

**Nur lokale Simulation. NICHT über Tailscale Serve/Funnel veröffentlichen und keine echten ComfyUI-Effekte auslösen.**

## Empfehlung: Neue Testdatenbank statt Alt-Konten migrieren

Die bisherigen Alpha-v1/v3-Konten können für den nächsten Test ignoriert werden. **Nicht blind die alte Datenbank löschen**: benutze für Auth v4 einen neuen Dateinamen. So bleiben alte Agenten-/Jobdatensätze als Testbackup erhalten und es ist kein Passwort-Reset nötig.

In **PowerShell A (Server)** aus dem Repository-Stammverzeichnis:

```powershell
$alphaDb = "$env:LOCALAPPDATA\Minglefield\private-alpha-v4.sqlite"
New-Item -ItemType Directory -Force (Split-Path $alphaDb) | Out-Null
python -B server/private_alpha_gateway.py --auth-db $alphaDb --port 8767
```

Vorher den alten Gateway per **Ctrl+C** beenden, sonst ist Port 8767 belegt.

In **PowerShell B (Administration)** im selben Repository:

```powershell
$alphaDb = "$env:LOCALAPPDATA\Minglefield\private-alpha-v4.sqlite"
python -B server/private_alpha_admin.py --db $alphaDb invite user.alpha4
```

**Wichtig:** `$alphaDb` ist eine **pro PowerShell-Fenster eigene Variable**. Beide müssen denselben Pfad verwenden. Der Einladungscode wird in PowerShell B angezeigt; er gehört in der neuen Webseite in das Feld **Einladungscode**, nicht ins Passwortfeld.

Im Browser `http://127.0.0.1:8767/`:

1. Einladungscode eintragen.
2. Als Agenten-ID beispielsweise `agent.alpha4` angeben; auch identische Benutzer-/Agenten-ID-Strings bleiben als bewusster Negativtest zulässig.
3. Ein **eigenes, nur für diesen Test verwendetes Passwort mit mindestens 12 Zeichen** eingeben.
4. **Einladung einlösen** klicken, dann **Connect** und **Simulate action**.
5. **Logout** klicken. Danach über **Benutzer-ID + Passwort → Anmelden** erneut einloggen. Dafür darf **kein neuer Einladungscode** erforderlich sein.
6. Browser neu laden und mit Benutzer-ID/Passwort erneut anmelden; Agents und simulierte Jobs müssen erhalten bleiben.

Die serverseitigen Sessions gelten weiterhin nur 15 Minuten. Nach Ablauf einfach erneut mit Benutzer-ID und Passwort anmelden. Passwörter werden in der privaten SQLite-Datenbank als gesalzene `scrypt`-Verifikatoren gespeichert, nicht im Klartext. Keine echten Passwörter verwenden; das ist noch kein produktionsfähiges Identitätssystem.

## Falls später wirklich ein Alt-Konto verwendet werden muss

Der lokale Operator kann das Passwort zurücksetzen und dadurch bestehende Sessions widerrufen, ohne Agenten und Jobhistorie zu löschen:

```powershell
python -B server/private_alpha_admin.py --db $alphaDb reset-password user.alpha4
```

Das ist **kein Remote-Endpunkt**, sondern eine lokale Administratorfunktion. Für den vorgeschlagenen frischen Testbetrieb ist sie **nicht erforderlich**.

## Lokal testen

```powershell
git pull --ff-only
python -B -m unittest discover -s tests/conformance -p "test_private_alpha_relogin.py" -v
python -B -m unittest discover -s tests/conformance -p "test_sec01_authoritative_admission_order.py" -v
python -B -m unittest discover -s tests/conformance -p "test_private_alpha_browser_enrollment.py" -v
python -B -m unittest discover -s tests/conformance -p "test_*.py"
python -B tests/conformance/validate_map_v01.py
git diff --check
git status --short
```

**Erwartung (noch unbestätigt):** 6 neue Passwort-/Recovery-Tests, 3 SEC-01-Ordnungstests, insgesamt **304 Conformance-Tests** gegenüber der zuletzt bestätigten Baseline 295.

## Sicherheitsgrenzen

- Das lokale Registrierungs- und Login-API ist nicht für über Tailscale Serve erreichbare Tester freigegeben; zu prüfen sind Rate-Limits, CSRF/Origin-Validierung, Proxyrouting, Audit und Sitzungsverwaltung.
- Passwörter ermöglichen wiederholte Anmeldung, ersetzen jedoch keine externe Identitätsprüfung oder sichere Account-Recovery für reale Freunde.
- SEC-01 testet derzeit nur die transaktionale Reihenfolge von Widerruf und Admission in einer isolierten SQLite-Datenbank. Weder remote Admission noch echte Game-Effekte wurden aktiviert.
