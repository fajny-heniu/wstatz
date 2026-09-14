#!/usr/bin/env python3
"""Uzupelnianie statystyk w sezonie archiwalnym (np. 2024/25).

Nie powiela parsera - importuje gotowy z aktualizuj.py. Trzy tryby, do
uruchamiania po kolei:

    python3 backfill.py --test                      # sprawdz parser na znanych danych
    python3 backfill.py --lista --url "ADRES"       # zbierz kody meczow
    python3 backfill.py --pobierz                   # pobierz i zapisz statystyki

Zasady:
  * Nigdy nie nadpisuje wypelnionej komorki. Uzupelnia tylko puste.
  * Nie rusza wyniku, daty, druzyn ani kolumny position.
  * Kod meczu z Flashscore ladnie do nowej kolumny flashscore_id; stare
    fixture_id (API-Football) zostaje jako slad pochodzenia.
  * Kazdy zapis poprzedzony kopia .bak.
"""
import argparse
import csv
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import aktualizuj as A  # noqa: E402  (parser, selektory, Playwright)

MAPA = {  # prefiks ze statystyk -> (kolumna_gospodarz, kolumna_gosc)
    "xg": ("xg_home", "xg_away"),
    "shots": ("shots_home", "shots_away"),
    "sot": ("sot_home", "sot_away"),
    "bc": ("bc_home", "bc_away"),
    "poss": ("poss_home", "poss_away"),
}


def wczytaj(sciezka):
    with open(sciezka, newline="", encoding="utf-8") as f:
        naglowki = next(csv.reader(f))
        f.seek(0)
        return naglowki, list(csv.DictReader(f))


def zapisz(sciezka, naglowki, wiersze):
    kopia = sciezka.with_suffix(sciezka.suffix + ".bak")
    if sciezka.exists():
        kopia.write_bytes(sciezka.read_bytes())
    with open(sciezka, "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=naglowki, lineterminator="\r\n")
        wr.writeheader()
        wr.writerows(wiersze)
    print(f"  zapisano {sciezka.name} (kopia: {kopia.name})")


def surowe_na_wartosci(surowe):
    """[(etykieta, gosp, gosc)] -> {kolumna: wartosc}. Braki pomijane."""
    out = {}
    for etykieta, gosp, gosc in surowe:
        klucz = A.dopasuj_etykiete(etykieta)
        if klucz == "passes":
            for tekst, kol_pct, kol_ok, kol_all in (
                (gosp, "pass_pct_home", "passes_acc_home", "passes_home"),
                (gosc, "pass_pct_away", "passes_acc_away", "passes_away"),
            ):
                # UWAGA na kolejnosc: rozbij_podania zwraca (total, celne, procent)
                wszystkie, udane, pct = A.rozbij_podania(tekst)
                if pct is not None:
                    out[kol_pct] = pct
                if udane is not None:
                    out[kol_ok] = udane
                if wszystkie is not None:
                    out[kol_all] = wszystkie
        elif klucz in MAPA:
            kol_h, kol_a = MAPA[klucz]
            for kol, tekst in ((kol_h, gosp), (kol_a, gosc)):
                v = A.liczba(tekst)
                if v is not None:
                    out[kol] = v
    return out


def sformatuj(kol, v):
    """Zapis dokladnie taki, jaki produkuje aktualizuj.py - zeby w jednym
    pliku nie siedzialy dwie konwencje tej samej metryki (0.8 vs 0.80)."""
    if v is None:
        return ""
    f = float(v)
    if f.is_integer() and not kol.startswith("xg"):
        return str(int(f))
    return str(f)


# ---------------------------------------------------------------------------
# tryb --test: parser na meczach, ktorych wynik juz znamy
# ---------------------------------------------------------------------------
def tryb_test(args):
    naglowki, wiersze = wczytaj(HERE / args.wzorzec)
    maja = [w for w in wiersze if (w.get("xg_home") or "").strip() and w.get("fixture_id")]
    probka = maja[: args.ile]
    if not probka:
        A.stop(f"{args.wzorzec}: brak wierszy z wypelnionym xG i fixture_id")

    print(f"\nTEST: {len(probka)} meczow z {args.wzorzec}, ktorych wartosci juz znamy.\n")
    pw, br, page = A.otworz_przegladarke(args.widok)
    zgodne = rozne = 0
    try:
        for w in probka:
            mid = w["fixture_id"].strip()
            surowe, _ = A.otworz_statystyki(page, mid, args.diagnostyka)
            nowe = surowe_na_wartosci(surowe)
            print(f"  k{w['round']:>2} {w['home_team']} - {w['away_team']}  (mid={mid})")
            for kol in ("xg_home", "xg_away", "shots_home", "sot_home",
                        "bc_home", "pass_pct_home", "poss_home"):
                stara = (w.get(kol) or "").strip()
                nowa = sformatuj(kol, nowe.get(kol))
                if not stara and not nowa:
                    continue
                # Porownanie liczbowe, nie tekstowe: "0.8" i "0.80" to ta sama
                # wartosc i nie ma powodu zglaszac tego jako rozbieznosci.
                try:
                    ok = abs(float(stara) - float(nowa)) < 0.005
                except ValueError:
                    ok = stara == nowa
                zgodne += ok
                rozne += not ok
                print(f"      {kol:<14} w CSV: {stara or '–':<7} pobrane: {nowa or '–':<7}"
                      f" {'zgodne' if ok else '<<< ROZNE'}")
    finally:
        br.close()
        pw.stop()
    print(f"\n  zgodnych: {zgodne}, roznych: {rozne}")
    print("  Jesli roznych jest 0, parser dziala i mozna isc dalej.\n"
          if not rozne else
          "  STOP. Nie pobieraj archiwum, dopoki to sie nie zgadza.\n")


# ---------------------------------------------------------------------------
# tryb --lista: kody meczow ze strony wynikow sezonu
# ---------------------------------------------------------------------------
JS_WIECEJ = r"""() => {
  const pasuje = (t) => /poka(z|ż)\s+wi(e|ę)cej|show more/i.test(t || '');
  const el = [...document.querySelectorAll('a,button,div,span')]
    .filter(e => e.children.length <= 2 && pasuje(e.textContent))
    .pop();
  if (!el) return null;
  el.scrollIntoView({block: 'center'});
  el.click();
  return {tag: el.tagName, cls: (el.className || '').toString().slice(0, 60),
          tekst: (el.textContent || '').trim().slice(0, 40)};
}"""


def rozwin_liste(page, klikniecia=40, sel=None):
    """Klika 'Pokaz wiecej meczow', az lista przestanie rosnac.

    Przycisk szukany po TRESCI, nie po klasie - klasy Flashscore maja losowe
    sufiksy i zmieniaja sie przy kazdym wdrozeniu. Warunkiem konca jest brak
    przyrostu wierszy, nie wykonanie N obrotow.
    """
    poprzednio = -1
    for proba in range(klikniecia):
        page.mouse.wheel(0, 30000)
        page.wait_for_timeout(500)
        ile = page.locator(sel).count() if sel else 0
        if proba == 0 or ile != poprzednio:
            print(f"    wierszy: {ile}")
        if ile == poprzednio:
            break
        poprzednio = ile
        try:
            klikniety = page.evaluate(JS_WIECEJ)
        except Exception:
            klikniety = None
        if klikniety is None:
            print("    nie znaleziono przycisku 'pokaz wiecej' - koniec listy "
                  "albo zmieniona strona")
            break
        if proba == 0:
            print(f"    przycisk: <{klikniety['tag'].lower()}> {klikniety['tekst']!r}")
        page.wait_for_timeout(1800)


def tryb_lista(args):
    if not args.url or not args.url.startswith("http"):
        A.stop("Podaj --url do strony WYNIKOW sezonu (adres z paska przegladarki).")
    naglowki, wiersze = wczytaj(HERE / args.csv)
    wiersze.sort(key=lambda w: int(w["round"]), reverse=True)

    pw, br, page = A.otworz_przegladarke(args.widok)
    try:
        page.goto(args.url, wait_until="domcontentloaded", timeout=45000)
        A.zamknij_banery(page)
        page.wait_for_timeout(2500)
        sel = A.SELEKTORY["wiersz_meczu"][0]
        if page.locator(sel).count() == 0:
            sel = A.SELEKTORY["wiersz_meczu"][1]
        rozwin_liste(page, args.klikniecia, sel)
        surowe = page.evaluate(JS_WIERSZE, sel)
    finally:
        br.close()
        pw.stop()

    # Lista jest calej ligi (306 meczow), wiec filtrujemy po nazwie druzyny.
    # Kod meczu siedzi w id wiersza: "g_1_XXXXXXXX".
    nasze = []
    for r in surowe:
        if not any(args.druzyna.lower() in t.lower() for t in r["tekst"]):
            continue
        m = re.match(r"g_1_([A-Za-z0-9]{8})$", r["id"])
        if not m:
            continue
        # Flashscore pisze date roznie: "24.05.", "24.05. 20:15", czasem z rokiem.
        # Szukamy wzorca wewnatrz linii, nie calej linii.
        mdata = re.search(r"(\d{2})\.(\d{2})\.", " | ".join(r["tekst"]))
        data = f"{mdata.group(1)}.{mdata.group(2)}" if mdata else None
        gole = [t for t in r["tekst"] if re.fullmatch(r"\d+", t)]
        nasze.append({"mid": m.group(1), "data": data, "gole": gole[-2:]})

    print(f"\n  wierszy na stronie: {len(surowe)}, meczow z '{args.druzyna}': {len(nasze)}, "
          f"wierszy w CSV: {len(wiersze)}")
    if len(nasze) < len(wiersze):
        print("  UWAGA: mniej meczow niz wierszy w CSV - lista pewnie nie rozwinela sie\n"
              "  do konca. Sprobuj --klikniecia 60.")

    # Parowanie po DACIE, nie po kolejnosci na stronie. Strona sortuje mecze
    # po dacie, a CSV po numerze kolejki - przy przelozonym meczu (k31 zagrana
    # po k32) te dwa porzadki sie rozjezdzaja i cicha zamiana kodow wpisalaby
    # statystyki do zlych wierszy. Wynik meczu zostaje jako kontrola.
    wg_daty = {}
    for r in nasze:
        wg_daty.setdefault(r["data"], []).append(r)

    pary, zgodne, watpliwe = [], 0, []
    print("\n  Parowanie po dacie (wynik jako kontrola):\n")
    for w in wiersze:
        _, mies, dzien = w["date"].split("-")
        kandydaci = wg_daty.get(f"{dzien}.{mies}", [])
        z_csv = [x.strip() for x in (w["score_ft"] or "").split(":")]
        trafiony = next((r for r in kandydaci if r["gole"] == z_csv), None)
        if trafiony is None and len(kandydaci) == 1:
            trafiony = kandydaci[0]     # data pasuje, wynik nie - zglosimy nizej
        ok = trafiony is not None and trafiony["gole"] == z_csv
        zgodne += ok
        if not ok:
            watpliwe.append(w["round"])
        if trafiony is not None:
            kandydaci.remove(trafiony)
            pary.append({"round": w["round"], "date": w["date"], "mid": trafiony["mid"],
                         "home": w["home_team"], "away": w["away_team"], "score": w["score_ft"]})
        print(f"    k{w['round']:>2}  {w['date']}  {w['home_team'][:20]:<20} - "
              f"{w['away_team'][:20]:<20} CSV {w['score_ft']:<5} "
              f"strona {(':'.join(trafiony['gole']) if trafiony else '-'):<5} "
              f"{trafiony['mid'] if trafiony else '':<9} {'' if ok else '<<< SPRAWDZ'}")

    print(f"\n  sparowanych: {len(pary)}/{len(wiersze)}, wynik zgodny w {zgodne}")
    if watpliwe:
        print(f"  do sprawdzenia recznie: kolejki {', '.join(watpliwe)}")
        print("  NIE uruchamiaj --pobierz, dopoki to sie nie wyjasni.")
    plik = HERE / args.pary
    plik.write_text(json.dumps(pary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  zapisano {plik.name}\n")


# ---------------------------------------------------------------------------
# tryb --pobierz: statystyki do CSV
# ---------------------------------------------------------------------------
def tryb_pobierz(args):
    plik_par = HERE / args.pary
    if not plik_par.exists():
        A.stop(f"Brak {args.pary}. Najpierw uruchom --lista.")
    pary = json.loads(plik_par.read_text(encoding="utf-8"))
    sciezka = HERE / args.csv
    naglowki, wiersze = wczytaj(sciezka)
    if "flashscore_id" not in naglowki:
        naglowki = naglowki + ["flashscore_id"]
        for w in wiersze:
            w.setdefault("flashscore_id", "")

    wg_kolejki = {int(w["round"]): w for w in wiersze}
    pw, br, page = A.otworz_przegladarke(args.widok)
    zmienione = puste = 0
    try:
        for p in pary:
            w = wg_kolejki.get(int(p["round"]))
            if w is None:
                print(f"  k{p['round']}: brak wiersza w CSV - pomijam")
                continue
            surowe, droga = A.otworz_statystyki(page, p["mid"], args.diagnostyka)
            nowe = surowe_na_wartosci(surowe)
            if not nowe:
                puste += 1
                print(f"  k{p['round']:>2} {p['mid']}: nic nie odczytano ({droga})")
                continue
            dopisane = []
            for kol, v in nowe.items():
                if kol not in naglowki:
                    continue
                if (w.get(kol) or "").strip():   # nigdy nie nadpisujemy
                    continue
                w[kol] = sformatuj(kol, v)
                dopisane.append(kol)
            if not (w.get("flashscore_id") or "").strip():
                w["flashscore_id"] = p["mid"]
            zmienione += bool(dopisane)
            brak = [k for k in ("xg_home", "bc_home") if not (w.get(k) or "").strip()]
            print(f"  k{p['round']:>2} {p['home'][:18]:<18} {len(dopisane):>2} kolumn"
                  + (f"   BRAK: {', '.join(brak)}" if brak else ""))
    finally:
        br.close()
        pw.stop()

    print(f"\n  uzupelnionych meczow: {zmienione}, bez odczytu: {puste}")
    if args.sucho:
        print("  --sucho: nic nie zapisano.\n")
        return
    wiersze.sort(key=lambda w: int(w["round"]), reverse=True)
    zapisz(sciezka, naglowki, wiersze)
    print("  Teraz: python3 zbuduj.py && python3 strona.py\n")


def main():
    ap = argparse.ArgumentParser(description="Uzupelnianie statystyk sezonu archiwalnego")
    ap.add_argument("--test", action="store_true", help="sprawdz parser na znanych meczach")
    ap.add_argument("--lista", action="store_true", help="zbierz kody meczow ze strony sezonu")
    ap.add_argument("--pobierz", action="store_true", help="pobierz statystyki i zapisz")
    ap.add_argument("--csv", default="archiwum-2024-25.csv")
    ap.add_argument("--wzorzec", default="2025-26.csv", help="plik z danymi do testu")
    ap.add_argument("--pary", default="backfill-pary.json")
    ap.add_argument("--url", default="", help="adres strony wynikow sezonu")
    ap.add_argument("--ile", type=int, default=5, help="ile meczow w tescie")
    ap.add_argument("--druzyna", default="Widzew", help="filtr nazwy na liscie ligowej")
    ap.add_argument("--klikniecia", type=int, default=20, help="ile razy klikac 'pokaz wiecej'")
    ap.add_argument("--widok", action="store_true", help="pokaz przegladarke")
    ap.add_argument("--sucho", action="store_true", help="nie zapisuj CSV")
    ap.add_argument("--diagnostyka", action="store_true")
    args = ap.parse_args()

    if args.test:
        tryb_test(args)
    elif args.lista:
        tryb_lista(args)
    elif args.pobierz:
        tryb_pobierz(args)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
