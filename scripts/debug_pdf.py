#!/usr/bin/env python3
import requests
import fitz
import os
from dotenv import load_dotenv

load_dotenv()
BASE_URL = "https://gym-leibniz-ge.de"
session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0"})
r1 = session.get(BASE_URL + "/iserv/login", timeout=30, allow_redirects=True)
session.post(r1.url, data={"_username": os.getenv("ISERV_USER"), "_password": os.getenv("ISERV_PASS"), "_remember_me": "on"}, allow_redirects=True, timeout=30)

url = BASE_URL + "/iserv/plan/show/raw/Vertretung%20Sch%C3%BCler/2026-05-04-S.pdf"
r = session.get(url, timeout=30)
doc = fitz.open(stream=r.content, filetype="pdf")

for i, page in enumerate(doc):
    blocks = page.get_text("blocks")
    blocks.sort(key=lambda b: (b[1], b[0]))
    print("=== SEITE " + str(i+1) + " ===")
    for b in blocks:
        text = b[4].strip()
        if "06c" in text or "06 c" in text.lower():
            print("BLOCK x=" + str(round(b[0])) + " y=" + str(round(b[1])) + ": " + repr(text))
