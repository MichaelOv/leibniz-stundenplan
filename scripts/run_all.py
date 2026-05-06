# -*- coding: utf-8 -*-
#!/usr/bin/env python3
import subprocess
import sys
import requests
from pathlib import Path
from datetime import datetime, date, timezone, timedelta
from notify import send_ntfy

BASE = Path(__file__).resolve().parent
PYTHON = sys.executable
DATA = BASE.parent / "data"

def get_today():
    now = datetime.now(timezone.utc) + timedelta(hours=2)
    if now.hour >= 9:
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

def run(script, *args):
    cmd = [PYTHON, str(BASE / script)] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout.strip())
    if result.returncode != 0:
        print("FEHLER in " + script + ": " + result.stderr.strip())
        return None
    return result

def untis_html_changed():
    try:
        r = requests.head(
            "https://leibniz-gymnasium.net/files/stpl/Kla1A_06c.htm",
            timeout=10
        )
        last_mod = r.headers.get("Last-Modified", "")
        cache = DATA / "untis_last_modified.txt"
        DATA.mkdir(exist_ok=True)
        if cache.exists() and cache.read_text().strip() == last_mod:
            return False
        cache.write_text(last_mod)
        return True
    except Exception as e:
        print("Warnung: Untis-Check fehlgeschlagen: " + str(e))
        return True

def vtg_has_entries(json_file):
    import json
    path = DATA / json_file
    if not path.exists():
        return False
    try:
        data = json.load(open(path))
        return len(data.get("substitutions", [])) > 0
    except:
        return False

def build_and_notify(target, out_file, label, vtg_file="latest_6c.json", notify=True):
    print(f"=== {label}: Tagesplan zusammenfuehren ===")
    result = subprocess.run(
        [PYTHON, str(BASE / "build_today.py"), target, out_file, vtg_file],
        capture_output=True, text=True
    )
    print(result.stdout.strip())

    zeilen_output = result.stdout.strip().splitlines()
    aenderungen = [z for z in zeilen_output if z.startswith("  Std ") and any(x in z for x in ["FREI", "VERTRETUNG", "INFO"])]

    if aenderungen and result.returncode == 0:
        msg_zeilen = []
        for a in aenderungen:
            a = a.strip()
            if "FREI" in a:
                msg_zeilen.append("❌ " + a)
            elif "VERTRETUNG" in a:
                msg_zeilen.append("🔄 " + a)
            else:
                msg_zeilen.append("📋 " + a)

        if notify:
            suffix = "tomorrow" if label == "Morgen" else "today"
            ok = send_ntfy(
                title="Änderung 6c " + label + " - " + target,
                msg="\n".join(msg_zeilen),
                priority=4,
                hash_suffix=suffix
            )
            if ok:
                print("Benachrichtigung gesendet!")
        else:
            print("Benachrichtigung übersprungen (Zeitfenster).")
    else:
        print("Keine Änderungen – keine Benachrichtigung.")

if __name__ == "__main__":
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

    now = datetime.now(timezone.utc) + timedelta(hours=2)
    after_nine = now.hour >= 9

    print("=== Schritt 4: Heute ===")
    if ok1:
        build_and_notify(today, "today_6c.json", "Heute", vtg_file="latest_6c.json", notify=not after_nine)
    else:
        print("PDF-Fehler – überspringe Heute.")

    print("=== Schritt 5: Morgen ===")
    if ok2 and vtg_has_entries("latest_6c_tomorrow.json"):
        build_and_notify(tomorrow, "tomorrow_6c.json", "Morgen", vtg_file="latest_6c_tomorrow.json", notify=after_nine)
    else:
        print("Kein Vertretungsplan für morgen – zeige regulären Plan.")
        run("build_today.py", tomorrow, "tomorrow_6c.json", "latest_6c_tomorrow.json")

    print("=== Fertig ===")
