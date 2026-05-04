# -*- coding: utf-8 -*-
#!/usr/bin/env python3
import subprocess
import sys
import requests
from pathlib import Path
from datetime import datetime, timezone, timedelta
from notify import send_ntfy

BASE = Path(__file__).resolve().parent
PYTHON = sys.executable
DATA = BASE.parent / "data"

def get_target_date():
    now = datetime.now(timezone.utc) + timedelta(hours=2)
    if now.hour >= 9:
        candidate = now + timedelta(days=1)
    else:
        candidate = now
    while candidate.weekday() > 4:
        candidate += timedelta(days=1)
    return candidate.strftime("%Y-%m-%d")

def run(script, *args):
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
        DATA.mkdir(exist_ok=True)
        if cache.exists() and cache.read_text().strip() == last_mod:
            return False
        cache.write_text(last_mod)
        return True
    except Exception as e:
        print("Warnung: Untis-Check fehlgeschlagen: " + str(e))
        return True  # Im Zweifel neu laden

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else get_target_date()
    print("Zieldatum: " + target)

    print("=== Schritt 1: Vertretungsplan laden ===")
    run("fetch_and_build.py", target)

    print("=== Schritt 2: Untis-Stundenplan laden ===")
    if untis_html_changed():
        run("parse_untis.py")
    else:
        print("Untis-HTML unveraendert, ueberspringe Parse.")

    print("=== Schritt 3: Tagesplan zusammenfuehren ===")
    result = subprocess.run(
        [PYTHON, str(BASE / "build_today.py"), target],
        capture_output=True, text=True
    )
    print(result.stdout.strip())
    
    # Änderungen aus stdout parsen
    zeilen_output = result.stdout.strip().splitlines()
    aenderungen = [z for z in zeilen_output if z.startswith("  Std ")]
    
    if aenderungen and result.returncode == 0:
        msg_zeilen = []
        for a in aenderungen:
            a = a.strip()
            if "FREI" in a:
                msg_zeilen.append("\u274c " + a)
            elif "VERTRETUNG" in a:
                msg_zeilen.append("\U0001f504 " + a)
            else:
                msg_zeilen.append("\U0001f4da " + a)
    
        ok = send_ntfy(
            title="Aenderung Klasse 6c - " + target,
            msg="\n".join(msg_zeilen),
            priority=4
        )
        print("Benachrichtigung gesendet!")
    else:
        print("Keine Änderungen – keine Benachrichtigung.")
    print("=== Fertig ===")