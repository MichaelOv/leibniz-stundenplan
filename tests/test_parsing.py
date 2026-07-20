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
from parse_untis import extract_valid_from
from build_today import parse_stunden, clean, clean_lehrer, fach_name, resolve_vtg_fach

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
    ])
    def test_no_match(self, kandidat, ziel):
        assert class_matches(kandidat, ziel) is False


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


class TestFachName:
    def test_bekanntes_kuerzel(self):
        assert fach_name("D", {"D": "Deutsch"}) == "Deutsch"

    def test_fuehrender_punkt_wird_entfernt(self):
        assert fach_name(".M", {"M": "Mathe"}) == "Mathe"

    def test_unbekanntes_kuerzel_bleibt(self):
        assert fach_name("XX", {}) == "XX"
