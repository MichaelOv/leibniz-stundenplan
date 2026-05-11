import os, requests, base64, hashlib
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
DATA_DIR = Path(__file__).resolve().parents[1] / "data"

def _ntfy_url() -> str:
    topic = os.getenv("NTFY_TOPIC")
    if not topic:
        raise ValueError("NTFY_TOPIC ist nicht gesetzt. Bitte in .env oder als Umgebungsvariable definieren.")
    return f"https://ntfy.sh/{topic}"

def rfc2047(s: str) -> str:
    b64 = base64.b64encode(s.encode("utf-8")).decode("ascii")
    return f"=?UTF-8?B?{b64}?="

def _hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()

def already_sent(key: str, hash_file: Path) -> bool:
    return hash_file.exists() and hash_file.read_text().strip() == _hash(key)

def send_ntfy(title: str, msg: str, priority: int = 3, hash_suffix: str = "today") -> bool:
    hash_file = DATA_DIR / f"last_ntfy_hash_{hash_suffix}.txt"
    key = title + "|" + msg
    if already_sent(key, hash_file):
        print("ntfy: Gleiche Benachrichtigung bereits gesendet, ueberspringe.")
        return False

    ntfy_url = _ntfy_url()
    try:
        r = requests.post(ntfy_url,
            data=msg.encode("utf-8"),
            headers={
                "Title":    rfc2047(title),
                "Priority": str(priority),
                "Tags":     "school,bell",
            },
            timeout=5
        )
        r.raise_for_status()
        hash_file.write_text(_hash(key))
        return True
    except requests.exceptions.ConnectionError:
        print("ntfy FEHLER: Keine Verbindung zu " + ntfy_url)
    except requests.exceptions.Timeout:
        print("ntfy FEHLER: Timeout nach 5s")
    except requests.exceptions.HTTPError as e:
        print("ntfy FEHLER: HTTP " + str(e.response.status_code) + " - " + e.response.text)
    except Exception as e:
        print("ntfy FEHLER: " + str(e))
    return False