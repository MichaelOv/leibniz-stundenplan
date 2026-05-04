#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup

url = "https://leibniz-gymnasium.net/files/stpl/Kla1A_06c.htm"
r = requests.get(url, timeout=30)
r.encoding = r.apparent_encoding
soup = BeautifulSoup(r.content, "html.parser")

# Alle Tabellen ausgeben
tables = soup.find_all("table")
print("Anzahl Tabellen: " + str(len(tables)))
print()

# Roher Text
text = soup.get_text(separator="|", strip=True)
print("TEXT:")
print(text[:3000])
print()

# Alle td/th mit Inhalt
print("ZELLEN:")
for i, td in enumerate(soup.find_all(["td","th"])):
    content = td.get_text(strip=True)
    if content:
        print(str(i) + ": " + content[:80])
    if i > 100:
        break
