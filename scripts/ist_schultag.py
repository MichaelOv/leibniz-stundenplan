#!/usr/bin/env python3
"""Exit-Code-Guard fuer den Cron: lohnt sich jetzt ein Pipeline-Lauf?

Exit 0  -> ja, ausloesen
Exit 1  -> nein, heute und morgen sind unterrichtsfrei

In den Ferien gibt es keinen Vertretungsplan und keinen Unterricht. Ohne
diesen Guard wuerde der Cron trotzdem rund dreissig Mal pro Werktag einen
Workflow starten, der sich nur bei iServ anmeldet und nichts findet.

Der letzte Ferientag laeuft bewusst mit: dann ist morgen wieder Schule, und
der Plan fuer den ersten Schultag soll rechtzeitig da sein.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_today import schulfrei_grund
from run_all import get_today, get_tomorrow

def main() -> int:
    today = get_today()
    tomorrow = get_tomorrow(today)
    g_today = schulfrei_grund(today)
    g_tomorrow = schulfrei_grund(tomorrow)
    if g_today and g_tomorrow:
        print(f"Kein Lauf: {today} ({g_today}), {tomorrow} ({g_tomorrow})")
        return 1
    print(f"Lauf: {today} ({g_today or 'Schultag'}), {tomorrow} ({g_tomorrow or 'Schultag'})")
    return 0

if __name__ == "__main__":
    sys.exit(main())
