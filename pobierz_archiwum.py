#!/usr/bin/env python3
"""
Pobiera SAME WYNIKI (bez statystyk) archiwalnych sezonow Widzewa
z API-Football - wylacznie do zasilenia historii H2H.

Rozni sie od pobierz.py: jedno zapytanie na CALY sezon (lista meczow
przychodzi za jednym razem), zero zapytan per-mecz o statystyki -
do H2H nie potrzeba xG, strzalow, kartek. Dzieki temu jest to bardzie
przyjazne dla darmowego limitu API niz pobierz.py (ktory robi ~34
zapytania na sezon).

Wyniki tych sezonow NIE wchodza do glownej analizy strony (pasek
srednich, wykresy, tabele) - trafiaja do osobnego archiwum, ktore
przeszukuje wylacznie funkcja H2H po kliknieciu na mecz.

Wymaga klucz.txt w tym samym katalogu (ten sam klucz co pobierz.py).

Uzycie:
    python pobierz_archiwum.py 2022 2023 2024

Kazdy argument to rok startowy sezonu (2022 = sezon 2022/23).
Darmowy plan API-Football obejmuje sezony 2022-2024 (sprawdzone na
zywo w tej sesji).
"""

import csv
import json
import pathlib
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
API_BASE = "https://v3.football.api-sports.io"
TEAM_ID = 6962  # Widzew Lodz - potwierdzone wczesniej w tym projekcie
PUCHAROWE = ("cup", "puchar")

KOLUMNY = [  # ten sam uklad co zwykle sezonowe CSV - staty po prostu puste
    "season", "round", "date", "competition", "venue", "home_team", "away_team",
    "score_ht", "score_ft", "xg_home", "xg_away", "shots_home", "shots_away",
    "sot_home", "sot_away", "bc_home", "bc_away", "passes_home", "passes_away",
    "passes_acc_home", "passes_acc_away", "pass_pct_home", "pass_pct_away",
    "poss_home", "poss_away", "position", "fixture_id",
]


def wczytaj_klucz():
    p = HERE / "klucz.txt"
    if not p.exists():
        sys.exit("BLAD: brak klucz.txt w tym katalogu.")
    k = p.read_text(encoding="utf-8").strip()
    if not k:
        sys.exit("BLAD: klucz.txt jest pusty.")
    return k


def api_get(sciezka, params, klucz):
    url = f"{API_BASE}{sciezka}?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"x-apisports-key": klucz})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        sys.exit(f"BLAD HTTP {e.code}: {e.read().decode()[:300]}")


def numer_kolejki(runda):
    """'Regular Season - 12' -> 12"""
    m = re.search(r"(\d+)\s*$", runda or "")
    return int(m.group(1)) if m else None


def pobierz_sezon(sezon, klucz):
    dane = api_get("/fixtures", {"team": TEAM_ID, "season": sezon}, klucz)
    if dane.get("errors"):
        print(f"  BLAD API: {dane['errors']}")
        return []

    wiersze = []
    for f in dane.get("response", []):
        liga = f.get("league", {})
        # Filtr sprawdzony na zywo w tej sesji: obiekt league na /fixtures
        # NIE MA pola 'type' (to bylo zle zalozenie w pobierz.py, juz
        # naprawione tam) - filtrujemy po kraju + wykluczeniu pucharow.
        if (liga.get("country") or "").lower() != "poland":
            continue
        nazwa_ligi = (liga.get("name") or "").lower()
        if any(p in nazwa_ligi for p in PUCHAROWE):
            continue
        if f["fixture"]["status"]["short"] not in ("FT", "AET", "PEN"):
            continue  # tylko rozegrane - archiwum nie potrzebuje terminarza

        gole = f.get("goals", {})
        if gole.get("home") is None:
            continue

        home = f["teams"]["home"]["name"]
        away = f["teams"]["away"]["name"]

        wiersze.append({
            "season": f"{sezon}/{str(sezon + 1)[2:]}",
            "round": numer_kolejki(liga.get("round")),
            "date": (f["fixture"].get("date") or "")[:10],
            "competition": liga.get("name"),
            "venue": "H" if "Widzew" in home else "A",
            "home_team": home,
            "away_team": away,
            "score_ft": f"{gole['home']}:{gole['away']}",
            "fixture_id": f["fixture"]["id"],
        })
    return wiersze


def zapisz(sezon, wiersze):
    wiersze = sorted(wiersze, key=lambda r: r["round"] or 0, reverse=True)
    plik = HERE / f"archiwum-{sezon}-{str(sezon + 1)[2:]}.csv"
    with open(plik, "w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=KOLUMNY, extrasaction="ignore")
        wr.writeheader()
        for w in wiersze:
            wr.writerow({k: w.get(k, "") for k in KOLUMNY})
    return plik


def main():
    if len(sys.argv) < 2:
        sys.exit("Uzycie: python pobierz_archiwum.py 2022 2023 2024")
    klucz = wczytaj_klucz()

    for arg in sys.argv[1:]:
        sezon = int(arg)
        print(f"Sezon {sezon}/{str(sezon + 1)[2:]}...")
        wiersze = pobierz_sezon(sezon, klucz)
        if not wiersze:
            print("  Zero meczow - nic nie zapisuje.")
            continue
        plik = zapisz(sezon, wiersze)
        print(f"  Zapisano {plik.name}: {len(wiersze)} meczow")
        time.sleep(1)  # uprzejmosc wobec API, nie zwiekszamy limitu bez potrzeby


if __name__ == "__main__":
    main()
