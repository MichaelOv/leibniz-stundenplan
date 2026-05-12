# Leibniz Stundenplan

Automatisches System, das täglich den Vertretungsplan des Leibniz-Gymnasiums Gelsenkirchen mit dem regulären Untis-Stundenplan zusammenführt, speziell für Klasse 6c. Das Ergebnis ist ein fertiger Tagesplan als JSON-Datei, der im Web-Dashboard angezeigt wird. Bei Änderungen (Ausfall, Vertretung, Raumwechsel) wird automatisch eine Push-Benachrichtigung aufs Handy geschickt.

## Wie es funktioniert

Das System hat zwei Datenquellen:

1. **Untis-Stundenplan** (`parse_untis.py`): Der reguläre Wochenplan der Klasse wird von einer öffentlich zugänglichen HTML-Seite der Schule geladen. Er enthält für jeden Wochentag und jede Stunde Fach, Lehrkraft und Raum. Dieser Plan ändert sich selten und wird nur neu geladen, wenn sich die Seite geändert hat.

2. **Vertretungsplan** (`fetch_and_build.py`): Die Schule stellt täglich ein PDF über iServ bereit, das alle Vertretungen, Ausfälle und Raumänderungen für den jeweiligen Tag enthält. Die Vertretungspläne sind nicht öffentlich zugänglich und der Elternaccount hat keinen Zugriff darauf, daher wird ein Schüleraccount verwendet.

`build_today.py` gleicht dann beide Quellen ab: Für jede Stunde aus dem Untis-Plan wird geprüft, ob es im Vertretungsplan einen passenden Eintrag gibt. Wenn ja, wird der Status auf `vertretung`, `frei` oder `info` gesetzt. Das Ergebnis landet in `data/today_6c.json` und `data/tomorrow_6c.json`.

`run_all.py` orchestriert alle Schritte und schickt am Ende eine Push-Benachrichtigung via [ntfy.sh](https://ntfy.sh), sobald Änderungen vorliegen.

```
iServ PDF (Vertretungsplan)  ->  fetch_and_build.py  ->  latest_6c.json
Untis HTML (Wochenplan)      ->  parse_untis.py      ->  untis_6c.json
                                           |
                               build_today.py        ->  today_6c.json / tomorrow_6c.json
                                           |
                                 notify.py           ->  ntfy.sh Push-Benachrichtigung
```

## Voraussetzungen

- **iServ-Schüleraccount** des Leibniz-Gymnasiums. Die Vertretungspläne sind nicht öffentlich zugänglich und der Elternaccount hat keinen Zugriff darauf.
- **ntfy-App** auf dem Handy ([Android](https://play.google.com/store/apps/details?id=io.heckel.ntfy) / [iOS](https://apps.apple.com/app/ntfy/id1625396347)), um Push-Benachrichtigungen zu empfangen

## Einrichtung

Das System besteht aus zwei Teilen: Der **GitHub Actions Workflow** übernimmt die eigentliche Pipeline (PDF laden, parsen, JSON bauen, committen). Ein **lokaler Cron-Job** auf einem eigenen Server triggert diesen Workflow zum richtigen Zeitpunkt.

> **Warum kein reiner GitHub Actions Schedule?**
> GitHub Actions führt Scheduled Workflows auf kostenlosen Repos häufig mit Verspätungen von 30-60 Minuten aus oder überspringt Ausführungen ganz, wenn die Runner ausgelastet sind. Für einen Schulplan, der morgens zuverlässig um 6:30 Uhr aktuell sein soll, ist das nicht brauchbar. Der lokale Cron-Job triggert den Workflow per `workflow_dispatch`, was sofort und zuverlässig ausgeführt wird.

---

### Schritt 1: GitHub Secrets anlegen

Unter *Settings -> Secrets and variables -> Actions* drei Secrets anlegen:

| Secret | Inhalt |
|---|---|
| `ISERV_USER` | iServ-Benutzername (Schüleraccount) |
| `ISERV_PASS` | iServ-Passwort |
| `NTFY_TOPIC` | Frei gewählter Kanalname, z.B. `leibniz-6c-abc123` |

`NTFY_TOPIC` ist der Name des Kanals, den du in der ntfy-App abonnierst. Wähle etwas Einzigartiges, damit keine fremden Personen zufällig dieselben Benachrichtigungen erhalten.

---

### Schritt 2: GitHub Pages aktivieren

Unter *Settings -> Pages -> Source: "Deploy from a branch" -> Branch: `main`, Folder: `/ (root)` -> Save*

Das Dashboard ist danach erreichbar unter `https://<github-username>.github.io/leibniz-stundenplan/`

---

### Schritt 3: ntfy-App einrichten

1. App installieren und öffnen
2. Neues Abonnement hinzufügen: den gewählten `NTFY_TOPIC`-Namen eingeben, Server bleibt `ntfy.sh`
3. Fertig, Benachrichtigungen kommen nun automatisch an

Das Dashboard zeigt in der Topbar einen "ntfy abonnieren"-Button, der direkt zum konfigurierten Kanal verlinkt. Er erscheint automatisch, sobald `run_all.py` einmal gelaufen ist und `data/config.json` erstellt hat.

---

### Schritt 4: Lokalen Cron-Job einrichten

Auf dem Server muss die [GitHub CLI](https://cli.github.com/) installiert und einmalig mit `gh auth login` authentifiziert sein.

```bash
crontab -e
```

Folgende Einträge hinzufügen:

```
# Leibniz Stundenplan - GitHub Workflow triggern (CEST)
# Morgens alle 5 Minuten 6:30-8:55
30,35,40,45,50,55 6 * * 1-5 HOME=/root /usr/bin/gh workflow run update.yml --repo <github-username>/leibniz-stundenplan
*/5 7-8 * * 1-5 HOME=/root /usr/bin/gh workflow run update.yml --repo <github-username>/leibniz-stundenplan
# Stündlich 9:00-22:00
0 9-22 * * 1-5 HOME=/root /usr/bin/gh workflow run update.yml --repo <github-username>/leibniz-stundenplan
```

`<github-username>` durch den tatsächlichen GitHub-Benutzernamen ersetzen. Die Zeiten sind in lokaler Serverzeit (CEST/MEZ). `HOME=/root` stellt sicher, dass `gh` die gespeicherten Anmeldedaten findet.

---

### Workflow manuell starten

Unter *Actions -> Update timetable -> Run workflow* oder per CLI:

```bash
gh workflow run update.yml --repo <github-username>/leibniz-stundenplan
```

---

## Benachrichtigungslogik

Die Benachrichtigung enthält immer den **kompletten Tagesplan** der Klasse, nicht nur die geänderten Stunden. Ausgefallene Stunden werden mit ❌, Vertretungen mit 🔄 und Info-Einträge mit 📋 markiert.

`run_all.py` bestimmt automatisch, für welchen Tag benachrichtigt wird:

- **Vor 09:00 Uhr:** Benachrichtigung bezieht sich auf **heute**, damit man noch vor der Schule weiß, ob etwas ausfällt.
- **Ab 09:00 Uhr:** Benachrichtigung bezieht sich auf **morgen**, da der heutige Tag bereits läuft.

Damit keine doppelten Benachrichtigungen verschickt werden, wird ein MD5-Hash des Benachrichtigungsinhalts gespeichert. Nur wenn sich der Inhalt gegenüber der letzten Benachrichtigung geändert hat, wird eine neue verschickt.

---

## Dashboard-Zeitstempel

Das Dashboard zeigt zwei Zeitstempel:

- **Stand X Uhr** (oben): Zeitpunkt, zu dem die Schule den Vertretungsplan veröffentlicht hat. Wird direkt aus dem PDF-Text ausgelesen, nicht aus dem HTTP-Header.
- **Zuletzt geprüft: X Uhr** (unten): Zeitpunkt, zu dem `run_all.py` zuletzt gelaufen ist.

---

## Konfiguration

### Fächernamen anpassen (`data/fach_mapping.json`)

Untis verwendet interne Kürzel (z.B. `SPSW`), die im Dashboard nicht selbsterklärend sind. Diese Datei übersetzt sie in lesbare Namen:

```json
{
  "D":    "Deutsch",
  "M":    "Mathe",
  "SPSW": "Sport Schwimmen"
}
```

Einträge können jederzeit ergänzt oder geändert werden, ohne Code-Änderung.

### Lehrer-Fach-Zuordnung (`data/lehrer_fach.json`)

Manche Vertretungsplan-Einträge enthalten nur das Lehrerkürzel, aber kein Fach. Diese Datei ordnet bekannte Lehrerkürzel einem Fachkürzel zu, damit das Fach trotzdem angezeigt werden kann:

```json
{
  "EBR": "RE",
  "AVS": "IR"
}
```

### Klasse oder Schule wechseln

Das System ist auf Klasse 6c des Leibniz-Gymnasiums Gelsenkirchen ausgerichtet. Für eine andere Klasse oder Schule müssen folgende Stellen angepasst werden:

| Was | Datei | Variable/Wert |
|---|---|---|
| Zielklasse (Vertretungsplan) | `scripts/fetch_and_build.py` | `TARGET_CLASS = "06c"` |
| Untis-URL | `scripts/parse_untis.py` | `UNTIS_URL` |
| iServ-Basis-URL | `scripts/fetch_and_build.py` | `BASE_URL` |
| ntfy-Topic | `.env` oder GitHub Secret | `NTFY_TOPIC` |

---

## Abhängigkeiten

| Paket | Zweck |
|---|---|
| `requests` | HTTP-Anfragen (iServ-Login, Untis, ntfy) |
| `beautifulsoup4` | HTML-Parsing des Untis-Stundenplans |
| `pymupdf` | Text-Extraktion aus dem Vertretungsplan-PDF |
| `python-dotenv` | Laden der Zugangsdaten aus der `.env`-Datei |
| `flask` | HTTP-Server für das lokale Dashboard |
