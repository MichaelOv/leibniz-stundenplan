# -*- coding: utf-8 -*-
import os, requests, base64, hashlib, json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
NTFY_TOPIC = os.getenv("NTFY_TOPIC", "leibniz-gym-ge-plan-jeo")
NTFY_URL = f"https://ntfy.sh/{NTFY_TOPIC}"
DATA_DIR = Path(__file__).resolve().parents[1] / "data"

def rfc2047(s: str) -> str:
    b64 = base64.b64encode(s.encode("utf-8")).decode("ascii")
    return f"=?UTF-8?B?{b64}?="

def already_sent(key: str, hash_file: Path) -> bool:
    h = hashlib.md5(key.encode()).hexdigest()
    if hash_file.exists() and hash_file.read_text().strip() == h:
        return True
    hash_file.write_text(h)
    return False

def send_ntfy(title: str, msg: str, priority: int = 3, hash_suffix: str = "today") -> bool:
    # Datum + Inhalt als eindeutiger Key
    hash_file = DATA_DIR / f"last_ntfy_hash_{hash_suffix}.txt"
    key = title + "|" + msg
    if already_sent(key, hash_file):
        print("ntfy: Gleiche Benachrichtigung bereits gesendet, ueberspringe.")
        return False

    try:
        r = requests.post(NTFY_URL,
            data=msg.encode("utf-8"),
            headers={
                "Title":    rfc2047(title),
                "Priority": str(priority),
                "Tags":     "school,bell",
            },
            timeout=5
        )
        r.raise_for_status()
        return True
    except requests.exceptions.ConnectionError:
        print("ntfy FEHLER: Keine Verbindung zu " + NTFY_URL)
    except requests.exceptions.Timeout:
        print("ntfy FEHLER: Timeout nach 5s")
    except requests.exceptions.HTTPError as e:
        print("ntfy FEHLER: HTTP " + str(e.response.status_code) + " - " + e.response.text)
    except Exception as e:
        print("ntfy FEHLER: " + str(e))
    return False