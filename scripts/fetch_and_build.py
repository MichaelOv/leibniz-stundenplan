#!/usr/bin/env python3
import json, os, sys, re, traceback, logging
from pathlib import Path
from datetime import datetime, date, timezone, timedelta
import fitz
import requests
from dotenv import load_dotenv
from constants import DAYS_DE

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

load_dotenv()
try:
    USERNAME = os.environ["ISERV_USER"]
    PASSWORD = os.environ["ISERV_PASS"]
except KeyError as e:
    print(f"FEHLER: Umgebungsvariable {e} fehlt – bitte .env prüfen.")
    sys.exit(1)
BASE_URL  = "https://gym-leibniz-ge.de"
ISERV_URL = BASE_URL + "/iserv/plan/show/raw/Vertretung%20Sch%C3%BCler/{date}-S.pdf"
TARGET_CLASS = "06c"

KNOWN_TEACHERS = re.compile(r'^[A-ZÄÖÜ]{2,6}$')
KNOWN_ROOMS    = re.compile(r'^[A-Z0-9][A-Z0-9\.\-]{1,7}$', re.IGNORECASE)

def class_matches(s, my_class):
    s = s.lower().strip()
    mc = my_class.lower().strip()
    if s == mc:
        return True
    jg  = re.search(r'(\d+)', mc)
    bst = re.search(r'([a-z]+)$', mc)
    if jg and bst:
        vjg   = re.search(r'(\d+)', s)
        vrest = re.sub(r'\d+', '', s)
        if vjg and vjg.group(1) == jg.group(1) and bst.group(1) in vrest:
            return True
    return False

def is_next_class(s):
    # Erkennt naechste Klassen-Zeile wie "06c", "07ab", "EF", "iföA"
    return bool(re.match(r'^(0?\d[a-z]{1,5}|[A-Z]{2,3}|if[oö][A-Z])$', s.strip()))

def get_authenticated_session():
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    r1 = session.get(BASE_URL + "/iserv/login", timeout=30, allow_redirects=True)
    r2 = session.post(r1.url, data={"_username": USERNAME, "_password": PASSWORD,
                                    "_remember_me": "on"}, allow_redirects=True, timeout=30)
    r2.raise_for_status()
    # iServ nutzt einen HTML meta-refresh fuer den OIDC-Abschluss – manuell folgen
    meta = re.search(r'<meta[^>]+http-equiv=["\']refresh["\'][^>]+content=["\']0;url=([^"\']+)["\']', r2.text, re.I)
    if meta:
        redirect_url = meta.group(1).replace("&amp;", "&")
        r2 = session.get(redirect_url, timeout=30, allow_redirects=True)
        r2.raise_for_status()
    if "/iserv/auth/login" in r2.url:
        raise ValueError("iServ-Login fehlgeschlagen – Zugangsdaten pruefen.")
    return session

def fetch_pdf(session, url):
    r = session.get(url, timeout=30)
    r.raise_for_status()
    if b"%PDF" not in r.content[:10]:
        print("KEIN PDF")
        return None
    print("PDF geladen: " + str(len(r.content)) + " bytes")
    return r.content

def parse_entry(lines, start):
    """Liest einen Vertretungseintrag ab Position start.
    Format: klasse, stunde, lehrer, [vertreter [raum]], [fach], [text...]
    Stoppt wenn naechste Klasse erkannt oder max 6 Felder gelesen."""
    klasse  = lines[start]
    stunde  = lines[start+1] if start+1 < len(lines) else ""
    lehrer  = lines[start+2] if start+2 < len(lines) else ""

    # Felder nach Lehrer dynamisch einlesen bis naechste Klasse
    rest = []
    j = start + 3
    while j < len(lines) and len(rest) < 6:
        val = lines[j].strip()
        if val == "---":
            rest.append("")
            j += 1
            continue
        if is_next_class(val) and len(rest) >= 1:
            break
        rest.append(val)
        j += 1

    # rest[0] = vertreter oder "vertreter raum" zusammen
    # rest[1] = raum oder fach
    # rest[2] = fach oder text
    # rest[3+] = text
    vertreter = ""
    raum      = ""
    fach      = ""
    text      = ""

    if len(rest) >= 1:
        v = rest[0]
        if " " in v:
            parts = v.split(None, 1)
            vertreter = parts[0]
            raum      = parts[1]
        else:
            vertreter = v

    if len(rest) >= 2 and not raum:
        raum = rest[1]
    elif len(rest) >= 2 and raum:
        fach = rest[1]

    if len(rest) >= 3:
        text = " ".join(rest[2:])

    if lehrer == "---":
        lehrer = ""
    if vertreter == "---":
        vertreter = ""
    if raum == "---":
        raum = ""
    if fach == "---":
        fach = ""

    return {
        "klasse": klasse, "stunde": stunde,
        "lehrer": lehrer, "vertreter": vertreter,
        "raum": raum, "fach": fach, "text": text
    }, j

def check_pdf_header(pdf_bytes, target_date):
    """Öffnet das PDF einmal und gibt (datum_stimmt, pdf_stand_iso) zurück."""
    d = date.fromisoformat(target_date)
    pattern = f"{d.day}.{d.month}."
    day_name = DAYS_DE[d.weekday()]
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        text = "".join(page.get_text() for page in doc)
    date_ok = (pattern in text and day_name in text)
    m = re.search(r'(\d{1,2}\.\d{1,2}\.\d{4})\s+(\d{1,2}:\d{2})', text)
    pdf_stand = None
    if m:
        try:
            dt = datetime.strptime(m.group(1) + " " + m.group(2), "%d.%m.%Y %H:%M")
            pdf_stand = dt.replace(tzinfo=timezone(timedelta(hours=2))).isoformat()
        except ValueError as e:
            print(f"Warnung: pdf_stand konnte nicht geparst werden: {e}")
    return date_ok, pdf_stand

def parse_class_data(pdf_bytes, target_class):
    data = []
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page in doc:
            for block in page.get_text("blocks"):
                lines = [ln.strip() for ln in block[4].split("\n") if ln.strip()]
                i = 0
                while i < len(lines):
                    if class_matches(lines[i], target_class):
                        entry, next_i = parse_entry(lines, i)
                        logging.debug("TREFFER: %s", entry)
                        data.append(entry)
                        i = next_i
                    else:
                        i += 1
    print("Gesamt: " + str(len(data)) + " Eintraege")
    return data

if __name__ == "__main__":
    target_date = sys.argv[1] if len(sys.argv) > 1 else datetime.now(timezone.utc).strftime("%Y-%m-%d")
    url = ISERV_URL.format(date=target_date)
    try:
        session = get_authenticated_session()
        pdf_bytes = fetch_pdf(session, url)
        if not pdf_bytes:
            sys.exit(1)   # kein PDF – erwartet (exit 1)
        date_ok, pdf_stand = check_pdf_header(pdf_bytes, target_date)
        if not date_ok:
            print("PDF enthält nicht das Zieldatum – kein Plan verfügbar.")
            sys.exit(1)   # falsches Datum – erwartet (exit 1)
        print("PDF-Stand: " + str(pdf_stand))
        class_data = parse_class_data(pdf_bytes, TARGET_CLASS)
        output = {"date": target_date, "class": TARGET_CLASS, "substitutions": class_data, "pdf_stand": pdf_stand}
        out_file = sys.argv[2] if len(sys.argv) > 2 else "latest_6c.json"
        data_path = Path(__file__).resolve().parents[1] / "data" / out_file
        data_path.parent.mkdir(exist_ok=True)
        with open(data_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        print("Fertig!")
    except (ValueError, requests.RequestException) as e:
        print("FEHLER: " + str(e), file=sys.stderr)
        sys.exit(2)   # echter Fehler (Login, Netzwerk) – exit 2
    except Exception:
        traceback.print_exc()
        sys.exit(2)   # unerwartete Exception – exit 2
