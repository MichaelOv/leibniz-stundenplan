#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import requests
from pathlib import Path
from datetime import datetime, date, timezone, timedelta
from zoneinfo import ZoneInfo

_TZ_BERLIN = ZoneInfo("Europe/Berlin")
from notify import send_ntfy
from constants import DAYS_DE, NOTIFY_HOUR_CUTOFF

BASE = Path(__file__).resolve().parent
PYTHON = sys.executable
DATA = BASE.parent / "data"

def get_today():
    """Aktueller Schultag fuer die Anzeige: heute, am Wochenende der Montag.

    Bewusst ohne Uhrzeit-Logik. Frueher sprang diese Funktion ab 9 Uhr auf den
    Folgetag, weil sie zugleich das Ziel der Benachrichtigung bestimmte. Damit
    zeigte das Dashboard waehrend des Unterrichts nicht mehr den laufenden Tag
    und konnte die aktuelle Stunde nicht markieren. Fuer die Benachrichtigung
    gibt es jetzt notify_ziel().
    """
    candidate = datetime.now(_TZ_BERLIN).date()
    while candidate.weekday() > 4:
        candidate += timedelta(days=1)
    return candidate.isoformat()

def get_tomorrow(today_str):
    d = date.fromisoformat(today_str) + timedelta(days=1)
    while d.weekday() > 4:
        d += timedelta(days=1)
    return d.isoformat()

def notify_ziel(today_str, tomorrow_str):
    """Tag, auf den sich die Push-Benachrichtigung bezieht.

    Vor 9 Uhr der laufende Tag (man will vor der Schule wissen, was ausfaellt),
    danach der naechste Schultag. Unveraendertes Verhalten, nur von der
    Anzeigelogik getrennt.
    """
    now = datetime.now(_TZ_BERLIN)
    if now.date().weekday() > 4 or now.hour >= NOTIFY_HOUR_CUTOFF:
        return tomorrow_str
    return today_str

def run(script, *args) -> int:
    """Gibt den Exit-Code zurück: 0=OK, 1=kein Plan verfügbar, 2=echter Fehler."""
    cmd = [PYTHON, str(BASE / script)] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout.strip())
    if result.returncode != 0:
        print("FEHLER in " + script + ": " + result.stderr.strip())
    return result.returncode

def untis_html_changed():
    try:
        r = requests.head(
            "https://leibniz-gymnasium.net/files/stpl/Kla1A_07c.htm",
            timeout=10
        )
        last_mod = r.headers.get("Last-Modified", "")
        cache = DATA / "untis_last_modified.txt"
        if cache.exists() and cache.read_text().strip() == last_mod:
            return False
        cache.write_text(last_mod)
        return True
    except Exception as e:
        print("Warnung: Untis-Check fehlgeschlagen: " + str(e))
        return True

def prune_old_hashes(keep_days=14):
    """Löscht datierte last_ntfy_hash_YYYY-MM-DD.txt, die älter als keep_days sind."""
    cutoff = datetime.now(_TZ_BERLIN).date() - timedelta(days=keep_days)
    for f in DATA.glob("last_ntfy_hash_*.txt"):
        stamp = f.stem.replace("last_ntfy_hash_", "")
        try:
            if date.fromisoformat(stamp) < cutoff:
                f.unlink()
        except ValueError:
            continue  # nicht-datierte Datei (z.B. _today) überspringen

def vtg_has_entries(json_file) -> bool:
    try:
        with open(DATA / json_file) as f:
            data = json.load(f)
        return len(data.get("substitutions", [])) > 0
    except FileNotFoundError:
        return False
    except (json.JSONDecodeError, OSError) as e:
        print(f"Warnung: {json_file} konnte nicht gelesen werden: {e}")
        return False

def build_and_notify(target, out_file, label, vtg_file="latest_7c.json", notify=True):
    print(f"=== {label}: Tagesplan zusammenfuehren ===")
    result = subprocess.run(
        [PYTHON, str(BASE / "build_today.py"), target, out_file, vtg_file],
        capture_output=True, text=True
    )
    print(result.stdout.strip())
    if result.returncode != 0:
        return

    try:
        with open(DATA / out_file) as f:
            plan_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Warnung: {out_file} konnte nicht gelesen werden: {e}")
        return

    alle_stunden = plan_data.get("plan", [])
    aenderungen = [p for p in alle_stunden if p["status"] in ("frei", "vertretung", "info")]

    if aenderungen:
        msg_zeilen = []
        for p in alle_stunden:
            mark = f" [{p['status'].upper()}]" if p["status"] != "normal" else ""
            vtg_str = f" -> {p['vertreter']}" if p["vertreter"] else ""
            hinweis = f" | {p['hinweis']}" if p["hinweis"] else ""
            line = f"Std {p['stunde']} {p['fach']} ({p['lehrer']}) {p['raum']}{mark}{vtg_str}{hinweis}"
            if p["status"] == "frei":
                msg_zeilen.append("❌ " + line)
            elif p["status"] == "vertretung":
                msg_zeilen.append("🔄 " + line)
            elif p["status"] == "info":
                msg_zeilen.append("📋 " + line)
            else:
                msg_zeilen.append("   " + line)

        if notify:
            d = date.fromisoformat(target)
            day_label = DAYS_DE[d.weekday()] + " " + str(d.day) + "." + str(d.month) + "."
            ok = send_ntfy(
                title="Änderung 7c " + day_label,
                msg="\n".join(msg_zeilen),
                priority=3,
                hash_suffix=target
            )
            if ok:
                print("Benachrichtigung gesendet!")
    else:
        print("Keine Änderungen – keine Benachrichtigung.")

if __name__ == "__main__":
    DATA.mkdir(exist_ok=True)
    # Manuelles Datum möglich: python run_all.py 2026-05-07
    manual = sys.argv[1] if len(sys.argv) > 1 else None
    today = manual or get_today()
    tomorrow = get_tomorrow(today)

    # Bewusst nur heute und morgen abrufen: die Schule veroeffentlicht praktisch
    # nicht weiter im Voraus, und die Pipeline laeuft morgens alle 5 Minuten.
    # Die Wochenuebersicht (Schritt 6) nutzt genau diese beiden Dateien und
    # zeigt fuer die uebrigen Tage den regulaeren Plan.
    print("=== Schritt 1: Vertretungsplan heute laden (" + today + ") ===")
    rc1 = run("fetch_and_build.py", today, "latest_7c.json")
    if rc1 == 2:
        print("KRITISCHER FEHLER in Schritt 1 – Pipeline abgebrochen.")
        sys.exit(2)

    print("=== Schritt 2: Vertretungsplan morgen laden (" + tomorrow + ") ===")
    rc2 = run("fetch_and_build.py", tomorrow, "latest_7c_tomorrow.json")
    if rc2 == 2:
        print("KRITISCHER FEHLER in Schritt 2 – Pipeline abgebrochen.")
        sys.exit(2)

    print("=== Schritt 3: Untis-Stundenplan laden ===")
    if untis_html_changed():
        if run("parse_untis.py") == 2:
            print("KRITISCHER FEHLER in Schritt 3 – Pipeline abgebrochen.")
            sys.exit(2)
    else:
        print("Untis-HTML unveraendert, ueberspringe Parse.")

    ziel = notify_ziel(today, tomorrow)
    print("=== Schritt 4: Heute (" + today + ") ===")
    if rc1 == 0 and vtg_has_entries("latest_7c.json"):
        build_and_notify(today, "today_7c.json", "Heute", vtg_file="latest_7c.json",
                         notify=(ziel == today))
    else:
        print("Kein Vertretungsplan für heute – zeige regulären Plan.")
        if rc1 != 0:
            empty = {"date": today, "class": "07c", "substitutions": []}
            (DATA / "latest_7c.json").write_text(json.dumps(empty))
        run("build_today.py", today, "today_7c.json", "latest_7c.json")

    print("=== Schritt 5: Morgen (" + tomorrow + ") ===")
    if rc2 == 0 and vtg_has_entries("latest_7c_tomorrow.json"):
        build_and_notify(tomorrow, "tomorrow_7c.json", "Morgen", vtg_file="latest_7c_tomorrow.json",
                         notify=(ziel == tomorrow))
    else:
        print("Kein Vertretungsplan für morgen – zeige regulären Plan.")
        if rc2 != 0:
            empty = {"date": tomorrow, "class": "07c", "substitutions": []}
            (DATA / "latest_7c_tomorrow.json").write_text(json.dumps(empty))
        run("build_today.py", tomorrow, "tomorrow_7c.json", "latest_7c_tomorrow.json")

    print("=== Schritt 6: Wochenuebersicht ===")
    run("build_week.py", today, "week_7c.json")

    config = {
        "ntfy_topic": os.getenv("NTFY_TOPIC", ""),
        "last_run_at": datetime.now(timezone.utc).isoformat()
    }
    (DATA / "config.json").write_text(json.dumps(config))

    prune_old_hashes()

    print("=== Fertig ===")
