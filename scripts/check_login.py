import requests
import re

BASE_URL = "https://gym-leibniz-ge.de"
session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0"})

r = session.get(BASE_URL + "/iserv/login", timeout=30)
print("Status: " + str(r.status_code))

# Alle input-Felder im Formular finden
inputs = re.findall(r'<input[^>]+>', r.text)
for inp in inputs:
    print("INPUT: " + inp)

# Action des Formulars finden
action = re.findall(r'<form[^>]+action="([^"]+)"', r.text)
print("FORM ACTION: " + str(action))
