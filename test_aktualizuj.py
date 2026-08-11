# -*- coding: utf-8 -*-
"""
Testy funkcji, ktore w trakcie prac realnie psuly dane.

Uruchomienie:
    pip install pytest
    python -m pytest -q

Scrapera tu nie ma - strona jest cudza i zmienna, testowanie jej z automatu
niczego nie chroni. Testowane jest to, co dziala na juz pobranych danych:
dopasowanie etykiet, rozbijanie podan, laczenie wierszy, kontrole i zapis CSV.
"""

import csv
import importlib.util
import pathlib

import pytest

TU = pathlib.Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("akt", TU / "aktualizuj.py")
akt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(akt)


# ---------------------------------------------------------------------------
# dopasuj_etykiete - najgrozniejsze miejsce w calym skrypcie
# ---------------------------------------------------------------------------

# Wszystkie 41 etykiet odczytanych z prawdziwej tabeli Flashscore
# (mecz Jagiellonia - Widzew, 2026-08-09).
ETYKIETY_BRANE = [
    ("Oczekiwane gole (xG)", "xg"),
    ("Posiadanie piłki", "poss"),
    ("Strzały łącznie", "shots"),
    ("Strzały na bramkę", "sot"),
    ("Wielkie szanse", "bc"),
    ("Podania", "passes"),
]

# Te MUSZA byc odrzucone. Kazda z nich byla kiedys lapana przez dopasowanie
# po fragmencie tekstu i nadpisywala wlasciwa metryke.
ETYKIETY_ODRZUCANE = [
    "xG na bramkę (xGOT)",      # lapalo sie na "xg"
    "xGot przeciw",             # lapalo sie na "xg" i nadpisywalo je jako ostatnie
    "Strzały niecelne",         # lapalo sie na "strzaly"
    "Strzały zablokowane",
    "Strzały z pola karnego",
    "Strzały spoza pola karnego",
    "Strzał w poprzeczkę",
    "Długie podania",           # lapalo sie na "podania"
    "Celne podania prostopadłe",
    "Podania w strefę obrony przeciwnika",
    "Oczekiwane asysty (xA)",
    "Rzuty rożne",
    "Żółte kartki",
    "Bramki strzelone głową",
    "Kontakty w polu karnym przeciwnika",
    "Spalone",
    "Rzuty wolne",
    "Dośrodkowania",
    "Wrzuty z autu",
    "Faule",
    "Próby odbioru piłki",
    "Wygrane pojedynki",
    "Wybicia",
    "Przechwyty",
    "Błędy skutkujące strzałem",
    "Błędy skutkujące golem",
    "Obrony bramkarza",
    "Zapobiegnięcia utracie gola",
    "Wykopy od bramki",
]


@pytest.mark.parametrize("etykieta,oczekiwane", ETYKIETY_BRANE)
def test_etykiety_ktore_bierzemy(etykieta, oczekiwane):
    assert akt.dopasuj_etykiete(etykieta) == oczekiwane


@pytest.mark.parametrize("etykieta", ETYKIETY_ODRZUCANE)
def test_etykiety_ktore_odrzucamy(etykieta):
    assert akt.dopasuj_etykiete(etykieta) is None, (
        f"{etykieta!r} zostalo dopasowane - dopasowanie znow jest za chciwe")


def test_z_pelnej_tabeli_bierzemy_dokladnie_szesc():
    wszystkie = [e for e, _ in ETYKIETY_BRANE] + ETYKIETY_ODRZUCANE
    brane = [e for e in wszystkie if akt.dopasuj_etykiete(e)]
    assert len(brane) == 6


def test_dopasowanie_ignoruje_wielkosc_liter_i_biale_znaki():
    assert akt.dopasuj_etykiete("  STRZAŁY   NA  BRAMKĘ ") == "sot"


# ---------------------------------------------------------------------------
# rozbij_podania - Flashscore zmienil format w trakcie prac
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("wejscie,oczekiwane", [
    ("355/458 (78%)", (458, 355, 78.0)),      # starszy format
    ("77%\n(353/456)", (456, 353, 77.0)),     # format z pelnej zakladki
    ("206/299", (299, 206, 69)),              # bez procentu - liczony z ulamka
    ("32%\n(16/50)", (50, 16, 32.0)),
    ("", (None, None, None)),
    (None, (None, None, None)),
    ("brak danych", (None, None, None)),
])
def test_rozbij_podania(wejscie, oczekiwane):
    assert akt.rozbij_podania(wejscie) == oczekiwane


def test_procent_zgodny_z_ulamkiem():
    total, celne, proc = akt.rozbij_podania("77%\n(353/456)")
    assert abs(round(100 * celne / total) - proc) <= 1


# ---------------------------------------------------------------------------
# liczby i tekst
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("wejscie,oczekiwane", [
    ("1.09", 1.09), ("60%", 60.0), ("1,21", 1.21), ("18", 18.0),
    ("", None), (None, None), ("-", None), ("-0.26", -0.26),
])
def test_liczba(wejscie, oczekiwane):
    assert akt.liczba(wejscie) == oczekiwane


def test_bez_ogonkow():
    assert akt.bez_ogonkow("Widzew Łódź") == "widzew lodz"
    assert akt.bez_ogonkow("Jagiellonia Białystok") == "jagiellonia bialystok"


def test_rok_dla_daty_nie_wyprzedza_terazniejszosci():
    """Flashscore nie podaje roku. Data nie moze wyjsc w przyszlosci."""
    from datetime import datetime
    dzis = datetime.now()
    wynik = akt.rok_dla_daty(dzis.day, dzis.month)
    assert wynik.startswith(str(dzis.year))


# ---------------------------------------------------------------------------
# czy_pelna - odsiewa kafelek-skrot z podsumowania meczu
# ---------------------------------------------------------------------------

SKROT = [("Oczekiwane gole (xG)", "1.08", "1.10"), ("Posiadanie piłki", "60%", "40%"),
         ("Strzały łącznie", "18", "16"), ("Wielkie szanse", "2", "2"),
         ("Kontakty w polu karnym przeciwnika", "22", "17")]

PELNA = SKROT + [("Strzały na bramkę", "5", "5"), ("Podania", "77%\n(353/456)", "69%\n(208/302)")]


def test_kafelek_z_podsumowania_nie_jest_pelna_tabela():
    assert akt.czy_pelna(SKROT) is False


def test_pelna_zakladka_przechodzi():
    assert akt.czy_pelna(PELNA) is True


# ---------------------------------------------------------------------------
# CSV: zapis nie moze zmieniac pliku, ktorego nie zmieniamy
# ---------------------------------------------------------------------------

NAGLOWKI = akt.KOLUMNY

WIERSZ_K3 = {
    "season": "2026/27", "round": "3", "date": "2026-08-09",
    "competition": "Ekstraklasa", "venue": "A",
    "home_team": "Jagiellonia Białystok", "away_team": "Widzew Łódź",
    "score_ht": "", "score_ft": "0:2", "xg_home": "1.09", "xg_away": "1.10",
    "shots_home": "18", "shots_away": "16", "sot_home": "5", "sot_away": "5",
    "bc_home": "2", "bc_away": "2", "passes_home": "458", "passes_away": "299",
    "passes_acc_home": "355", "passes_acc_away": "206",
    "pass_pct_home": "78", "pass_pct_away": "69",
    "poss_home": "61", "poss_away": "39", "position": "7", "fixture_id": "WhZpaOLb",
}

ZAPOWIEDZ_K4 = dict({k: "" for k in NAGLOWKI}, **{
    "season": "2026/27", "round": "4", "date": "2026-08-15",
    "competition": "Ekstraklasa", "venue": "H",
    "home_team": "Widzew Łódź", "away_team": "Korona Kielce",
    "fixture_id": "dtlSbFRF",
})


def zapisz_probny(tmp_path, wiersze):
    sciezka = tmp_path / "2026-27.csv"
    akt.zapisz_csv(sciezka, wiersze, NAGLOWKI)
    return sciezka


def test_zapis_zachowuje_konce_linii_crlf(tmp_path):
    """Plik w repo ma \\r\\n. Zapis z \\n zrobilby diff na calej tresci."""
    sciezka = zapisz_probny(tmp_path, [ZAPOWIEDZ_K4, WIERSZ_K3])
    surowe = sciezka.read_bytes()
    assert b"\r\n" in surowe
    assert b"\n" not in surowe.replace(b"\r\n", b"")


def test_odczyt_i_zapis_daja_identyczny_plik(tmp_path):
    sciezka = zapisz_probny(tmp_path, [ZAPOWIEDZ_K4, WIERSZ_K3])
    przed = sciezka.read_bytes()
    wiersze, naglowki = akt.wczytaj_csv(sciezka)
    akt.zapisz_csv(sciezka, wiersze, naglowki)
    assert sciezka.read_bytes() == przed


def test_naglowki_pliku_zgadzaja_sie_z_kolumnami(tmp_path):
    sciezka = zapisz_probny(tmp_path, [WIERSZ_K3])
    with open(sciezka, newline="", encoding="utf-8") as f:
        assert next(csv.reader(f)) == NAGLOWKI


# ---------------------------------------------------------------------------
# scal_wiersz - wiersz zapowiedzi ma byc uzupelniony, nie odrzucony
# ---------------------------------------------------------------------------

def wynik_meczu(nadpisania=None):
    r = dict(ZAPOWIEDZ_K4)
    r.update({"score_ft": "2:1", "xg_home": "1.80", "xg_away": "0.90",
              "shots_home": "14", "shots_away": "9", "sot_home": "6", "sot_away": "3",
              "bc_home": "3", "bc_away": "1", "passes_home": "400", "passes_away": "320",
              "passes_acc_home": "332", "passes_acc_away": "250",
              "pass_pct_home": "83", "pass_pct_away": "78",
              "poss_home": "56", "poss_away": "44"})
    if nadpisania:
        r.update(nadpisania)
    return r


def test_zapowiedz_zostaje_uzupelniona_w_miejscu():
    wiersze = [dict(ZAPOWIEDZ_K4), dict(WIERSZ_K3)]
    wynik, co = akt.scal_wiersz(wiersze, wynik_meczu())
    assert co == "uzupelniony"
    assert len(wynik) == 2, "nie moze powstac drugi wiersz dla tej samej kolejki"
    k4 = [w for w in wynik if w["fixture_id"] == "dtlSbFRF"][0]
    assert k4["score_ft"] == "2:1"
    assert k4["round"] == "4"


def test_uzupelnianie_nie_gubi_pol_ktorych_nowy_wiersz_nie_ma():
    zapowiedz = dict(ZAPOWIEDZ_K4, position="6")
    wiersze = [zapowiedz]
    wynik, _ = akt.scal_wiersz(wiersze, wynik_meczu({"position": ""}))
    assert wynik[0]["position"] == "6"


def test_mecz_juz_zapisany_nie_jest_ruszany():
    wiersze = [dict(WIERSZ_K3)]
    wynik, co = akt.scal_wiersz(wiersze, wynik_meczu({"fixture_id": "WhZpaOLb"}))
    assert co == "juz_jest"
    assert wynik[0]["xg_home"] == "1.09", "istniejacy wiersz zostal nadpisany"


def test_nowy_mecz_ladnie_na_gorze():
    wiersze = [dict(WIERSZ_K3)]
    wynik, co = akt.scal_wiersz(wiersze, wynik_meczu({"fixture_id": "ZZZZ1234"}))
    assert co == "dodany"
    assert wynik[0]["fixture_id"] == "ZZZZ1234"
    assert len(wynik) == 2


# ---------------------------------------------------------------------------
# sprawdz_przed_zapisem
# ---------------------------------------------------------------------------

def dobry_wiersz(nadpisania=None):
    r = dict(WIERSZ_K3)
    if nadpisania:
        r.update(nadpisania)
    return r


def test_dobry_wiersz_przechodzi():
    assert akt.sprawdz_przed_zapisem(dobry_wiersz()) == []


def test_wiersz_widmo_jest_odrzucany():
    """Statystyki sa, ale nie wiadomo czyje ani z kiedy."""
    widmo = dobry_wiersz({"home_team": "", "away_team": "", "date": "", "score_ft": ""})
    bledy = akt.sprawdz_przed_zapisem(widmo)
    assert len(bledy) >= 4
    assert any("Widzew" in b for b in bledy)


def test_mecz_bez_widzewa_jest_odrzucany():
    obcy = dobry_wiersz({"home_team": "Lech Poznań", "away_team": "Legia Warszawa"})
    assert any("Widzew" in b for b in akt.sprawdz_przed_zapisem(obcy))


def test_ta_sama_nazwa_po_obu_stronach():
    bledny = dobry_wiersz({"home_team": "Jagiellonia Białystok",
                           "away_team": "Jagiellonia Białystok"})
    assert akt.sprawdz_przed_zapisem(bledny) != []


def test_strzaly_na_bramke_nie_moga_przekraczac_wszystkich():
    assert any("strzaly na bramke" in b
               for b in akt.sprawdz_przed_zapisem(dobry_wiersz({"sot_home": "20"})))


def test_posiadanie_musi_sumowac_sie_do_stu():
    assert any("posiadanie" in b
               for b in akt.sprawdz_przed_zapisem(dobry_wiersz({"poss_away": "30"})))


def test_procent_podan_musi_zgadzac_sie_z_ulamkiem():
    assert any("podan" in b
               for b in akt.sprawdz_przed_zapisem(dobry_wiersz({"pass_pct_home": "50"})))


@pytest.mark.parametrize("xg", ["9.5", "-1"])
def test_xg_poza_rozsadnym_zakresem(xg):
    assert any("xG" in b for b in akt.sprawdz_przed_zapisem(dobry_wiersz({"xg_home": xg})))


def test_brak_statystyk_jest_bledem():
    """Zmieniony uklad strony daje puste odczyty - to nie moze przejsc."""
    puste = dobry_wiersz({"shots_home": "", "sot_home": "", "xg_home": ""})
    assert akt.sprawdz_przed_zapisem(puste) != []


@pytest.mark.parametrize("wynik", ["2-1", "2:1:0", "wygrana", "2;1"])
def test_dziwny_format_wyniku(wynik):
    assert any("wynik" in b for b in akt.sprawdz_przed_zapisem(dobry_wiersz({"score_ft": wynik})))


@pytest.mark.parametrize("data", ["15.08.2026", "2026/08/15", "15-08-2026"])
def test_dziwny_format_daty(data):
    assert any("data" in b for b in akt.sprawdz_przed_zapisem(dobry_wiersz({"date": data})))


def test_rok_z_daty_nie_pasuje_do_sezonu():
    assert any("sezon" in b
               for b in akt.sprawdz_przed_zapisem(dobry_wiersz({"date": "2024-08-09"})))
