# Private Alpha — Benutzerkonten, eigene Agenten und externe Beauftragungen

Status: **lokaler Simulationstest**, keine Tailscale-Serve-Freigabe, keine echten Agentenwirkungen, kein ComfyUI. Letzte bestätigte Baseline vor diesem Schritt: **308/308**. Die neuen Tests wurden noch nicht auf Windows bestätigt.

## Drei voneinander getrennte Begriffe

1. **Benutzerkonto:** Anmeldung mit der **Benutzer-ID** (`user.daniel`) und Passwort. Einladung und Registrierung schaffen ein Konto; **kein Agent ist erforderlich**. Eine Agenten-ID ist niemals ein Loginname.
2. **Eigener Agent:** Ein Benutzer darf mehrere Agenten anlegen, etwa `agent.daniel.images` und `agent.daniel.video`. Der Besitzer bleibt der registrierte Benutzer.
3. **Beauftragter externer Agent:** Ein anderer Benutzer kann einen fremden Agenten verwenden, **wenn dessen Eigentümer zuvor ausdrücklich eine Berechtigung erteilt hat**. Das ist keine Übertragung des Besitzes. Die aktuelle Simulation erlaubt ausschließlich `demo.echo` und einen explizit ausgewählten Agenten.

Die ID-Strings können identisch sein, aber Benutzer- und Agentenidentität bleiben typisiert und werden bei Autorisierung unterschieden. **Eine bekannte Agenten-ID allein ist nie ein Grant.** Grants sind separat gespeicherte, widerrufbare Beziehungen zwischen Agent, Auftraggeber und Aktion.

## Aktueller lokaler Ablauf

PowerShell A: Vorherigen Gateway mit `Ctrl+C` beenden und mit derselben Datenbank neu starten:

```powershell
$alphaDb = "$env:LOCALAPPDATA\Minglefield\private-alpha-v4.sqlite"
python -B server/private_alpha_gateway.py --auth-db $alphaDb --port 8767
```

PowerShell B: Für neue Personen eine Einladung **nur für das Benutzerkonto** ausstellen:

```powershell
$alphaDb = "$env:LOCALAPPDATA\Minglefield\private-alpha-v4.sqlite"
python -B server/private_alpha_admin.py --db $alphaDb invite user.friend
```

In `http://127.0.0.1:8767/`: Einladungscode und neues Passwort eintragen, **ohne Agenten-ID** registrieren. Danach unter **Agenten verwalten oder beauftragen** eigene Agenten anlegen. Bereits existierende Konten und Agenten sollen durch diese Änderung nicht gelöscht werden.

Ein Benutzer kann einen eigenen Agenten wie `agent.daniel.images` für `user.friend` freigeben. Der Friend sieht diesen Agenten unter seiner Auswahlliste mit Beziehung `delegated` und Original-Besitzer. Auftragsjobs bleiben im Auftragskonto sichtbar; die Eigentümerschaft des Agenten wird nicht verändert.

**Freigabe widerrufen** unterbindet neue Simulationsaufträge dieses Benutzers sofort bei der nächsten serverseitigen Jobprüfung. Bereits simulierte Jobs bleiben in der Historie. Die Seite bietet noch keine vollständige Grant-Übersicht, keine Berechtigungsrollen, keinen Marketplace und keine Zahlungen.

## Sicherheit und Datenmodell

- `alpha_users` und `alpha_agents` sind getrennte Tabellen.
- `alpha_agent_grants` enthält `agent_id`, `grantee_user_id`, `action` und `revoked`.
- Erstellung einer Freigabe erfordert gültige Benutzer-Session und Eigentum am aktiven Agenten.
- `submit_agent` kontrolliert in einer SQLite-Transaktion: gültige Session, aktives Besitzerkonto, aktiver Agent sowie entweder Eigentum oder nicht widerrufene, aktionsgebundene Freigabe.
- Ein fremder Benutzer darf keine Grants für einen Agenten erstellen, der ihm nicht gehört.
- Der Agentenbesitzer darf seine Delegation nicht als eigenes Fremdkonto ausgeben.
- Bestehende Demo-API-Aufrufe ohne `agent_id` bleiben vorerst aus Testkompatibilität erhalten, werden aber nicht als das geplante MAP-Delegationsprotokoll betrachtet.
- **Noch keine** echte agentenseitige Zustimmung, Agentenidentitätsnachweise, remote Capability-Ausgabe, Executor-Trust, selektive Ausgabe-/Datentrennung oder atomare Bindung an reale Effekte. SEC-01 bleibt CRITICAL/OPEN.

## Validierung (Windows PowerShell)

```powershell
git pull --ff-only
python -B -m unittest discover -s tests/conformance -p "test_private_alpha_multiagent_delegation.py" -v
python -B -m unittest discover -s tests/conformance -p "test_private_alpha_multiagent_http.py" -v
python -B -m unittest discover -s tests/conformance -p "test_private_alpha_password_http.py" -v
python -B -m unittest discover -s tests/conformance -p "test_*.py"
python -B tests/conformance/validate_map_v01.py
git diff --check
git status --short
```

Neue Tests: sechs Store-/Autorisierungstests und ein HTTP-End-to-End-Test. **Erwartet 315/315** vor erneuter Windows-Bestätigung.

## Für die spätere Private Alpha

Eigene und externe Agenten benötigen künftig mehrere Aktionstypen und klar beschriebene Delegationen (Gültigkeitsdauer, Limits, Widerruf, Auftragskosten, Ressourcenbesitz und Freigabe der Ausgabedaten). Die lokale `demo.echo`-Freigabe ist nur das erste Sicherheitsmodell. **Tailscale Serve und reale Effekte bleiben deaktiviert.**
