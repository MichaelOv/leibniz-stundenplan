
import hashlib, json, os, sys, re
from pathlib import Path
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Load env variables
load_dotenv()
USERNAME = os.getenv("ISERV_USER")
PASSWORD = os.getenv("ISERV_PASS")

ISERV_URL = "https://gym-leibniz-ge.de/iserv/plan/show/raw/Vertretung%20Sch%C3%BCler/{date}-S.pdf"
UNTIS_URL = "https://leibniz-gymnasium.net/files/stpl/Kla1A_06c.htm"
TARGET_CLASS = "06c"

def fetch_with_login(url):
    session = requests.Session()
    if USERNAME and PASSWORD:
        session.post("https://gym-leibniz-ge.de/iserv/login", data={"user": USERNAME, "password": PASSWORD})
    r = session.get(url, timeout=30)
    r.raise_for_status()
    return r.content


def parse_pdf_for_class(pdf_bytes, target_class):
    import fitz
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    all_data = []

    for page in doc:
        # Extract text blocks
        blocks = page.get_text("blocks")
        blocks.sort(key=lambda b: b[1]) # Sort by y0

        for b in blocks:
            text = b[4].strip()
            # Split into lines
            lines = text.split('\n')
            for line in lines:
                # Find lines that contain our target class
                if target_class in line:
                    parts = line.split()
                    # Basic robust mapping
                    row = {
                        "klasse": parts[0],
                        "stunde": parts[1] if len(parts) > 1 else "",
                        "lehrer": parts[2] if len(parts) > 2 else "",
                        "vertreter": parts[3] if len(parts) > 3 else "",
                        "raum": parts[4] if len(parts) > 4 else "",
                        "fach": parts[5] if len(parts) > 5 else "",
                        "text": " ".join(parts[6:]) if len(parts) > 6 else ""
                    }
                    all_data.append(row)
    return all_data


if __name__ == "__main__":
    target_date = sys.argv[1] if len(sys.argv) > 1 else datetime.utcnow().strftime("%Y-%m-%d")
    pdf_url = ISERV_URL.format(date=target_date)

    try:
        pdf_bytes = fetch_with_linker = fetch_with_login(pdf_url)
        class_data = parse_pdf_for_class(pdf_bytes, TARGET_CLASS)

        output = {
            "date": target_date,
            "class": TARGET_CLASS,
            "substitutions": class_data
        }

        data_path = Path(__file__).resolve().parents[1] / "data" / "latest_6c.json"
        data_path.write_text(json.dumps(output, indent=2))
        print(f"Successfully processed {TARGET_CLASS}")
    except Exception as e:
        print(f"Error: {e}")
