# SEC-01 Remote-Admission-Vertrag — lokale Proof-/Pre-Commit-Simulation

**Status: CRITICAL / OPEN. KEINE Remote-Freigabe.** Kein Netzwerk-Endpunkt, kein Tailscale Serve, kein realer Effekt oder ComfyUI-Auftrag.

## Modell

`server/sec01_remote_precommit_sim.py` bindet die bisher getrennten lokalen Bausteine in einer bewusst **nicht ausführenden** Schnittstelle zusammen:

1. **Issuer:** `LocalProofIssuer.issue()` fordert über `IntegratedAlphaAdmission.admit()` eine **neue** atomar gespeicherte Entscheidung an. Ohne gültige Session, Agent, Eigentümer, Fremdgrant und Hostzuordnung entsteht kein Proof.
2. **Mock Proof:** Der bestehende HMAC-Testnachweis bindet `issuer`, `audience=host_id`, `executor`, `job_id`, `request_fingerprint`, `effect_key`, kurze Gültigkeit und `nonce`. Der Issuer erzeugt bei einer historischen Wiederholung desselben `effect_key` **keinen neuen** Proof.
3. **Executor Pre-Commit:** `online_precommit_check()` validiert Proof-MAC, Empfänger, Executor, Job, Fingerprint, Effekt-Key und Gültigkeit. Danach öffnet er eine Transaktion in derselben Alpha-Autoritätsdatenbank und kontrolliert den exakt gespeicherten Admission-Binding-Datensatz, aktiven Requester und Owner, Agent, weiterhin gültigen Grant sowie aktive Host-/Agentzuordnung.
4. **Fail closed:** Bei nicht verfügbarer Autorität erfolgt `authority_unavailable`, bei Widerrufen oder falscher Bindung ein konkreter Denial. Ergebnis `online_precheck_only_no_effect` löst **nie** eine externe Ausführung aus.

## Aktuell geprüfte Fälle

`tests/conformance/test_sec01_remote_precommit_sim.py` deckt zehn Szenarien ab: fehlender Grant, erfolgreiche Ausstellung, keine erneute Ausstellung für denselben Effekt, manipulierte MAC, falsche Audience/Executor und abgelaufene Gültigkeit, Widerruf nach Proof-Ausstellung, Host- und Assignment-Widerruf, Deaktivierung von Requester/Owner, falscher Requester, fehlende Autorität, fehlender Admission-Datensatz, dreifache Prüfung ohne Effekt.

## Offene SEC-01-Blocker (explizit)

- **Keine verteilte Atomizität:** Zwischen einem Online-Precheck und einem entfernten Spiel-/Executor-Commit kann ein Widerruf erfolgen. Eine separate Bestätigung und ein serverseitig definierter finaler Commit-Vertrag sind nötig. Ein Proof oder positives Precheck-Ergebnis allein **darf niemals** einen Effekt auslösen.
- **Revoke/Regrant-ABA:** Die bisherige `alpha_agent_grants`-Tabelle hält aktuell nur `revoked`, keine monotone Grant-Epoch. Widerruf mit anschließender neuer Freigabe kann von einem älteren Proof nicht unterschieden werden. Vor jeder Ausführung sind monotone Versionen und Proof-Bindung an diese Generation erforderlich.
- **Session-Epoch:** Nach Proof-Ausstellung wird aktuell die fortbestehende **Benutzeraktivität**, aber nicht der Zustand der ursprünglichen konkreten Session geprüft. Session-Token-/Grant-/Agent-/Host-Epochen müssen im zukünftigen Proof und finalen Commit-Vertrag berücksichtigt werden.
- **HMAC statt echter Identitätsinfrastruktur:** Der Test-MAC verwendet einen gemeinsamen symmetrischen Schlüssel. Er ist für unabhängig verwaltete Hosts ungeeignet. Erforderlich sind authentifizierte Issuer, Schlüsselverteilung/Rotation und ein tragfähiges Signatur-/Verifikationsmodell.
- **Keine Game-Bindung:** Die existierende `MockTransactionalGame`-Fixture ist absichtlich nicht automatisch an die Online-Prüfung gekoppelt, da dies sonst eine nicht vorhandene atomare Garantie suggerieren würde.
- **Keine echten Rollen-/Host-Trust- oder Audit-Garantien.** Provisioning und Testschlüssel bleiben rein lokal und vertrauensbasiert.

## Windows-Validierung

```powershell
git pull --ff-only
python -B -m unittest discover -s tests/conformance -p "test_sec01_remote_precommit_sim.py" -v
python -B -m unittest discover -s tests/conformance -p "test_*.py"
python -B tests/conformance/validate_map_v01.py
git diff --check
git status --short
```

Bestätigte Ausgangsbasis: **335/335**. Neu: **10 Tests**. Erwartet **345/345** nach lokaler Validierung; noch nicht bestätigt.

**Nächste technische Maßnahme:** Zuerst monotone Session-/Grant-/Agent-/Host-Generationen und Revoke/Regrant-Tests, dann endgültige remote Commit-Semantik entwerfen. Nicht per Gateway oder Serve freigeben.
