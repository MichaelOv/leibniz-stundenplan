# Leibniz Stundenplan

Automatisches System, das täglich den Vertretungsplan des Leibniz-Gymnasiums Gelsenkirchen mit dem regulären Untis-Stundenplan zusammenführt, speziell für Klasse 6c. Das Ergebnis ist ein fertiger Tagesplan als JSON-Datei, der im Web-Dashboard angezeigt wird. Bei Änderungen (Ausfall, Vertretung, Raumwechsel) wird automatisch eine Push-Benachrichtigung aufs Handy geschickt.

## Wie es funktioniert

Das System hat zwei Datenquellen:

1. **Untis-Stundenplan** (`parse_untis.py`): Der reguläre Wochenplan der Klasse wird von einer öffentlich zugänglichen HTML-Seite der Schule geladen. Er enthält für jeden Wochentag und jede Stunde Fach, Lehrkraft und Raum. Dieser Plan ändert sich selten und wird nur neu geladen, wenn sich die Seite geändert hat.

2. **Vertretungsplan** (`fetch_and_build.py`): Die Schule stellt täglich ein PDF über iServ bereit, das alle Vertretungen, Ausfälle und Raumänderungen für den jeweiligen Tag enthält. Die Vertretungspläne sind nicht öffentlich zugänglich und der Elternaccount hat keinen Zugriff darauf, daher wird ein Schüleraccount verwendet.

`build_today.py` gleicht dann beide Quellen ab: Für jede Stunde aus dem Untis-Plan wird geprüft, ob es im Vertretungsplan einen passenden Eintrag gibt. Wenn ja, wird der Status auf `vertretung`, `frei` oder `info` gesetzt. Das Ergebnis landet in `data/today_6c.json` und `data/tomorrow_6c.json`.

`run_all.py` orchestriert alle Schritte und schickt am Ende, falls es Änderungen gibt, eine Push-Benachrichtigung via [ntfy.sh](https://ntfy.sh).

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

Es gibt zwei Betriebsmodi: vollständig über GitHub Actions und GitHub Pages (kein eigener Server nötig) oder lokal auf einem eigenen Server.

---

### Option A: GitHub Actions + GitHub Pages

Der Workflow läuft komplett in der Cloud. GitHub Actions führt die Pipeline aus und committet die aktualisierten JSON-Dateien zurück ins Repository. Das Dashboard wird über GitHub Pages bereitgestellt.

#### 1. GitHub Secrets anlegen

Unter *Settings -> Secrets and variables -> Actions* drei Secrets anlegen:

| Secret | Inhalt |
|---|---|
| `ISERV_USER` | iServ-Benutzername (Schüleraccount) |
| `ISERV_PASS` | iServ-Passwort |
| `NTFY_TOPIC` | Frei gewählter Kanalname, z.B. `leibniz-6c-abc123` |

`NTFY_TOPIC` ist der Name des Kanals, den du in der ntfy-App abonnierst. Wähle etwas Einzigartiges, damit keine fremden Personen zufällig dieselben Benachrichtigungen erhalten.

#### 2. GitHub Pages aktivieren

Unter *Settings -> Pages -> Source: "Deploy from a branch" -> Branch: `main`, Folder: `/ (root)` -> Save*

Das Dashboard ist danach erreichbar unter `https://michaelov.github.io/leibniz-stundenplan/`

#### 3. ntfy-App einrichten

1. App installieren und öffnen
2. Neues Abonnement hinzufügen: den gewählten `NTFY_TOPIC`-Namen eingeben, Server bleibt `ntfy.sh`
3. Fertig, Benachrichtigungen kommen nun automatisch an

#### 4. Workflow testen

Unter *Actions -> Update timetable -> Run workflow* kann der Workflow manuell gestartet werden. Bei Erfolg werden die JSON-Dateien in `data/` aktualisiert und committed.

#### Zeitplan

Der Workflow läuft automatisch montags bis freitags (alle Zeiten MESZ):

- **6:30 bis 9:00 Uhr:** alle 5 Minuten, da sich der Plan morgens häufig kurzfristig ändert
- **9:00 bis 22:00 Uhr:** stündlich

Hinweis: GitHub Actions garantiert keine sekundengenaue Ausführung, Verzögerungen von einigen Minuten sind möglich.

---

### Option B: Lokaler Server

Das System läuft auf einem eigenen Rechner oder Server. Der Cron-Job übernimmt die Automatisierung, `server.py` stellt das Dashboard bereit.

#### 1. Python-Umgebung einrichten

```bash
cd leibniz-stundenplan
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### 2. Zugangsdaten hinterlegen

Eine Datei `.env` im Projektordner anlegen:

```
ISERV_USER=vorname.nachname
ISERV_PASS=dein-passwort
NTFY_TOPIC=leibniz-6c-abc123
```

#### 3. ntfy-App einrichten

1. App installieren und öffnen
2. Neues Abonnement hinzufügen: den gewählten `NTFY_TOPIC`-Namen eingeben, Server bleibt `ntfy.sh`
3. Fertig, Benachrichtigungen kommen nun automatisch an

#### 4. Cron-Job einrichten

```bash
crontab -e
```

Folgende Einträge hinzufügen (Pfad anpassen):

```
# Morgens alle 5 Minuten (6:30 bis 8:55)
30,35,40,45,50,55 6 * * 1-5 cd /pfad/zu/leibniz-stundenplan && venv/bin/python scripts/run_all.py >> /tmp/stundenplan.log 2>&1
*/5 7-8 * * 1-5 cd /pfad/zu/leibniz-stundenplan && venv/bin/python scripts/run_all.py >> /tmp/stundenplan.log 2>&1

# Tagsüber stündlich (9:00 bis 22:00)
0 9-22 * * 1-5 cd /pfad/zu/leibniz-stundenplan && venv/bin/python scripts/run_all.py >> /tmp/stundenplan.log 2>&1
```

Die Jobs laufen nur montags bis freitags (`1-5`). Ab 9 Uhr schaltet `run_all.py` automatisch auf den Plan für morgen um. Die Ausgabe wird in `/tmp/stundenplan.log` gespeichert.

Hinweis für Alpine Linux: Die `30,35,...,55 6`-Zeile ist absichtlich ausgeschrieben, da busybox crond mit der Schreibweise `30-59/5` manchmal Probleme hat.

#### 5. Dashboard starten

```bash
venv/bin/python server.py
```

Danach im Browser öffnen: [http://localhost:8080](http://localhost:8080)

Das Dashboard liest die JSON-Dateien aus `data/` und aktualisiert sich automatisch alle 5 Minuten.

---

## Benachrichtigungslogik

Das System unterscheidet, ob es eher morgens oder tagsüber läuft:

- **Vor 09:00 Uhr:** Benachrichtigung bezieht sich auf **heute**, damit man noch vor der Schule weiß, ob etwas ausfällt.
- **Ab 09:00 Uhr:** Benachrichtigung bezieht sich auf **morgen**, da der heutige Tag bereits läuft.

Damit keine doppelten Benachrichtigungen verschickt werden, wird ein MD5-Hash des Benachrichtigungsinhalts gespeichert. Nur wenn sich der Inhalt gegenüber der letzten Benachrichtigung geändert hat, wird eine neue verschickt.

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

## Abhängigkeiten

| Paket | Zweck |
|---|---|
| `requests` | HTTP-Anfragen (iServ-Login, Untis, ntfy) |
| `beautifulsoup4` | HTML-Parsing des Untis-Stundenplans |
| `pymupdf` | Text-Extraktion aus dem Vertretungsplan-PDF |
| `python-dotenv` | Laden der Zugangsdaten aus der `.env`-Datei |
| `flask` | HTTP-Server für das lokale Dashboard (Option B) |
