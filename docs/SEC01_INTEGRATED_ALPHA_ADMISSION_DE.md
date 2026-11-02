# SEC-01 — Integrierte lokale Admission (Private Alpha + Executor/Host)

**Status: CRITICAL / OPEN. Nur Simulation.** Keine Netzwerkschnittstelle, keine ausführbaren Rechte, keine realen Effekte, keine ComfyUI-Aufträge, kein Tailscale Serve.

## Problem und neue gemeinsame Transaktionsgrenze

Die bisherige Private Alpha speichert reale lokale Testbenutzer, Session-Token-Hashes, Agentenbesitz und widerrufbare Fremdbeauftragungs-Grants in einer SQLite-Datenbank. Das bisherige Executor-/Host-Modell verwendete dagegen eine unabhängige Simulationsdatenbank. Bei einer verteilten Prüfung wäre ein Widerruf in Datenbank A **nicht** automatisch mit der Admission in Datenbank B serialisiert.

`server/sec01_integrated_alpha_admission.py` verwendet deshalb **die vorhandene Private-Alpha-Datenbank** und denselben `AlphaAuthStore._tx()`-Mechanismus (`BEGIN IMMEDIATE`) für:

- Authentifizierung des Auftraggebers über eine aktive, nicht widerrufene Alpha-Session.
- Prüfung des aktiven Agenten und des tatsächlichen Eigentümers aus `alpha_agents`/`alpha_users`.
- Eigentümerfreigabe über den **realen** `alpha_agent_grants`-Datensatz, falls der Auftraggeber nicht Eigentümer ist.
- Vertrauensseitig konfigurierte Host-/Executor-Zuordnung in `alpha_executor_hosts` und `alpha_agent_host_assignments`.
- Eindeutiges, dauerhaft gespeichertes Admission-Ledger `alpha_sec01_admissions`.

Die übermittelte `owner_id` und `executor_id` sind lediglich **zu prüfende Behauptungen**. Sie überschreiben nicht die tatsächliche Besitzeridentität bzw. vertrauensseitige Host-Operator-Identität. Die Benutzer-Session bestimmt den Auftraggeber; dessen behauptete ID wird nicht akzeptiert.

## Admission-Entscheidung

`IntegratedAlphaAdmission.admit(authorization, effect_key=..., job_id=..., fingerprint=..., agent_id=..., owner_id=..., executor_id=..., host_id=...)` liefert `LocalAdmission(accepted, reason)`.

Ein **neuer** Admission-Eintrag wird nur innerhalb einer einzigen Transaktion angelegt, wenn alle Bedingungen zutreffen. Eine vorhandene `effect_key`-Bindung kann mit identischen Angaben nur als `already_admitted_no_new_effect` zurückkehren. Abweichende Bindung: `idempotency_binding_mismatch`. Bindungen enthalten `job_id`, `fingerprint`, authentifizierten Auftraggeber, Agenten, Eigentümer, Executor, Host und Aktion.

**Wichtig:** Eine bereits akzeptierte Admission bleibt als historische Entscheidung abrufbar, selbst wenn der Grant später widerrufen wird; dadurch wird **kein neuer Effekt** zugelassen. Jede neu beantragte Admission mit eigenem Effekt-Key prüft den aktuellen Widerruf. Dies ist kein Protokoll, das einen früher zugelassenen externen Auftrag wieder zurückholen oder eine entfernte Ausführung atomar abbrechen kann.

## Sicherheitsgrenzen

Die neuen Host-Provisioning-Methoden sind vertrauenswürdige lokale Test-Fixtures **ohne Authentifizierung** und sind absichtlich kein HTTP-API. Sie dürfen nicht von Auftraggebern angesprochen werden. Der Admission-Service ist nicht in den bestehenden Gateway-/Job-Endpunkt eingebaut: der Browser bleibt bei `demo.echo` und `simulated_no_effect`.

Für ein echtes Remote-System fehlen weiterhin: authentifizierte Executor-Registrierung, hostseitige Consent-/Ressourcenpolicies, kryptographische Identitäts- und Proof-Verifikation, Signaturschlüssel-/Rotation, garantierte Bindung an game-owned Admission, sauberer Effekt-Commit, verteilte Widerrufssemantik, Audit und fail-closed Netzwerkausfallbehandlung. **Es gibt keine Freigabe für Serve oder echte Effekte.**

## Windows-Validierung

```powershell
git pull --ff-only
python -B -m unittest discover -s tests/conformance -p "test_sec01_integrated_alpha_admission.py" -v
python -B -m unittest discover -s tests/conformance -p "test_*.py"
python -B tests/conformance/validate_map_v01.py
git diff --check
git status --short
```

Zuletzt vom Betreiber bestätigt: **323/323**. Neue Tests: **12**, erwartet **335/335** nach erfolgreichem Windows-Test. Bestehende Testkonten und laufender Gateway müssen für diese isolierte Validierung nicht verändert werden.
