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
    now = datetime.now(_TZ_BERLIN)
    if now.hour >= NOTIFY_HOUR_CUTOFF:
        candidate = now.date() + timedelta(days=1)
    else:
        candidate = now.date()
    while candidate.weekday() > 4:
        candidate += timedelta(days=1)
    return candidate.isoformat()

def get_tomorrow(today_str):
    d = date.fromisoformat(today_str) + timedelta(days=1)
    while d.weekday() > 4:
        d += timedelta(days=1)
    return d.isoformat()

def run(script, *args) -> bool:
    cmd = [PYTHON, str(BASE / script)] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout.strip())
    if result.returncode != 0:
        print("FEHLER in " + script + ": " + result.stderr.strip())
        return False
    return True

def untis_html_changed():
    try:
        r = requests.head(
            "https://leibniz-gymnasium.net/files/stpl/Kla1A_06c.htm",
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

def build_and_notify(target, out_file, label, vtg_file="latest_6c.json", notify=True):
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
            suffix = "tomorrow" if label == "Morgen" else "today"
            ok = send_ntfy(
                title="Änderung 6c " + day_label,
                msg="\n".join(msg_zeilen),
                priority=4,
                hash_suffix=suffix
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

    print("=== Schritt 1: Vertretungsplan heute laden (" + today + ") ===")
    ok1 = run("fetch_and_build.py", today, "latest_6c.json")

    print("=== Schritt 2: Vertretungsplan morgen laden (" + tomorrow + ") ===")
    ok2 = run("fetch_and_build.py", tomorrow, "latest_6c_tomorrow.json")

    print("=== Schritt 3: Untis-Stundenplan laden ===")
    if untis_html_changed():
        run("parse_untis.py")
    else:
        print("Untis-HTML unveraendert, ueberspringe Parse.")

    print("=== Schritt 4: Heute ===")
    if ok1:
        build_and_notify(today, "today_6c.json", "Heute", vtg_file="latest_6c.json", notify=True)
    else:
        print("PDF-Fehler – überspringe Heute.")

    print("=== Schritt 5: Morgen ===")
    if ok2 and vtg_has_entries("latest_6c_tomorrow.json"):
        build_and_notify(tomorrow, "tomorrow_6c.json", "Morgen", vtg_file="latest_6c_tomorrow.json", notify=False)
    else:
        print("Kein Vertretungsplan für morgen – zeige regulären Plan.")
        if not ok2:
            empty = {"date": tomorrow, "class": "06c", "substitutions": []}
            (DATA / "latest_6c_tomorrow.json").write_text(json.dumps(empty))
        run("build_today.py", tomorrow, "tomorrow_6c.json", "latest_6c_tomorrow.json")

    config = {
        "ntfy_topic": os.getenv("NTFY_TOPIC", ""),
        "last_run_at": datetime.now(timezone.utc).isoformat()
    }
    (DATA / "config.json").write_text(json.dumps(config))

    print("=== Fertig ===")
