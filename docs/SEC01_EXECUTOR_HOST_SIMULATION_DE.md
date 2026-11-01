# SEC-01 Executor / Host — isolierter Sicherheitsprototyp

**Status: CRITICAL / OPEN.** Nur lokale SQLite-Simulation, **keine** echten Host-Befehle, kein Agentenstart, keine Remote-API, keine ComfyUI-Aufträge und keine Tailscale-Serve-Freigabe.

## Identitäten und Rechte

- **Owner** (`user.owner`): Eigentümer eines Agenten; die Eigentümer-ID ist unveränderlich im lokalen Agenten-Fixture.
- **Requester** (`user.friend`): Auftraggeber, der einen fremden Agenten nur mit einem ausdrücklich eingerichteten, aktiven `demo.echo`-Grant beauftragen darf.
- **Agent** (`agent.images`): eigenständige Identität und Aktionsziel; kein Benutzerkonto und kein Executor-Login.
- **Executor** (`operator.cloud`): vertrauensseitig definierte Operator-Identität des ausführenden Hosts.
- **Host** (`host.cloud`): unabhängig aktivierbare Ressource; der Host muss dem Agenten **separat** zugeordnet sein.

Die lokal simulierte Zulassungsentscheidung erfolgt erst dann, wenn **alle** Bedingungen gelten: gültige Bindungsfelder, aktiver Agent, korrekter Eigentümer, aktiver Host, Host-Operator stimmt mit Executor-ID überein, vorhandene Agent→Host-Zuordnung und Auftraggeber ist entweder Eigentümer oder besitzt einen aktiven `demo.echo`-Grant.

`effect_key` bindet Job, Fingerprint, Requester, Agent, Owner, Executor, Host und Aktion per persistenter Idempotenz. Identische Wiederholungen ergeben `already_admitted_no_new_effect`, veränderte Bindungen `idempotency_binding_mismatch`.

## Implementiert

- `server/sec01_executor_host_admission_sim.py` modelliert Eigentümer/Agenten, Host/Executor, separate Agent→Host-Zuordnungen, Auftraggeber-Grants und Admission-Records in einer **einzigen SQLite-Transaktionsdomäne**.
- `tests/conformance/test_sec01_executor_host_admission.py` prüft acht Szenarien: ohne Grant, positive Fremdbeauftragung, willkürliche Host-/Executor-Wahl, Grant-Widerruf, Host-/Zuordnungs-Widerruf, Owner-Verwechslung, eigene Aufträge, Idempotenz und parallele Revocation.
- Bestehende `private_alpha_gateway.py`, `private_alpha_auth.py` und MAP-Protokollflächen werden durch diesen Schritt **nicht** verändert. Es ist ein eigenständiger Sicherheitsbaustein.

## Architekturgrenze (wichtig)

Alle Provisioning-/Grant-/Host-Methoden sind **vertrauensbasierte Test-Fixtures** und authentifizieren keinen echten Benutzer oder Host. Der Prototyp ist weder an die aktuelle Private-Alpha-Benutzerdatenbank noch an B2 bzw. den bisherigen SEC-01-Autoritätsfence gekoppelt. Er modelliert deshalb **nicht** die Sicherheit einer verteilten Autorisierung. Auch ein historisch akzeptierter Admission-Record autorisiert nicht automatisch einen zukünftigen Effekt. Ein widerrufener Grant stoppt neue Admissions, aber bereits zugelassene Vorgänge benötigen später eine eigene definierte Stornierungs-/Laufzeit-Semantik.

Offen bleiben insbesondere: authentifizierte Host-Registrierung, Bescheinigung der Executor-Identität, Ressourcen- und Policy-Grenzen, autoritative Grant-/Session-/Host-Epoch-Fences, Remote-Proof-Ausgabe, key rotation, Widerrufs-Reihenfolge über mehrere Systeme, fail-closed Effektausführung und überprüfbare Audits. Keine Interoperabilitäts- oder Produktionsfreigabe ableiten.

## Prüfung unter Windows PowerShell

```powershell
git pull --ff-only
python -B -m unittest discover -s tests/conformance -p "test_sec01_executor_host_admission.py" -v
python -B -m unittest discover -s tests/conformance -p "test_*.py"
python -B tests/conformance/validate_map_v01.py
git diff --check
git status --short
```

Zuletzt bestätigte Ausgangsbasis: **315/315**. Neu: **acht** Tests; erwartet **323/323** nach lokaler Validierung. Der Prototyp erfordert weder Gateway-Neustart noch neue Testkonten.
