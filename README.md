# Leibniz Stundenplan

Automatisches System, das den Vertretungsplan des Leibniz-Gymnasiums Gelsenkirchen mit dem regulären Untis-Stundenplan zusammenführt, aktuell für Klasse 7c. Das Ergebnis wird in einem Web-Dashboard angezeigt (Tages- und Wochenansicht) und bei Änderungen als Push-Benachrichtigung aufs Handy geschickt.

## Wie es funktioniert

Das System hat zwei Datenquellen:

1. **Untis-Stundenplan** (`parse_untis.py`): Der reguläre Wochenplan der Klasse wird von einer öffentlich zugänglichen HTML-Seite der Schule geladen. Er enthält für jeden Wochentag und jede Stunde Fach, Lehrkraft und Raum. Er ändert sich selten und wird nur neu geladen, wenn sich die Seite geändert hat.

2. **Vertretungsplan** (`fetch_and_build.py`): Die Schule stellt pro Tag ein PDF über iServ bereit. Die Vertretungspläne sind nicht öffentlich zugänglich und der Elternaccount hat keinen Zugriff darauf, daher wird ein Schüleraccount verwendet.

`build_today.py` gleicht beide Quellen ab: Für jede Stunde aus dem Untis-Plan wird geprüft, ob es im Vertretungsplan einen passenden Eintrag gibt. Wenn ja, wird der Status auf `vertretung`, `frei` oder `info` gesetzt. `build_week.py` baut daraus zusätzlich die Wochenübersicht.

`run_all.py` orchestriert alle Schritte und schickt am Ende eine Push-Benachrichtigung via [ntfy.sh](https://ntfy.sh), sobald sich etwas geändert hat.

```
iServ PDF (Vertretungsplan)  ->  fetch_and_build.py  ->  latest_7c.json
                                                         latest_7c_tomorrow.json
                                                         latest_7c_extra_<datum>.json
Untis HTML (Wochenplan)      ->  parse_untis.py      ->  untis_7c.json / untis_7c_prev.json
                                           |
                               build_today.py        ->  today_7c.json / tomorrow_7c.json
                               build_week.py         ->  week_7c.json
                                           |
                                 notify.py           ->  ntfy.sh Push-Benachrichtigung
```

### Besondere Fälle

**Neuer Untis-Plan vor Gültigkeitsdatum**
Schulen veröffentlichen den Stundenplan für die nächste Woche manchmal schon mittwochs. Die HTML-Seite enthält ein `(ab DD.MM.YY)`-Datum, das als `valid_from` in `untis_7c.json` landet. Der alte Plan wird als `untis_7c_prev.json` gesichert und verwendet, solange das Zieldatum vor `valid_from` liegt.

**Veralteter Stundenplan (Stale-Guard)**
`parse_untis.py` liest das Schuljahr aus dem HTML mit. Passt es nicht zum aktuellen Datum, etwa weil die Schule nach den Ferien noch den alten Plan online hat, wird `untis_stale` gesetzt und das Dashboard zeigt eine deutliche Warnung. Vertretungen bleiben dabei gültig, nur die regulären Stunden sind fraglich.

**Doppelstunden**
Untis stellt Doppelstunden als zusammengefasste Tabellenzelle dar. `parse_untis.py` erkennt das und trägt die Stunde in beiden Slots ein. Das ist fehleranfällig, deshalb prüft `tests/test_parsing.py` das komplette Wochenraster gegen einen echten, gespeicherten Untis-Export.

**Verschobene und vorgezogene Stunden**
Steht im Vertretungsplan "frei; verlegt auf X. Std.", wird die Zielstunde mit Fach und Lehrkraft der verschobenen Stunde aktualisiert. Umgekehrt nennen Hinweise wie "E statt Do. 10.9. 1. Std." das Fach einer vorgezogenen Stunde, auch wenn an dem Tag regulär gar kein Unterricht wäre.

**Kein Vertretungsplan verfügbar**
Ist für einen Tag kein PDF abrufbar (Ferien, Wochenende, noch nicht hochgeladen), antwortet der Server mit 404. Das ist ein erwarteter Fall und kein Fehler: Es wird der reguläre Untis-Plan angezeigt, der Lauf bleibt grün.

## Dashboard

Erreichbar über GitHub Pages, lokal über `server.py` auf Port 8080.

- **Drei Reiter:** der laufende Schultag, der Folgetag und die **Woche** (Standardansicht). Die Wochenansicht zeigt ab 720px ein Raster, auf dem Handy Tageskarten, beides aus demselben Markup.
- **Jetzt, Pause und Schluss:** Die laufende Stunde wird hervorgehoben, dazu Restzeit sowie Beginn und Ende des Tages. Weicht das vom regulären Rahmen ab, steht es dabei ("Schluss 12:50, eine Stunde früher"). In der Pause steht dort "Pause bis 10:15, danach 3. Std Sport", und die kommende Stunde ist schwächer markiert als eine laufende.
- **Fachfarben:** exakt die Farben aus dem Untis-Export der Schule. Im dunklen Design abgedunkelt, damit die Vollton-Farben nicht blenden.
- **Kurswahl:** Der Untis-Plan listet alle Parallelkurse der Klasse (Latein/Französisch, die Religionen). Über den Knopf *Kurse* lässt sich auswählen, welche belegt sind. Die Auswahl wird im Browser gespeichert und gilt nur auf dem jeweiligen Gerät, die Push-Nachrichten bleiben ungefiltert.
- **PWA:** Die Seite ist aufs Handy installierbar und offline nutzbar. Plandaten werden dabei immer zuerst aus dem Netz geladen, der Cache dient nur als Rückfallebene, damit nie ein veralteter Plan angezeigt wird.

Barrierefreiheit: getestet gegen WCAG 2.2 AA (axe-core ohne Befund), Tastaturbedienung der Reiter nach WAI-ARIA-Pattern.

## Voraussetzungen

- **iServ-Schüleraccount** des Leibniz-Gymnasiums. Die Vertretungspläne sind nicht öffentlich zugänglich und der Elternaccount hat keinen Zugriff darauf.
- **ntfy-App** auf dem Handy ([Android](https://play.google.com/store/apps/details?id=io.heckel.ntfy) / [iOS](https://apps.apple.com/app/ntfy/id1625396347)) für die Push-Benachrichtigungen

## Einrichtung

Der **GitHub Actions Workflow** übernimmt die Pipeline (PDFs laden, parsen, JSON bauen, committen). Ein **lokaler Cron-Job** triggert ihn zum richtigen Zeitpunkt.

> **Warum kein reiner GitHub Actions Schedule?**
> GitHub führt Scheduled Workflows auf kostenlosen Repos häufig mit 30 bis 60 Minuten Verspätung aus oder überspringt sie. Für einen Schulplan, der morgens um 6:30 aktuell sein soll, ist das nicht brauchbar. Der lokale Cron-Job triggert per `workflow_dispatch`, das läuft sofort.

---

### Schritt 1: GitHub Secrets anlegen

Unter *Settings -> Secrets and variables -> Actions* drei Secrets anlegen:

| Secret | Inhalt |
|---|---|
| `ISERV_USER` | iServ-Benutzername (Schüleraccount) |
| `ISERV_PASS` | iServ-Passwort |
| `NTFY_TOPIC` | Frei gewählter Kanalname, z.B. `leibniz-7c-abc123` |

`NTFY_TOPIC` ist der Kanal, den du in der ntfy-App abonnierst. Wähle etwas Einzigartiges: ntfy.sh-Kanäle sind ohne Anmeldung les- und beschreibbar, wer den Namen kennt, sieht die Nachrichten. Deshalb steht das Topic auch bewusst **nicht** im Repository.

---

### Schritt 2: GitHub Pages aktivieren

Unter *Settings -> Pages -> Source: "Deploy from a branch" -> Branch: `main`, Folder: `/ (root)` -> Save*

Das Dashboard ist danach erreichbar unter `https://<github-username>.github.io/leibniz-stundenplan/`

---

### Schritt 3: ntfy-App einrichten

1. App installieren und öffnen
2. Neues Abonnement hinzufügen: den gewählten `NTFY_TOPIC`-Namen eingeben, Server bleibt `ntfy.sh`

---

### Schritt 4: Lokalen Cron-Job einrichten

Auf dem Server muss die [GitHub CLI](https://cli.github.com/) installiert und einmalig mit `gh auth login` authentifiziert sein.

```bash
crontab -e
```

```
# Leibniz Stundenplan - GitHub Workflow triggern (CEST)
# Morgens alle 5 Minuten 6:30-8:55
30,35,40,45,50,55 6 * * 1-5 HOME=/root /usr/bin/gh workflow run update.yml --repo <github-username>/leibniz-stundenplan
*/5 7-8 * * 1-5 HOME=/root /usr/bin/gh workflow run update.yml --repo <github-username>/leibniz-stundenplan
# Stündlich 9:00-22:00
0 9-22 * * 1-5 HOME=/root /usr/bin/gh workflow run update.yml --repo <github-username>/leibniz-stundenplan
```

`<github-username>` ersetzen. Die Zeiten sind lokale Serverzeit. `HOME=/root` stellt sicher, dass `gh` die Anmeldedaten findet.

---

### Workflow manuell starten

Unter *Actions -> Update timetable -> Run workflow* oder per CLI:

```bash
gh workflow run update.yml --repo <github-username>/leibniz-stundenplan
```

---

## Welche Pläne wann geladen werden

Nicht jeder Lauf lädt alles. Die PDF-Stände zeigen, dass die Schule morgens ausschließlich den laufenden Tag aktualisiert (beobachtet 06:07, 07:28, 08:17) und die Folgetage nachmittags veröffentlicht (13:33, 15:09, 16:52).

| Tag | Wann abgerufen |
|---|---|
| heute | bei jedem Lauf |
| morgen | bei jedem Lauf |
| übrige Schultage der Woche | erst ab 9:00, also nur in den stündlichen Läufen (`WEEK_FETCH_FROM_HOUR`) |

Das spart gegenüber "immer alles" rund 40 Prozent der Abrufe, ohne später informiert zu sein. Damit die schon bekannten Vertretungen der späteren Tage morgens nicht aus der Wochenansicht fallen, übernimmt `build_week.py` sie aus dem bisherigen Stand.

## Fehlerüberwachung

| Situation | Verhalten |
|---|---|
| Kein PDF für den Tag (404) | Regulärer Untis-Plan wird angezeigt, kein Alarm |
| Login fehlgeschlagen | Workflow schlägt fehl → GitHub sendet Failure-E-Mail |
| Netzwerkfehler | Workflow schlägt fehl → GitHub sendet Failure-E-Mail |
| Unerwartete Exception | Workflow schlägt fehl → GitHub sendet Failure-E-Mail |
| Abruf eines späteren Wochentags scheitert | wird übersprungen, Pipeline läuft weiter |

Zusätzlich protokolliert jeder Lauf, welche Klassen das PDF enthält. Damit lässt sich im Log unterscheiden, ob es für die Klasse wirklich keine Vertretung gibt oder ob sie nur nicht erkannt wurde:

```
Klassen im PDF: 05a(2), 07c(1), 08a(3)
Keine Vertretung fuer 07c in diesem PDF.
```

## Benachrichtigungslogik

Die Benachrichtigung enthält immer den **kompletten Tagesplan**, nicht nur die geänderten Stunden. Ausfälle mit ❌, Vertretungen mit 🔄, Infos mit 📋.

Worauf sie sich bezieht:

- **Vor 09:00:** auf **heute**, damit man vor der Schule weiß, ob etwas ausfällt.
- **Ab 09:00:** auf den **nächsten Schultag**, der laufende Tag hat ja schon begonnen.

Damit keine Dubletten verschickt werden, wird ein Hash des Inhalts pro Tag gespeichert. Nur bei geändertem Inhalt geht eine neue Nachricht raus. Wird eine gemeldete Änderung von der Schule **zurückgenommen**, kommt eine Nachricht "Wieder regulär", damit man sich nicht nach einem Ausfall richtet, den es nicht mehr gibt.

Anzeige und Benachrichtigung sind bewusst getrennt: Das Dashboard zeigt den laufenden Schultag, damit die aktuelle Stunde markiert werden kann, und wechselt erst **nach der letzten Stunde** auf den nächsten Schultag. Das Unterrichtsende wird aus dem Stundenplan des jeweiligen Wochentags bestimmt, nicht aus einer festen Uhrzeit.

## Dashboard-Zeitstempel

- **Stand X Uhr** (oben): Zeitpunkt, zu dem die Schule den Vertretungsplan veröffentlicht hat, direkt aus dem PDF-Text gelesen.
- **Zuletzt geprüft: X Uhr** (unten): Zeitpunkt des letzten Laufs.

## Konfiguration

### Fächernamen (`data/fach_mapping.json`)

Untis verwendet Kürzel, die im Dashboard nicht selbsterklärend sind:

```json
{ "D": "Deutsch", "M": "Mathe", "SPSW": "Sport Schwimmen" }
```

Ein unbekanntes Kürzel wird unverändert angezeigt. Taucht eines auf, gehört es hier ergänzt.

### Lehrer-Fach-Zuordnung (`data/lehrer_fach.json`)

Manche Vertretungseinträge enthalten nur das Lehrerkürzel, aber kein Fach. Diese Datei ordnet bekannte Kürzel einem Fach zu:

```json
{ "EBR": "RE", "AVS": "IR" }
```

### Lehrernamen (`data/lehrer_namen.json`)

Optional. Ist ein Klarname hinterlegt, zeigt das Dashboard ihn mit dem Kürzel als Zusatz. Leere Werte bedeuten: nur das Kürzel anzeigen.

```json
{ "GRU": "Frau Gruber", "MAT": "" }
```

### Klasse oder Schule wechseln

| Was | Datei | Variable/Wert |
|---|---|---|
| Zielklasse (Vertretungsplan) | `scripts/fetch_and_build.py` | `TARGET_CLASS = "07c"` |
| Untis-URL | `scripts/parse_untis.py` | `UNTIS_URL` |
| Untis-URL (Änderungsprüfung) | `scripts/run_all.py` | in `untis_html_changed()` |
| iServ-Basis-URL | `scripts/fetch_and_build.py` | `BASE_URL` |
| Dateinamen `*_7c.json` | `scripts/*.py`, `index.html`, `.gitignore` | |
| Beschriftung | `index.html` | Titel, Kopfzeile, Fußzeile |
| ntfy-Topic | GitHub Secret | `NTFY_TOPIC` |

Die Klassenerkennung im PDF vergleicht den Jahrgang numerisch, "7c" und "07c" werden also beide gefunden.

### Stundenzeiten

Beginn und Ende der Stunden stehen in `scripts/constants.py` (`STUNDEN_ZEITEN`) für die Umschaltung nach Unterrichtsende und in `index.html` (`ZEITEN`) für die Anzeige. Ändert die Schule die Zeiten, müssen **beide** angepasst werden.

## Entwicklung

```bash
python3 -m venv venv
venv/bin/pip install -r requirements-dev.txt
venv/bin/python -m pytest -q          # 123 Tests
venv/bin/python server.py             # Dashboard auf Port 8080
```

Die Tests decken die heuristischen Teile ab, also genau die Stellen, die bei geändertem PDF- oder HTML-Layout still falsche Ergebnisse liefern könnten: PDF-Zerlegung, Klassenerkennung, Fach- und Vertretungslogik, Doppelstunden und die Abruf- und Benachrichtigungssteuerung. `tests/fixtures/` enthält dafür einen echten Untis-Export.

Einzelne Schritte lassen sich mit einem Datum aufrufen:

```bash
venv/bin/python scripts/fetch_and_build.py 2026-09-10 latest_7c.json
venv/bin/python scripts/build_today.py     2026-09-10 today_7c.json latest_7c.json
venv/bin/python scripts/build_week.py      2026-09-10 week_7c.json
```

## Abhängigkeiten

| Paket | Zweck |
|---|---|
| `requests` | HTTP-Anfragen (iServ-Login, Untis, ntfy) |
| `beautifulsoup4` | HTML-Parsing des Untis-Stundenplans |
| `pymupdf` | Text-Extraktion aus dem Vertretungsplan-PDF |
| `python-dotenv` | Laden der Zugangsdaten aus der `.env`-Datei |
| `flask` | HTTP-Server für das lokale Dashboard (nur `requirements-dev.txt`) |
| `pytest` | Tests (nur `requirements-dev.txt`) |

Die Pipeline selbst braucht `flask` nicht, es wird nur für das lokale Dashboard verwendet.
