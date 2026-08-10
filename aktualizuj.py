#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
aktualizuj.py - jedna komenda, cala reszta sama.

    python aktualizuj.py                 # pelny przebieg: pobierz, zapisz, przelicz, wypchnij
    python aktualizuj.py --sucho         # przejdz cala droge, pokaz wiersz, NIC nie zapisuj
    python aktualizuj.py --widok         # pokaz okno przegladarki (do ogladania)
    python aktualizuj.py --diagnostyka   # wypisz, co skrypt widzi na stronie (do mapowania selektorow)
    python aktualizuj.py --mid WhZpaOLb  # weź konkretny mecz, nie szukaj najnowszego
    python aktualizuj.py --pozycja 7     # wpisz pozycje w tabeli recznie

Zasada bezpieczenstwa: CSV jest zapisywany PRZED przeliczeniem, ale jesli
zbuduj.py zglosi jakiekolwiek ostrzezenie, plik jest cofany przez
`git checkout` i nic nie idzie do repo.
"""

import argparse
import csv
import glob
import io
import os
import pathlib
import re
import subprocess
import sys
from datetime import datetime

HERE = pathlib.Path(__file__).resolve().parent
WIDZEW = "Widzew Łódź"
ROZGRYWKI = "Ekstraklasa"
ZRZUTY = HERE / "zrzuty"

# ---------------------------------------------------------------------------
# DO UZUPELNIENIA PRZEZ CIEBIE (raz)
# ---------------------------------------------------------------------------
# Wejdz na Flashscore, znajdz strone Widzewa -> zakladka "Wyniki",
# skopiuj adres z paska przegladarki i wklej ponizej.
URL_WYNIKI = "https://www.flashscore.pl/druzyna/widzew-lodz/rNOIW3uC/wyniki/"

# ---------------------------------------------------------------------------
# WARSTWA SELEKTOROW - jedyne miejsce, ktore trzeba poprawic, gdy Flashscore
# przebuduje strone. Kazdy klucz to lista kandydatow, prubowanych po kolei.
# ---------------------------------------------------------------------------
SELEKTORY = {
    # wiersz meczu na liscie wynikow
    "wiersz_meczu": [
        '[data-testid="wcl-matchRow"]',
        ".event__match",
    ],
    # wiersz statystyki na zakladce STATYSTYKI (jedna metryka = jeden wiersz)
    "wiersz_statystyki": [
        '[data-testid="wcl-statistics"]',
        ".stat__row",
        ".statRow",
    ],
    # w obrebie wiersza: etykieta i dwie wartosci
    "etykieta": [
        '[data-testid="wcl-statistics-category"]',
        ".stat__categoryName",
        ".statCategoryName",
    ],
    "wartosc": [
        '[data-testid="wcl-statistics-value"]',
        ".stat__homeValue, .stat__awayValue",
        ".statHomeValue, .statAwayValue",
    ],
    # naglowek z nazwa rozgrywek i numerem kolejki, np. "EKSTRAKLASA - RUNDA 3"
    "naglowek_rozgrywek": [
        '[data-testid="wcl-scores-overline-02"]',
        ".tournamentHeader__country",
        ".description__country",
    ],
    "nazwa_gospodarza": [
        '[data-testid="wcl-participantName"]',
        ".duelParticipant__home .participant__participantName",
        ".event__participant--home",
    ],
    "nazwa_goscia": [
        '[data-testid="wcl-participantName"]',
        ".duelParticipant__away .participant__participantName",
        ".event__participant--away",
    ],
    # nazwy druzyn WEWNATRZ wiersza na liscie wynikow
    "wiersz_gospodarz": [
        ".event__homeParticipant",
        ".event__participant--home",
        '[data-testid="wcl-matchRow-participant-home"]',
    ],
    "wiersz_gosc": [
        ".event__awayParticipant",
        ".event__participant--away",
        '[data-testid="wcl-matchRow-participant-away"]',
    ],
}

# Etykieta na Flashscore -> nasz prefiks kolumny. Pierwsze trafienie wygrywa,
# dlatego "Strzały na bramkę" MUSI byc sprawdzane przed "Strzały".
# Dopasowanie DOKLADNE, nie po fragmencie. Pelna tabela Flashscore ma 41
# wierszy, w tym "Strzaly niecelne", "Strzaly zablokowane", "Dlugie podania"
# czy "xGot przeciw" - dopasowanie po fragmencie lapalo je wszystkie i
# nadpisywalo wlasciwe metryki wartosciami z zupelnie innych wierszy.
ETYKIETY_DOKLADNE = {
    "oczekiwane gole (xg)": "xg",
    "oczekiwane gole": "xg",
    "posiadanie pilki": "poss",
    "posiadanie": "poss",
    "strzaly lacznie": "shots",
    "strzaly ogolem": "shots",
    "strzaly na bramke": "sot",
    "strzaly celne": "sot",
    "wielkie szanse": "bc",
    "sytuacje bramkowe": "bc",
    "podania": "passes",
}


def dopasuj_etykiete(tekst):
    """Zwraca prefiks kolumny albo None. Tylko dokladne trafienie."""
    return ETYKIETY_DOKLADNE.get(re.sub(r"\s+", " ", bez_ogonkow(tekst)))


KOLUMNY = [
    "season", "round", "date", "competition", "venue", "home_team", "away_team",
    "score_ht", "score_ft", "xg_home", "xg_away", "shots_home", "shots_away",
    "sot_home", "sot_away", "bc_home", "bc_away", "passes_home", "passes_away",
    "passes_acc_home", "passes_acc_away", "pass_pct_home", "pass_pct_away",
    "poss_home", "poss_away", "position", "fixture_id",
]


# ---------------------------------------------------------------------------
# wypisywanie krokow
# ---------------------------------------------------------------------------
class Krok:
    def __init__(self):
        self.n = 0

    def __call__(self, opis):
        self.n += 1
        print(f"[{self.n}] {opis} ... ", end="", flush=True)

    def ok(self, dopisek=""):
        print("ok" + (f" ({dopisek})" if dopisek else ""))

    def stop(self, powod):
        print("STOP")
        print(f"\n    {powod}\n")


krok = Krok()


def stop(powod, kod=1):
    krok.stop(powod)
    sys.exit(kod)


# ---------------------------------------------------------------------------
# pomocnicze: liczby i tekst
# ---------------------------------------------------------------------------
def bez_ogonkow(s):
    tab = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")
    return (s or "").translate(tab).lower().strip()


def liczba(s):
    """'1.09' -> 1.09 ; '78%' -> 78.0 ; '' -> None"""
    if s is None:
        return None
    t = str(s).replace("%", "").replace(",", ".").strip()
    if not t:
        return None
    try:
        return float(t)
    except ValueError:
        return None


def rozbij_podania(s):
    """'355/458 (78%)' -> (458, 355, 78.0). Zwraca (total, celne, procent)."""
    if not s:
        return (None, None, None)
    m = re.search(r"(\d+)\s*/\s*(\d+)", s)
    celne = total = None
    if m:
        celne, total = int(m.group(1)), int(m.group(2))
    p = re.search(r"(\d+(?:[.,]\d+)?)\s*%", s)
    proc = liczba(p.group(1)) if p else None
    if proc is None and celne and total:
        proc = round(100.0 * celne / total)
    return (total, celne, proc)




# ---------------------------------------------------------------------------
# przegladarka
# ---------------------------------------------------------------------------
def pierwszy_dzialajacy(zakres, klucz):
    """Zwraca locator dla pierwszego selektora, ktory cokolwiek znalazl."""
    for sel in SELEKTORY[klucz]:
        loc = zakres.locator(sel)
        try:
            if loc.count() > 0:
                return loc, sel
        except Exception:
            continue
    return None, None


def otworz_przegladarke(widok):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        stop("Brak Playwrighta. Uruchom:\n    pip install playwright\n    playwright install chromium")
    pw = sync_playwright().start()
    br = pw.chromium.launch(headless=not widok)
    ctx = br.new_context(
        locale="pl-PL",
        viewport={"width": 1440, "height": 2200},
        user_agent=("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0 Safari/537.36"),
    )
    return pw, br, ctx.new_page()


def zamknij_banery(page):
    for tekst in ("Zgadzam się", "Akceptuj", "Zgoda", "Accept", "Rozumiem"):
        try:
            b = page.get_by_role("button", name=re.compile(tekst, re.I))
            if b.count() > 0:
                b.first.click(timeout=2500)
                page.wait_for_timeout(400)
                return
        except Exception:
            continue


def rok_dla_daty(dzien, miesiac):
    """Flashscore nie podaje roku. Zakladamy biezacy; jesli wyszla data
    bardziej niz tydzien w przyszlosci, to znaczy ze chodzi o rok poprzedni."""
    dziś = datetime.now()
    for rok in (dziś.year, dziś.year - 1):
        try:
            d = datetime(rok, miesiac, dzien)
        except ValueError:
            continue
        if (d - dziś).days <= 7:
            return d.strftime("%Y-%m-%d")
    return ""


def czytaj_wiersz(w):
    """Jeden wiersz z listy wynikow -> slownik albo None."""
    # identyfikator meczu siedzi w atrybucie id elementu: g_1_WhZpaOLb
    mid = None
    try:
        el_id = w.get_attribute("id") or ""
        m = re.match(r"g_\d+_([A-Za-z0-9]{8})$", el_id.strip())
        if m:
            mid = m.group(1)
    except Exception:
        pass
    if mid is None:
        try:
            m = re.search(r'id="g_\d+_([A-Za-z0-9]{8})"', w.inner_html(timeout=3000))
            if m:
                mid = m.group(1)
        except Exception:
            return None
    if mid is None:
        return None

    try:
        tekst = w.inner_text(timeout=3000)
    except Exception:
        return None
    linie = [x.strip() for x in tekst.split("\n") if x.strip()]

    gosp = gosc = ""
    for klucz, cel in (("wiersz_gospodarz", "gosp"), ("wiersz_gosc", "gosc")):
        loc, _ = pierwszy_dzialajacy(w, klucz)
        if loc is not None:
            try:
                val = loc.first.inner_text(timeout=2000).strip()
                if cel == "gosp":
                    gosp = val
                else:
                    gosc = val
            except Exception:
                pass
    if not gosp or not gosc:
        kandydaci = [l for l in linie if not re.fullmatch(r"[\d.: ]+", l) and len(l) > 2]
        if len(kandydaci) >= 2:
            gosp, gosc = kandydaci[0], kandydaci[1]

    wynik = ""
    cyfry = [l for l in linie if re.fullmatch(r"\d+", l)]
    if len(cyfry) >= 2:
        wynik = f"{cyfry[0]}:{cyfry[1]}"

    data = ""
    d = re.search(r"(\d{1,2})\.(\d{1,2})\.", tekst)
    if d:
        data = rok_dla_daty(int(d.group(1)), int(d.group(2)))

    # Flashscore dopisuje kraj w nawiasie przy sparingach i pucharach
    # miedzynarodowych: "Widzew Lodz (Pol)". W Ekstraklasie tego nie ma.
    liga = "(" not in gosp and "(" not in gosc

    return {"mid": mid, "gosp": gosp, "gosc": gosc, "wynik": wynik,
            "data": data, "liga": liga, "tekst": " | ".join(linie[:8])}


def znajdz_mecze(page, diagnostyka=False):
    """Lista meczow ze strony wynikow, od najnowszego."""
    if "PODMIEN-MNIE" in URL_WYNIKI:
        stop("Nie ustawiony URL_WYNIKI. Otworz aktualizuj.py i wklej adres strony\n"
             "    'Wyniki' Widzewa z Flashscore w linii URL_WYNIKI (okolo 40. linia).")
    page.goto(URL_WYNIKI, wait_until="domcontentloaded", timeout=45000)
    zamknij_banery(page)
    page.wait_for_timeout(2500)

    loc, sel = pierwszy_dzialajacy(page, "wiersz_meczu")
    if loc is None:
        stop("Nie widze zadnego wiersza meczu na stronie wynikow.\n"
             "    Trzeba poprawic SELEKTORY['wiersz_meczu'].")
    if diagnostyka:
        print(f"\n  wiersz_meczu: dziala selektor {sel!r}, znaleziono {loc.count()}")

    mecze = []
    for i in range(min(loc.count(), 30)):
        m = czytaj_wiersz(loc.nth(i))
        if m:
            mecze.append(m)

    if diagnostyka:
        print(f"  odczytanych wierszy: {len(mecze)}")
        for x in mecze[:10]:
            znak = "LIGA" if x["liga"] else "poza"
            print(f"    {x['mid']}  {znak}  {x['data'] or '?':10}  "
                  f"{x['wynik'] or '-':5}  {x['gosp']} - {x['gosc']}")
    return mecze


def zbierz_surowe(loc):
    """Odczytuje tabele statystyk -> lista (etykieta, gospodarz, gosc)."""
    surowe = []
    if loc is None:
        return surowe
    for i in range(loc.count()):
        w = loc.nth(i)
        try:
            et_loc, _ = pierwszy_dzialajacy(w, "etykieta")
            wa_loc, _ = pierwszy_dzialajacy(w, "wartosc")
            if et_loc is None or wa_loc is None or wa_loc.count() < 2:
                continue
            etykieta = et_loc.first.inner_text(timeout=2000).strip()
            gosp = wa_loc.nth(0).inner_text(timeout=2000).strip()
            gosc = wa_loc.nth(wa_loc.count() - 1).inner_text(timeout=2000).strip()
        except Exception:
            continue
        surowe.append((etykieta, gosp, gosc))
    return surowe


# Bez tych dwoch metryk mamy tylko kafelek-skrot z podsumowania meczu,
# a nie pelna zakladke STATYSTYKI - w CSV zostalyby dziury w 5 kolumnach.
WYMAGANE = ("sot", "passes")


def czy_pelna(surowe):
    znalezione = {dopasuj_etykiete(e) for e, _, _ in surowe}
    return all(k in znalezione for k in WYMAGANE)


def rozwin_statystyki(page):
    """Flashscore dorysowuje dolne sekcje dopiero po doprzewinieciu."""
    poprzednio = -1
    for proba in range(8):
        loc, _ = pierwszy_dzialajacy(page, "wiersz_statystyki")
        ile = loc.count() if loc is not None else 0
        if ile == poprzednio and proba >= 2:
            break
        poprzednio = ile
        try:
            page.mouse.wheel(0, 1200)
        except Exception:
            try:
                page.evaluate("window.scrollBy(0, 1200)")
            except Exception:
                pass
        page.wait_for_timeout(700)
    try:
        page.evaluate("window.scrollTo(0, 0)")
    except Exception:
        pass
    page.wait_for_timeout(400)
    loc, _ = pierwszy_dzialajacy(page, "wiersz_statystyki")
    return loc


def czytaj_tu(page):
    """Przewin i odczytaj tabele w obecnym stanie strony."""
    return zbierz_surowe(rozwin_statystyki(page))


def wejdz_na(page, url):
    """Wymuszone przeladowanie. Bez about:blank przegladarka traktuje zmiane
    samego fragmentu po '#' jako nawigacje w tym samym dokumencie i NIE
    przeladowuje strony - trzy rozne adresy daja wtedy ten sam widok."""
    try:
        page.goto("about:blank", timeout=15000)
    except Exception:
        pass
    page.goto(url, wait_until="domcontentloaded", timeout=45000)
    zamknij_banery(page)
    page.wait_for_timeout(2600)


# JS: szuka elementow, ktorych cala tresc to dokladnie "statystyki" - bez
# zalozen o tym, czy to <a>, <button> czy <div>.
JS_ZAKLADKI = r"""() => {
  const norm = s => (s || '').replace(/\s+/g, ' ').trim().toLowerCase()
    .replace(/ą/g,'a').replace(/ę/g,'e').replace(/ó/g,'o').replace(/ł/g,'l')
    .replace(/ś/g,'s').replace(/[żź]/g,'z').replace(/ć/g,'c').replace(/ń/g,'n');
  const out = [];
  document.querySelectorAll('a,button,div,span,li,[role]').forEach(e => {
    if (norm(e.textContent) === 'statystyki' && e.children.length <= 2) {
      out.push({
        tag: e.tagName,
        cls: String(e.className || '').slice(0, 70),
        href: e.getAttribute('href') || '',
        rola: e.getAttribute('role') || '',
        testid: e.getAttribute('data-testid') || ''
      });
    }
  });
  return out.slice(0, 12);
}"""

JS_KLIK = r"""(n) => {
  const norm = s => (s || '').replace(/\s+/g, ' ').trim().toLowerCase()
    .replace(/ą/g,'a').replace(/ę/g,'e').replace(/ó/g,'o').replace(/ł/g,'l')
    .replace(/ś/g,'s').replace(/[żź]/g,'z').replace(/ć/g,'c').replace(/ń/g,'n');
  const el = [];
  document.querySelectorAll('a,button,div,span,li,[role]').forEach(e => {
    if (norm(e.textContent) === 'statystyki' && e.children.length <= 2) el.push(e);
  });
  if (!el[n]) return false;
  el[n].scrollIntoView({block: 'center'});
  el[n].click();
  return true;
}"""


def otworz_statystyki(page, mid, diagnostyka=False):
    """Zwraca (surowe, opis_drogi). Nie zwraca wskaznika do strony - stan
    strony zmienia sie przy kolejnych probach i wskaznik traci waznosc."""
    baza = None
    try:
        wiersz = page.locator(f"#g_1_{mid}")
        if wiersz.count() > 0:
            wiersz.first.click(timeout=8000)
            page.wait_for_timeout(3000)
            if "/mecz/" in page.url or "/match/" in page.url:
                baza = page.url.split("#")[0]
    except Exception:
        pass
    if baza is None:
        baza = f"https://www.flashscore.pl/mecz/{mid}/"
    if diagnostyka:
        print(f"\n  adres meczu: {baza}")

    najlepsze = ([], "brak")

    def sprawdz(surowe, opis):
        nonlocal najlepsze
        rozpoznane = sorted({dopasuj_etykiete(e) for e, _, _ in surowe} - {None})
        if diagnostyka:
            print(f"    {opis}: wierszy {len(surowe)}, metryki {rozpoznane}")
        if len(rozpoznane) > len({dopasuj_etykiete(e) for e, _, _ in najlepsze[0]} - {None}):
            najlepsze = (surowe, opis)
        return czy_pelna(surowe)

    # 1. adresy, kazdy z wymuszonym przeladowaniem
    for hasz in ("#/podsumowanie-meczu/statystyki-meczu/0",
                 "#/statystyki-meczu/0",
                 "#/match-summary/match-statistics/0"):
        wejdz_na(page, baza + hasz)
        surowe = czytaj_tu(page)
        if sprawdz(surowe, f"adres {hasz}"):
            return surowe, f"adres {hasz}"

    # 2. zakladka po tresci - bez zalozen co do rodzaju elementu
    try:
        kandydaci = page.evaluate(JS_ZAKLADKI)
    except Exception:
        kandydaci = []
    if diagnostyka:
        print(f"    elementow o tresci 'statystyki': {len(kandydaci)}")
        for k in kandydaci:
            print(f"      <{k['tag'].lower()}> class={k['cls']!r} href={k['href']!r} "
                  f"role={k['rola']!r} testid={k['testid']!r}")

    # 2a. te z href - po prostu wchodzimy pod ten adres
    for k in kandydaci:
        h = k["href"]
        if not h or h in ("#", "/"):
            continue
        url = h if h.startswith("http") else (
            baza + h if h.startswith("#") else "https://www.flashscore.pl" + h)
        wejdz_na(page, url)
        surowe = czytaj_tu(page)
        if sprawdz(surowe, f"href {h}"):
            return surowe, f"href {h}"

    # 2b. te bez href - klikamy w przegladarce
    for n in range(len(kandydaci)):
        try:
            if not page.evaluate(JS_KLIK, n):
                continue
        except Exception:
            continue
        page.wait_for_timeout(2600)
        surowe = czytaj_tu(page)
        if sprawdz(surowe, f"klik #{n} <{kandydaci[n]['tag'].lower()}>"):
            return surowe, f"klik #{n}"

    if diagnostyka:
        print(f"    zadna droga nie dala pelnej tabeli; najlepsza: {najlepsze[1]}")
    return najlepsze


def wczytaj_statystyki(page, mid, diagnostyka=False):
    """Zwraca (dane, meta)."""
    surowe, droga = otworz_statystyki(page, mid, diagnostyka)

    ZRZUTY.mkdir(exist_ok=True)
    zrzut = ZRZUTY / f"{mid}.png"
    try:
        page.screenshot(path=str(zrzut), full_page=True)
    except Exception:
        zrzut = None

    if diagnostyka:
        print(f"\n  --- co widze (droga: {droga}) ---")
        if not surowe:
            print("    NIC. Zrzut ekranu pokaze, co bylo na stronie.")
        for e, g, a in surowe:
            pref = dopasuj_etykiete(e)
            znak = "-> " + pref if pref else "-"
            e1 = re.sub(r"\s+", " ", e)[:38]
            g1, a1 = re.sub(r"\s+", " ", g)[:16], re.sub(r"\s+", " ", a)[:16]
            print(f"    {e1:38} | {g1:>16} | {a1:>16}   {znak}")
        brak = [k for k in ("xg", "shots", "sot", "bc", "passes", "poss")
                if not any(dopasuj_etykiete(e) == k for e, _, _ in surowe)]
        if brak:
            print(f"\n    BRAKUJE JESZCZE: {', '.join(brak)}")
        print("  --- koniec ---\n")

    if not czy_pelna(surowe):
        print("    UWAGA: tabela niepelna - brak strzalow na bramke lub podan.")

    dane = {}
    konflikty = []

    def wstaw(klucz, wartosc):
        """Ta sama metryka moze wystapic w tabeli dwa razy (skrot u gory i
        pelna sekcja nizej). Zgodne powtorzenie jest w porzadku, rozbiezne
        znaczy, ze dopasowanie etykiet jest zle - i lepiej nie zapisywac nic."""
        if wartosc is None:
            return
        if klucz in dane and dane[klucz] != wartosc:
            konflikty.append(f"{klucz}: {dane[klucz]} vs {wartosc}")
            return
        dane[klucz] = wartosc

    for etykieta, g, a in surowe:
        pref = dopasuj_etykiete(etykieta)
        if pref is None:
            continue
        if pref == "passes":
            for strona, val in (("home", g), ("away", a)):
                total, celne, proc = rozbij_podania(val)
                wstaw(f"passes_{strona}", total)
                wstaw(f"passes_acc_{strona}", celne)
                wstaw(f"pass_pct_{strona}", int(proc) if proc is not None else None)
        else:
            wstaw(f"{pref}_home", liczba(g))
            wstaw(f"{pref}_away", liczba(a))

    if konflikty:
        print("    UWAGA: sprzeczne odczyty tej samej metryki:")
        for k in konflikty:
            print(f"      - {k}")
        stop("Nie zapisuje niczego - dopasowanie etykiet wymaga poprawki.")

    meta = {"zrzut": str(zrzut) if zrzut else None, "droga": droga}
    # naglowek meczu na Flashscore wyglada tak: "PKO BP EKSTRAKLASA - KOLEJKA 3"
    try:
        tekst = page.locator("body").inner_text(timeout=4000)
        r = re.search(r"(?:kolejka|runda)\s*(\d+)", tekst, re.I)
        if r:
            meta["round"] = int(r.group(1))
        meta["ekstraklasa"] = "ekstraklasa" in bez_ogonkow(tekst[:1500])
    except Exception:
        pass
    return dane, meta


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------
def plik_sezonu():
    pliki = sorted(glob.glob(str(HERE / "[0-9][0-9][0-9][0-9]-[0-9][0-9].csv")))
    if not pliki:
        stop("Nie znalazlem pliku CSV sezonu w tym folderze.")
    return pathlib.Path(pliki[-1])


def wczytaj_csv(sciezka):
    with open(sciezka, newline="", encoding="utf-8") as f:
        czyt = csv.DictReader(f)
        return list(czyt), czyt.fieldnames


def zapisz_csv(sciezka, wiersze, naglowki):
    """lineterminator \\r\\n - tak jak w istniejacym pliku, zeby nie robic
    diffu na calej tresci."""
    buf = io.StringIO()
    zap = csv.DictWriter(buf, fieldnames=naglowki, lineterminator="\r\n",
                         extrasaction="ignore")
    zap.writeheader()
    for w in wiersze:
        zap.writerow(w)
    with open(sciezka, "w", newline="", encoding="utf-8") as f:
        f.write(buf.getvalue())


def scal_wiersz(wiersze, nowy):
    """Wstawia lub uzupelnia. Zwraca (wiersze, co_sie_stalo)."""
    for i, w in enumerate(wiersze):
        if w.get("fixture_id") and w["fixture_id"] == nowy["fixture_id"]:
            if (w.get("score_ft") or "").strip():
                return wiersze, "juz_jest"
            scalony = dict(w)
            for k, v in nowy.items():
                if v not in (None, ""):
                    scalony[k] = v
            wiersze[i] = scalony
            return wiersze, "uzupelniony"
    wiersze.insert(0, nowy)
    return wiersze, "dodany"


def sprawdz_przed_zapisem(r):
    """Te same kontrole co w zbuduj.py, ale PRZED zapisem - lepiej nie
    dotykac pliku, niz cofac go potem."""
    bledy = []
    for strona in ("home", "away"):
        s, sot = liczba(r.get(f"shots_{strona}")), liczba(r.get(f"sot_{strona}"))
        if s is None or sot is None:
            bledy.append(f"brak strzalow ({strona}) - parser nic nie odczytal")
        elif sot > s:
            bledy.append(f"strzaly na bramke > strzaly lacznie ({strona})")
        x = liczba(r.get(f"xg_{strona}"))
        if x is None:
            bledy.append(f"brak xG ({strona})")
        elif not (0 <= x <= 8):
            bledy.append(f"podejrzane xG ({strona}): {x}")
        tot, cel = liczba(r.get(f"passes_{strona}")), liczba(r.get(f"passes_acc_{strona}"))
        pct = liczba(r.get(f"pass_pct_{strona}"))
        if tot and cel and pct is not None:
            if abs(round(100.0 * cel / tot) - pct) > 1:
                bledy.append(f"% podan nie zgadza sie z ulamkiem ({strona}): "
                             f"{cel}/{tot} vs {pct}%")
    poss = (liczba(r.get("poss_home")) or 0) + (liczba(r.get("poss_away")) or 0)
    if not (95 <= poss <= 105):
        bledy.append(f"posiadanie nie sumuje sie do 100 ({poss})")
    return bledy


# ---------------------------------------------------------------------------
# git i przeliczanie
# ---------------------------------------------------------------------------
def git(*args, cicho=False):
    p = subprocess.run(["git", *args], cwd=HERE, capture_output=True, text=True)
    if p.returncode != 0 and not cicho:
        stop(f"git {' '.join(args)} nie wyszlo:\n    {p.stderr.strip()}")
    return p.stdout.strip()


def uruchom(skrypt):
    p = subprocess.run([sys.executable, skrypt], cwd=HERE, capture_output=True, text=True)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def ostrzezenia_z(wyjscie):
    szukane = ("ostrzez", "OSTRZEZ", "UWAGA", "BLAD", "nie sumuje", "podejrzane",
               "poza zakresem", "przerwa w kolejkach", "sprzeczn")
    return [l.strip() for l in wyjscie.splitlines()
            if any(s.lower() in l.lower() for s in szukane)]


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--sucho", action="store_true", help="nic nie zapisuj")
    ap.add_argument("--widok", action="store_true", help="pokaz okno przegladarki")
    ap.add_argument("--diagnostyka", action="store_true", help="wypisz, co widze na stronie")
    ap.add_argument("--mid", help="konkretny mecz zamiast najnowszego")
    ap.add_argument("--pozycja", type=int, help="pozycja w tabeli po tej kolejce")
    ap.add_argument("--bez-pusha", action="store_true", help="commit, ale nie pushuj")
    a = ap.parse_args()

    sciezka = plik_sezonu()
    wiersze, naglowki = wczytaj_csv(sciezka)
    if naglowki != KOLUMNY:
        print("UWAGA: naglowki w CSV roznia sie od tych, ktore znam. Uzywam tych z pliku.")
    sezon = wiersze[0].get("season") if wiersze else None
    znane = {w.get("fixture_id") for w in wiersze if (w.get("score_ft") or "").strip()}

    krok(f"czytam {sciezka.name}")
    krok.ok(f"{len(wiersze)} wierszy, sezon {sezon}")

    if not a.sucho and not a.diagnostyka:
        krok("sprawdzam, czy repo jest czyste")
        if git("status", "--porcelain"):
            stop("W repo sa niezapisane zmiany. Zrob commit albo `git stash`,\n"
                 "    zeby cofanie w razie bledu bylo bezpieczne.")
        krok.ok()

    krok("otwieram przegladarke")
    pw, br, page = otworz_przegladarke(a.widok or a.diagnostyka)
    krok.ok("chromium" + (", okno widoczne" if (a.widok or a.diagnostyka) else ""))

    try:
        mid = a.mid
        wiersz = None
        if not mid:
            krok("szukam najnowszego meczu ligowego")
            mecze = znajdz_mecze(page, a.diagnostyka)
            # tylko Ekstraklasa: sparingi i puchary miedzynarodowe maja na
            # Flashscore kraj w nawiasie przy nazwie druzyny
            zagrane = [m for m in mecze if m["wynik"] and m["liga"]]
            odrzucone = [m for m in mecze if m["wynik"] and not m["liga"]]
            if not zagrane:
                stop("Nie znalazlem zadnego rozegranego meczu ligowego.")
            wiersz = zagrane[0]
            mid = wiersz["mid"]
            krok.ok(f"{mid}  {wiersz['gosp']} - {wiersz['gosc']}  {wiersz['wynik']}"
                    + (f", pominietych poza liga: {len(odrzucone)}" if odrzucone else ""))
        else:
            znajdz_mecze(page, a.diagnostyka)

        if mid in znane and not a.diagnostyka and not a.sucho:
            print(f"\n    Mecz {mid} jest juz w CSV z wynikiem. Nic nowego.\n")
            return
        if mid in znane and a.sucho:
            print(f"    (ten mecz jest juz w CSV - --sucho, wiec czytam go na probe)")

        krok("zbieram statystyki")
        dane, meta = wczytaj_statystyki(page, mid, a.diagnostyka)
        krok.ok(f"{len(dane)} pol" + (f", zrzut: {meta['zrzut']}" if meta.get("zrzut") else ""))
    finally:
        try:
            br.close(); pw.stop()
        except Exception:
            pass

    if a.diagnostyka:
        print("Diagnostyka skonczona. Wklej powyzsze do rozmowy - domapuje etykiety.")
        return

    if wiersz:
        meta.setdefault("home_team", wiersz["gosp"])
        meta.setdefault("away_team", wiersz["gosc"])
        if not meta.get("date"):
            meta["date"] = wiersz["data"]
        if not meta.get("score_ft"):
            meta["score_ft"] = wiersz["wynik"]

    home = meta.get("home_team") or ""
    away = meta.get("away_team") or ""
    if WIDZEW not in (home, away):
        print(f"    UWAGA: nie rozpoznaje Widzewa w nazwach ({home!r} vs {away!r}).")

    # Kolejka - w tej wlasnie kolejnosci zrodel:
    # 1) wiersz zapowiedzi, jesli juz go masz (wpisales go swiadomie),
    # 2) naglowek na Flashscore, 3) ostatnia znana + 1.
    istniejacy = next((w for w in wiersze if w.get("fixture_id") == mid), None)
    kolejki = [int(w["round"]) for w in wiersze if (w.get("round") or "").strip().isdigit()]
    if istniejacy and (istniejacy.get("round") or "").strip().isdigit():
        runda = int(istniejacy["round"])
        zrodlo_rundy = "wiersz zapowiedzi"
    elif meta.get("round"):
        runda = meta["round"]
        zrodlo_rundy = "naglowek Flashscore"
    else:
        runda = max(kolejki) + 1 if kolejki else 1
        zrodlo_rundy = "ostatnia znana + 1"
    print(f"    kolejka {runda} (zrodlo: {zrodlo_rundy})")

    nowy = {k: "" for k in naglowki}
    nowy.update({
        "season": sezon,
        "round": runda,
        "date": meta.get("date", ""),
        "competition": ROZGRYWKI,
        "venue": "H" if home == WIDZEW else "A",
        "home_team": home,
        "away_team": away,
        "score_ht": "",
        "score_ft": meta.get("score_ft", ""),
        "position": a.pozycja if a.pozycja else (
            (istniejacy or {}).get("position") or ""),
        "fixture_id": mid,
    })
    for k, v in dane.items():
        if k in nowy:
            nowy[k] = "" if v is None else (int(v) if float(v).is_integer() and k[:2] != "xg" else v)

    print("\n  --- wiersz do zapisu ---")
    for k in naglowki:
        print(f"    {k:18} {nowy[k]}")
    print("  ------------------------\n")

    bledy = sprawdz_przed_zapisem(nowy)
    if bledy:
        stop("Wiersz nie przeszedl kontroli, nie zapisuje:\n    - " + "\n    - ".join(bledy))
    krok("kontrole wiersza")
    krok.ok("wszystkie przeszly")

    if not nowy["position"]:
        print("    Uwaga: kolumna 'position' pusta. Uzupelnij recznie albo podaj --pozycja N.")

    if a.sucho:
        print("  --sucho: koniec, plik nietkniety.\n")
        return

    wiersze, co = scal_wiersz(wiersze, nowy)
    if co == "juz_jest":
        print("    Mecz jest juz w CSV z wynikiem. Nic nie robie.\n")
        return
    krok(f"zapisuje CSV ({co})")
    zapisz_csv(sciezka, wiersze, naglowki)
    krok.ok()

    krok("przeliczam zbuduj.py")
    kod, wy = uruchom("zbuduj.py")
    ostrz = ostrzezenia_z(wy)
    if kod != 0 or ostrz:
        git("checkout", "--", sciezka.name)
        stop("zbuduj.py zglosil problem - cofnalem CSV, nic nie poszlo do repo:\n    "
             + "\n    ".join(ostrz or [wy.strip()[:500]]))
    krok.ok()

    krok("generuje strona.py")
    kod, wy = uruchom("strona.py")
    if kod != 0:
        git("checkout", "--", sciezka.name)
        stop("strona.py sie wywalil - cofnalem CSV:\n    " + wy.strip()[:500])
    krok.ok()

    krok("commit")
    git("add", sciezka.name, "data.json", "index.html")
    opis = f"Kolejka {runda}: {home} - {away} {nowy['score_ft']} (auto)"
    git("commit", "-m", opis)
    krok.ok(opis)

    if a.bez_pusha:
        print("\n    --bez-pusha: commit zostal lokalnie.\n")
        return
    krok("push")
    git("push")
    krok.ok("GitHub Pages przebuduje sie w ciagu minuty")
    print("\n  Gotowe.\n")


if __name__ == "__main__":
    main()
