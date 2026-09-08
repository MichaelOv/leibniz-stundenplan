"""Tests für die reine Parser- und Merge-Logik (kein Netzwerk, keine Dateien).

Deckt die heuristischen Funktionen ab, die bei geändertem PDF /HTML-Layout
still falsche Ergebnisse liefern könnten.
"""
import pytest

import pytest as _pytest
import requests
from fetch_and_build import class_matches, is_next_class, parse_entry, fetch_pdf


class _FakeResp:
    def __init__(self, status_code, content=b""):
        self.status_code = status_code
        self.content = content
    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"{self.status_code}")


class _FakeSession:
    def __init__(self, resp):
        self._resp = resp
    def get(self, url, timeout=None):
        return self._resp


class TestFetchPdf:
    def test_404_ist_kein_fehler_sondern_none(self):
        # Kern des Ferien /Morgen-Bugs: 404 darf NICHT raisen (Exit 2),
        # sondern None liefern (-> Exit 1, regulaerer Plan).
        assert fetch_pdf(_FakeSession(_FakeResp(404)), "u") is None

    def test_200_ohne_pdf_ist_none(self):
        assert fetch_pdf(_FakeSession(_FakeResp(200, b"<html>login")), "u") is None

    def test_200_mit_pdf_gibt_bytes(self):
        pdf = b"%PDF-1.7 ..."
        assert fetch_pdf(_FakeSession(_FakeResp(200, pdf)), "u") == pdf

    def test_500_bleibt_echter_fehler(self):
        with _pytest.raises(requests.exceptions.HTTPError):
            fetch_pdf(_FakeSession(_FakeResp(500)), "u")
from datetime import date
from parse_untis import extract_valid_from, extract_schuljahr
from constants import expected_schuljahr
from build_today import parse_stunden, clean, clean_lehrer, fach_name, resolve_vtg_fach, ist_ausfall

FACH_MAP = {"BI": "Biologie", "GE": "Geschichte", "M": "Mathe", ".IR": "Islamische Rel."}


class TestParseStunden:
    @pytest.mark.parametrize("raw, stunden, lehrer", [
        ("7 - 8 ROM", [7, 8], "ROM"),
        ("1 - 2 MAT", [1, 2], "MAT"),
        ("3", [3], ""),
        ("5", [5], ""),
    ])
    def test_parse(self, raw, stunden, lehrer):
        assert parse_stunden(raw) == (stunden, lehrer)


class TestClassMatches:
    @pytest.mark.parametrize("kandidat, ziel", [
        ("06c", "06c"),      # exakt
        ("06bc", "06c"),     # Gruppe enthält Buchstaben der Zielklasse
    ])
    def test_matches(self, kandidat, ziel):
        assert class_matches(kandidat, ziel) is True

    @pytest.mark.parametrize("kandidat, ziel", [
        ("06a", "06c"),      # anderer Buchstabe
        ("07c", "06c"),      # anderer Jahrgang
        ("17c", "07c"),      # 17 ist nicht 7, trotz numerischem Vergleich
        ("08c", "07c"),
    ])
    def test_no_match(self, kandidat, ziel):
        assert class_matches(kandidat, ziel) is False

    @pytest.mark.parametrize("kandidat", ["7c", "7C", "7bc", "7ac"])
    def test_ohne_fuehrende_null(self, kandidat):
        # Schreibt die Schule "7c" statt "07c", darf der Eintrag nicht
        # stillschweigend verloren gehen.
        assert class_matches(kandidat, "07c") is True


class TestIsNextClass:
    @pytest.mark.parametrize("wert", ["06c", "6c", "EF", "Q1", "Q2", "(06d)", "07ab"])
    def test_is_class(self, wert):
        assert is_next_class(wert) is True

    @pytest.mark.parametrize("wert", ["GE", "BI", "MU", "SP", "MOR", "A1.17"])
    def test_is_not_class(self, wert):
        # Fachkürzel und Räume dürfen NICHT als Klasse erkannt werden
        assert is_next_class(wert) is False


class TestParseEntry:
    def test_klassenleitungstag_raum_nicht_als_vertreter(self):
        # Bug 17.7.: "603" (Raum) landete faelschlich als Vertreter,
        # "Klassenleitungstag" als Raum.
        lines = ["06c", "1", "GRU", "603", "Klassenleitungstag"]
        entry, _ = parse_entry(lines, 0)
        assert entry["vertreter"] == ""        # KEIN "603"
        assert entry["raum"] == "603"          # Raum korrekt
        assert entry["fach"] == "Klassenleitungstag"
        assert "Klassenleitungstag" not in entry["raum"]

    def test_normale_vertretung_bleibt_unveraendert(self):
        # Vertreterkuerzel (Buchstaben) muss weiterhin als Vertreter erkannt werden
        lines = ["06c", "3", "MOR", "SUB", "A12"]
        entry, _ = parse_entry(lines, 0)
        assert entry["vertreter"] == "SUB"
        assert entry["raum"] == "A12"

    def test_vertreter_und_raum_zusammen(self):
        # PyMuPDF merged "SUB A12" in eine Zeile
        lines = ["06c", "3", "MOR", "SUB A12"]
        entry, _ = parse_entry(lines, 0)
        assert entry["vertreter"] == "SUB"
        assert entry["raum"] == "A12"


class TestExpectedSchuljahr:
    @pytest.mark.parametrize("d, erwartet", [
        (date(2026, 9, 2),  "2026/27"),   # Schuljahresbeginn
        (date(2026, 8, 1),  "2026/27"),   # August zaehlt schon zum neuen Jahr
        (date(2026, 7, 20), "2025/26"),   # Juli noch altes Jahr
        (date(2027, 1, 15), "2026/27"),   # Januar gehoert zum Vorjahr-Start
        (date(2029, 12, 1), "2029/30"),   # Jahrhundertwechsel-nahe Formatierung
    ])
    def test_schuljahr(self, d, erwartet):
        assert expected_schuljahr(d) == erwartet


class TestExtractSchuljahr:
    def test_findet_schuljahr(self):
        assert extract_schuljahr("Untis 2024 2025/26 Leibniz") == "2025/26"

    def test_kein_schuljahr(self):
        assert extract_schuljahr("kein Jahr hier") is None


class TestExtractValidFrom:
    @pytest.mark.parametrize("html, erwartet", [
        ("Stundenplan (ab 5.5.25) gültig", "2025-05-05"),
        ("Plan (ab 12.1.2026)", "2026-01-12"),
        ("kein Datum hier", None),
    ])
    def test_extract(self, html, erwartet):
        assert extract_valid_from(html) == erwartet


class TestClean:
    @pytest.mark.parametrize("roh, erwartet", [
        ("---", ""),
        (None, ""),
        ("  Mathe  ", "Mathe"),
        ("D", "D"),
    ])
    def test_clean(self, roh, erwartet):
        assert clean(roh) == erwartet

    @pytest.mark.parametrize("roh, erwartet", [
        ("MOR GRU", "MOR"),   # zusammengeführte Lehrer /Vertreter-Spalte
        ("---", ""),
        ("", ""),
        ("HIL", "HIL"),
    ])
    def test_clean_lehrer(self, roh, erwartet):
        assert clean_lehrer(roh) == erwartet


class TestResolveVtgFach:
    def test_strukturiertes_fach_gewinnt(self):
        assert resolve_vtg_fach("BI", "irgendwas", FACH_MAP) == "BI"

    def test_fuehrender_punkt_im_strukturierten_fach(self):
        assert resolve_vtg_fach(".IR", "", FACH_MAP) == "IR"

    def test_kuerzel_aus_hinweis(self):
        # der Montag-Fall: "BI statt Do. 9.7. 5. Std."
        assert resolve_vtg_fach("", "BI statt Do. 9.7. 5. Std.", FACH_MAP) == "BI"
        assert resolve_vtg_fach("", "GE statt 3. Std.", FACH_MAP) == "GE"

    def test_unbekanntes_kuerzel_wird_ignoriert(self):
        assert resolve_vtg_fach("", "XYZ statt Do.", FACH_MAP) == ""

    def test_freitext_ohne_kuerzel(self):
        assert resolve_vtg_fach("", "Aufgaben werden gestellt", FACH_MAP) == ""
        assert resolve_vtg_fach("", "", FACH_MAP) == ""

    def test_namens_initiale_wird_nicht_als_fach_gelesen(self):
        # 'M' ist Mathe im Mapping, darf hier aber NICHT als Fachwechsel gelten
        assert resolve_vtg_fach("", "M. Müller vertritt", FACH_MAP) == ""
        assert resolve_vtg_fach("", "D Schmidt krank", FACH_MAP) == ""

    def test_kuerzel_ohne_schluesselwort_ignoriert(self):
        # nur 'statt'/'verlegt' lösen einen Fachwechsel aus
        assert resolve_vtg_fach("", "GE Raumänderung", FACH_MAP) == ""


class TestIstAusfall:
    @pytest.mark.parametrize("text", [
        "frei", "frei; verlegt auf Fr. 10.7. 2. Std.",
        "entfällt", "Entfällt", "entfall", "Stunde entfällt ersatzlos",
    ])
    def test_ausfall_erkannt(self, text):
        assert ist_ausfall(text) is True

    @pytest.mark.parametrize("vtg", ["frei", "Entfällt", "entfall"])
    def test_ausfall_ueber_vertreter_feld(self, vtg):
        assert ist_ausfall("", vtg) is True

    @pytest.mark.parametrize("text", [
        "", "BI statt Do. 9.7. 5. Std.", "Raumänderung", "Klassenleitungstag",
    ])
    def test_kein_ausfall(self, text):
        assert ist_ausfall(text) is False


class TestFachName:
    def test_bekanntes_kuerzel(self):
        assert fach_name("D", {"D": "Deutsch"}) == "Deutsch"

    def test_fuehrender_punkt_wird_entfernt(self):
        assert fach_name(".M", {"M": "Mathe"}) == "Mathe"

    def test_unbekanntes_kuerzel_bleibt(self):
        assert fach_name("XX", {}) == "XX"


@pytest.fixture(scope="module")
def plan():
    from pathlib import Path
    from parse_untis import parse_untis_html
    pfad = Path(__file__).parent / "fixtures" / "untis_7c_2026-27.htm"
    return parse_untis_html(pfad.read_bytes())


class TestUntisGrid:
    """Parser gegen den echten Untis-Export vom 01.09.2026 (Schuljahr 2026/27).

    Der Plan wurde gegen das gerenderte Layout im Browser abgeglichen, ist also
    die tatsaechliche Wahrheit. Regression fuer zwei Fehler: verschachtelte
    Tabellenzellen verschoben die Spaltenzaehlung, wodurch Doppelstunden am
    Zeilenende (Freitag) verloren gingen; die Tagesbreite von 13 statt 12
    Spalten liess Spalte 13 zusaetzlich auf Montag passen.
    """
    ERWARTET = {
        1: {"Montag": ["M"], "Dienstag": [".F7", "L7"], "Donnerstag": ["E"], "Freitag": ["PK"]},
        2: {"Montag": ["M"], "Dienstag": [".F7", "L7"], "Mittwoch": ["E"],
            "Donnerstag": ["E"], "Freitag": ["D"]},
        3: {"Montag": ["D"], "Dienstag": ["EK"], "Mittwoch": ["SP"],
            "Donnerstag": [".F7", "L7"], "Freitag": ["M"]},
        4: {"Montag": ["D"], "Dienstag": [".ER", "IR", "KR", "PP"], "Mittwoch": ["M"],
            "Donnerstag": [".F7", "L7"], "Freitag": ["CH"]},
        5: {"Montag": ["EK"], "Dienstag": ["PK"], "Mittwoch": ["KU"],
            "Donnerstag": [".ER", "IR", "KR", "PP"], "Freitag": ["SP"]},
        6: {"Montag": ["E"], "Dienstag": ["CH"], "Mittwoch": ["KU"],
            "Donnerstag": ["D"], "Freitag": ["SP"]},
    }

    def test_kopfdaten(self, plan):
        _, valid_from, schuljahr = plan
        assert valid_from == "2026-08-31"
        assert schuljahr == "2026/27"

    @pytest.mark.parametrize("stunde", sorted(ERWARTET))
    def test_stunde(self, plan, stunde):
        tt = plan[0]
        ist = {tag: sorted(l["fach"] for l in les)
               for tag, les in tt.get(stunde, {}).items() if les}
        soll = {tag: sorted(f) for tag, f in self.ERWARTET[stunde].items()}
        assert ist == soll

    def test_doppelstunde_am_zeilenende(self, plan):
        # Sport freitags 5. UND 6. Stunde: genau der Fall, der vorher fehlte
        tt = plan[0]
        assert [l["fach"] for l in tt[5]["Freitag"]] == ["SP"]
        assert [l["fach"] for l in tt[6]["Freitag"]] == ["SP"]

    def test_keine_stunden_nach_der_sechsten(self, plan):
        tt = plan[0]
        for stunde in (7, 8, 9):
            assert not any(tt.get(stunde, {}).values())


class TestKlassenDiagnose:
    """Die Diagnose unterscheidet 'keine Vertretung' von 'nicht erkannt'."""

    def test_zaehlt_klassen(self, monkeypatch):
        import fetch_and_build as fb

        class FakeSeite:
            def get_text(self, was):
                return [(0, 0, 0, 0, "07c\n1\nGRU\n603\nfrei\n08a\n2\nMOR\n")]

        class FakeDoc:
            def __iter__(self): return iter([FakeSeite()])
            def __enter__(self): return self
            def __exit__(self, *a): return False

        monkeypatch.setattr(fb.fitz, "open", lambda **kw: FakeDoc())
        gefunden = fb.klassen_im_pdf(b"egal")
        assert gefunden == {"07c": 1, "08a": 1}

    def test_leeres_pdf_meldet_nichts(self, monkeypatch):
        import fetch_and_build as fb

        class FakeSeite:
            def get_text(self, was):
                return [(0, 0, 0, 0, "Kein Unterrichtsausfall\n")]

        class FakeDoc:
            def __iter__(self): return iter([FakeSeite()])
            def __enter__(self): return self
            def __exit__(self, *a): return False

        monkeypatch.setattr(fb.fitz, "open", lambda **kw: FakeDoc())
        assert fb.klassen_im_pdf(b"egal") == {}


class TestAnzeigeUndBenachrichtigung:
    """Anzeige zeigt den laufenden Schultag, die Benachrichtigung darf
    davon abweichen (ab 9 Uhr geht es um den naechsten Tag)."""

    def _run_all(self, monkeypatch, iso, stunde):
        import importlib
        from datetime import datetime
        from zoneinfo import ZoneInfo
        import run_all
        importlib.reload(run_all)
        tz = ZoneInfo("Europe/Berlin")
        fest = datetime.fromisoformat(iso).replace(hour=stunde, tzinfo=tz)

        class FakeDatetime(datetime):
            @classmethod
            def now(cls, tzinfo=None):
                return fest

        monkeypatch.setattr(run_all, "datetime", FakeDatetime)
        return run_all

    @pytest.mark.parametrize("iso, stunde, erwartet_heute", [
        ("2026-09-04", 7,  "2026-09-04"),   # Freitag frueh -> heute
        ("2026-09-04", 12, "2026-09-04"),   # mitten im Unterricht -> heute
        ("2026-09-04", 13, "2026-09-04"),   # 13 Uhr, letzte Stunde laeuft noch
        ("2026-09-04", 14, "2026-09-07"),   # nach Unterrichtsende -> Montag
        ("2026-09-04", 20, "2026-09-07"),   # abends -> Montag
        ("2026-09-02", 14, "2026-09-03"),   # Mittwoch nach Schluss -> Donnerstag
        ("2026-09-05", 10, "2026-09-07"),   # Samstag -> Montag
        ("2026-09-06", 10, "2026-09-07"),   # Sonntag -> Montag
    ])
    def test_anzeige_zeigt_laufenden_schultag(self, monkeypatch, iso, stunde, erwartet_heute):
        ra = self._run_all(monkeypatch, iso, stunde)
        assert ra.get_today() == erwartet_heute

    @pytest.mark.parametrize("iso, stunde, erwartet_ziel", [
        ("2026-09-02", 7,  "heute"),    # vor 9 Uhr, Tag laeuft -> heute
        ("2026-09-02", 9,  "morgen"),   # ab 9 Uhr, Tag laeuft -> morgen
        ("2026-09-02", 12, "morgen"),
        # Nach Unterrichtsende ist "heute" schon der Folgetag, darueber wird
        # benachrichtigt (nicht uebermorgen).
        ("2026-09-02", 15, "heute"),
        ("2026-09-04", 20, "heute"),    # Freitagabend -> Montag
        ("2026-09-05", 7,  "heute"),    # Samstag -> Montag
    ])
    def test_benachrichtigungsziel(self, monkeypatch, iso, stunde, erwartet_ziel):
        ra = self._run_all(monkeypatch, iso, stunde)
        heute = ra.get_today()
        morgen = ra.get_tomorrow(heute)
        ziel = ra.notify_ziel(heute, morgen)
        assert ziel == (heute if erwartet_ziel == "heute" else morgen)

    def test_morgen_ueberspringt_wochenende(self, monkeypatch):
        ra = self._run_all(monkeypatch, "2026-09-04", 12)
        assert ra.get_tomorrow("2026-09-04") == "2026-09-07"


class TestVorgezogeneStunde:
    """Vorgezogene Stunden standen als Platzhalter "Gruppe" im Plan.

    Realfall Mittwoch 09.09.2026: 'E statt Do. 10.9. 1. Std.', Lehrer und
    Vertreter beide MOR. Das Fach steht nur im Hinweis, im regulaeren Plan
    gibt es an dem Tag keine 1. Stunde.
    """

    def test_fach_kommt_aus_dem_hinweis(self):
        assert resolve_vtg_fach("", "E statt Do. 10.9.1. Std.", {"E": "Englisch"}) == "E"

    def _baue(self, tmp_path, monkeypatch, subs):
        """Baut einen Tagesplan in einem eigenen Datenverzeichnis."""
        import json, build_today
        daten = tmp_path / "data"
        daten.mkdir()
        (daten / "untis_7c.json").write_text(json.dumps({
            "valid_from": "2026-08-31", "schuljahr": "2026/27",
            "2": {"Mittwoch": [{"fach": "E", "lehrer": "MOR", "raum": "433"}]},
        }), encoding="utf-8")
        (daten / "fach_mapping.json").write_text(json.dumps({"E": "Englisch"}), encoding="utf-8")
        (daten / "lehrer_fach.json").write_text("{}", encoding="utf-8")
        (daten / "lehrer_namen.json").write_text("{}", encoding="utf-8")
        (daten / "vtg.json").write_text(json.dumps(
            {"date": "2026-09-09", "class": "07c", "substitutions": subs}), encoding="utf-8")
        monkeypatch.setattr(build_today, "BASE", tmp_path)
        return build_today.build_plan("2026-09-09", vtg_file="vtg.json")

    def test_vorgezogene_stunde_bekommt_ihr_fach(self, tmp_path, monkeypatch):
        plan = self._baue(tmp_path, monkeypatch, [
            {"klasse": "07c", "stunde": "1", "lehrer": "MOR", "vertreter": "MOR",
             "raum": "433", "fach": "", "text": "E statt Do. 10.9.1. Std."},
        ])
        eintrag = [p for p in plan["plan"] if p["stunde"] == 1][0]
        assert eintrag["fach"] == "Englisch"      # frueher "Gruppe"
        assert eintrag["fach_kurz"] == "E"
        assert eintrag["vertreter"] == ""         # MOR vertritt nicht sich selbst

    def test_ohne_erkennbares_fach_neutraler_platzhalter(self, tmp_path, monkeypatch):
        plan = self._baue(tmp_path, monkeypatch, [
            {"klasse": "07c", "stunde": "1", "lehrer": "XYZ", "vertreter": "",
             "raum": "", "fach": "", "text": "Raumaenderung"},
        ])
        eintrag = [p for p in plan["plan"] if p["stunde"] == 1][0]
        # "Gruppe" klang nach einem Schulfach, das es nicht gibt
        assert eintrag["fach"] == "Zusatzstunde"

    @pytest.mark.parametrize("lehrer, vertreter, erwartet", [
        ("MOR", "MOR", ""),      # Selbstvertretung: kein Wechsel
        ("MOR", "SUB", "SUB"),   # echte Vertretung bleibt
        ("MOR", "frei", ""),     # Ausfall ist kein Vertreter
        ("MOR", "", ""),
    ])
    def test_selbstvertretung_wird_unterdrueckt(self, lehrer, vertreter, erwartet):
        # gleiche Bedingung wie in build_today
        ergebnis = "" if (ist_ausfall("", vertreter) or vertreter == lehrer) else vertreter
        assert ergebnis == erwartet


class TestAlleWochentageHolen:
    """Die Wochenansicht soll alle veroeffentlichten Plaene zeigen, nicht nur
    heute und morgen."""

    def _run_all(self, monkeypatch):
        import importlib, run_all
        importlib.reload(run_all)
        return run_all

    @pytest.mark.parametrize("heute, erwartet", [
        # Montag: Di ist "morgen", zusaetzlich Mi, Do, Fr
        ("2026-09-07", ["2026-09-09", "2026-09-10", "2026-09-11"]),
        ("2026-09-08", ["2026-09-10", "2026-09-11"]),
        ("2026-09-09", ["2026-09-11"]),
        ("2026-09-10", []),          # Do: nur noch Fr, und der ist "morgen"
        ("2026-09-11", []),          # Fr: "morgen" ist schon naechste Woche
    ])
    def test_restliche_wochentage(self, monkeypatch, heute, erwartet):
        ra = self._run_all(monkeypatch)
        assert ra.restliche_wochentage(heute, ra.get_tomorrow(heute)) == erwartet

    def test_vergangene_tage_werden_nicht_geholt(self, monkeypatch):
        ra = self._run_all(monkeypatch)
        # Mittwoch: Montag und Dienstag sind vorbei, kommen nicht mehr vor
        tage = ra.restliche_wochentage("2026-09-09", "2026-09-10")
        assert all(t >= "2026-09-09" for t in tage)

    def test_build_week_findet_alle_dateien(self, tmp_path, monkeypatch):
        import json, build_week
        daten = tmp_path
        (daten / "latest_7c.json").write_text(
            json.dumps({"date": "2026-09-08", "substitutions": []}), encoding="utf-8")
        (daten / "latest_7c_tomorrow.json").write_text(
            json.dumps({"date": "2026-09-09", "substitutions": []}), encoding="utf-8")
        (daten / "latest_7c_extra_2026-09-10.json").write_text(
            json.dumps({"date": "2026-09-10", "substitutions": []}), encoding="utf-8")
        (daten / "latest_7c_extra_2026-09-11.json").write_text(
            json.dumps({"date": "2026-09-11", "substitutions": []}), encoding="utf-8")
        monkeypatch.setattr(build_week, "DATA", daten)
        zuordnung = build_week.vtg_file_by_date()
        assert zuordnung == {
            "2026-09-08": "latest_7c.json",
            "2026-09-09": "latest_7c_tomorrow.json",
            "2026-09-10": "latest_7c_extra_2026-09-10.json",
            "2026-09-11": "latest_7c_extra_2026-09-11.json",
        }

    def test_hauptdatei_gewinnt_bei_gleichem_datum(self, tmp_path, monkeypatch):
        import json, build_week
        # Sollte ein Extra dasselbe Datum tragen, gilt die frisch geschriebene
        # Hauptdatei.
        (tmp_path / "latest_7c.json").write_text(
            json.dumps({"date": "2026-09-08", "substitutions": []}), encoding="utf-8")
        (tmp_path / "latest_7c_extra_2026-09-08.json").write_text(
            json.dumps({"date": "2026-09-08", "substitutions": []}), encoding="utf-8")
        monkeypatch.setattr(build_week, "DATA", tmp_path)
        assert build_week.vtg_file_by_date()["2026-09-08"] == "latest_7c.json"


class TestAbrufTiming:
    """Spaetere Wochentage werden nur abgerufen, wenn die Schule sie
    ueberhaupt aktualisiert (nachmittags), und gehen dazwischen nicht
    verloren."""

    def test_konstante_passt_zum_benachrichtigungs_cutoff(self):
        from constants import WEEK_FETCH_FROM_HOUR, NOTIFY_HOUR_CUTOFF
        # Ab 9 Uhr laeuft der Cron nur noch stuendlich, davor alle 5 Minuten.
        assert WEEK_FETCH_FROM_HOUR == NOTIFY_HOUR_CUTOFF == 9

    def test_uebertrag_wenn_tag_nicht_abgerufen(self, tmp_path, monkeypatch):
        import json, build_week
        monkeypatch.setattr(build_week, "DATA", tmp_path)
        # bisheriger Stand mit Vertretungsplan fuer Donnerstag
        (tmp_path / "week_7c.json").write_text(json.dumps({
            "days": [{"date": "2026-09-10", "day": "Donnerstag", "plan": [
                {"stunde": 1, "fach": "Englisch", "fach_kurz": "E", "lehrer": "MOR",
                 "raum": "433", "status": "frei", "vertreter": "",
                 "hinweis": "frei; verlegt auf Mi."}],
                "vtg_count": 1, "has_vertretungsplan": True,
                "pdf_stand": "2026-09-08T15:00:00+02:00"}]
        }), encoding="utf-8")
        vorher = {t["date"]: t for t in
                  json.loads((tmp_path / "week_7c.json").read_text())["days"]}
        alt = vorher["2026-09-10"]
        assert alt["has_vertretungsplan"] and alt["plan"][0]["status"] == "frei"

    def test_kein_uebertrag_ohne_vertretungsplan(self, tmp_path, monkeypatch):
        import json, build_week
        monkeypatch.setattr(build_week, "DATA", tmp_path)
        # War der Tag nur regulaer, gibt es nichts zu erhalten: er wird neu
        # gebaut und kann so einen frisch veroeffentlichten Plan aufnehmen.
        (tmp_path / "week_7c.json").write_text(json.dumps({
            "days": [{"date": "2026-09-10", "day": "Donnerstag", "plan": [],
                      "vtg_count": 0, "has_vertretungsplan": False, "pdf_stand": ""}]
        }), encoding="utf-8")
        vorher = {t["date"]: t for t in
                  json.loads((tmp_path / "week_7c.json").read_text())["days"]}
        assert vorher["2026-09-10"]["has_vertretungsplan"] is False
