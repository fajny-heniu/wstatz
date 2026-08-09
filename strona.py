#!/usr/bin/env python3
"""
Buduje index.html z data.json.

Uzycie:
    python3 zbuduj.py && python3 strona.py

Dane trafiaja do HTML jako wbudowany JSON, wiec plik dziala samodzielnie -
mozna go otworzyc dwuklikiem albo wrzucic na hosting bez zadnego serwera.
"""

import datetime
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
DATA = HERE / "data.json"
OUT = HERE / "index.html"

SZABLON = """<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>WSTATZ — widzewskie statystyki</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg%20xmlns%3D%27http%3A//www.w3.org/2000/svg%27%20viewBox%3D%270%200%2032%2032%27%3E%3Crect%20width%3D%2732%27%20height%3D%2732%27%20fill%3D%27%23e01b24%27/%3E%3Ctext%20x%3D%2716%27%20y%3D%2723%27%20font-family%3D%27Arial%2Csans-serif%27%20font-weight%3D%27900%27%20font-size%3D%2719%27%20fill%3D%27white%27%20text-anchor%3D%27middle%27%3EW%3C/text%3E%3C/svg%3E">
<style>
  :root {
    --ground: #dfe3e6;
    --panel: #fbfaf8;
    --ink: #1b1a19;
    --oxblood: #5e1018;
    --signal: #e01b24;
    --muted: #7a7f84;
    --line: #c7ced3;
    --win: #1c6b3a;
    --draw: #5a6066;
    --loss: #9a2b2b;
    --display: "Oswald", "Arial Narrow", "Haettenschweiler", system-ui, sans-serif;
    --data: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
    --label: system-ui, -apple-system, "Segoe UI", sans-serif;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; padding: 28px 20px 60px;
    background: var(--ground);
    color: var(--ink);
    font-family: var(--label);
    /* watek osnowy: pionowe nitki w tle, gesciej niz siatka tabeli */
    background-image: repeating-linear-gradient(90deg,
      rgba(94,16,24,.045) 0 1px, transparent 1px 9px);
  }
  header { max-width: 1240px; margin: 0 auto 30px; }
  h1 {
    font-family: var(--display); font-weight: 600;
    font-size: clamp(28px, 5vw, 46px);
    letter-spacing: -.01em; text-transform: uppercase;
    margin: 0; line-height: .95; color: var(--oxblood);
  }
  h1 span {
    font-weight: 400; color: var(--signal); letter-spacing: .01em;
  }
  .sub {
    font-family: var(--label); font-weight: 500; color: var(--muted);
    font-size: clamp(12px, 1.6vw, 15px); letter-spacing: .1em;
    margin: 10px 0 0;
  }

  footer {
    max-width: 1240px; margin: 34px auto 0;
    border-top: 1px solid var(--line); padding-top: 12px;
    font-size: 11.5px; color: var(--muted); line-height: 1.7;
  }
  footer b { font-weight: 600; color: #5a6066; }

  /* pasek porownania srednich */
  .compare {
    max-width: 1240px; margin: 0 auto 26px;
    display: grid; grid-template-columns: repeat(auto-fit, minmax(196px, 1fr));
    gap: 1px; background: var(--line);
    border: 1px solid var(--line);
  }
  .metric { background: var(--panel); padding: 13px 16px 15px; }
  .metric b {
    display: block; font-size: 13px; letter-spacing: .1em;
    text-transform: uppercase; color: var(--muted); font-weight: 600;
    margin-bottom: 9px;
  }
  /* jeden wiersz = jeden sezon, wartosci jedna pod druga */
  .metric .row { display: flex; align-items: baseline; gap: 10px; }
  .metric .sez {
    flex: none; min-width: 68px; white-space: nowrap;
    font-family: var(--label); font-size: 10px; font-weight: 600;
    letter-spacing: .06em; color: var(--muted);
  }
  .metric .row.now .val {
    font-family: var(--data); font-size: 25px; font-weight: 600;
    color: var(--signal); line-height: 1.15;
  }
  .metric .row.was { margin-top: 5px; }
  .metric .row.was .val {
    font-family: var(--data); font-size: 14px; color: #6f7479;
  }
  .metric .delta { font-family: var(--data); font-size: 12px; }
  .up { color: #1c6b3a; } .down { color: #9a2b2b; } .flat { color: var(--muted); }
  /* .metric .row .val ma wyzszy priorytet (3 klasy w lancuchu) niz samo .up/.down -
     bez tych regul znak nadwyzki goli nigdy by sie nie pokolorowal */
  .metric .row.now .val.up { color: var(--win); }
  .metric .row.now .val.down { color: var(--loss); }
  .metric .row.now .val.flat { color: var(--muted); }
  .metric .row.was .val.up { color: var(--win); }
  .metric .row.was .val.down { color: var(--loss); }

  .controls { max-width: 1240px; margin: 0 auto 14px; display: flex;
    flex-wrap: wrap; gap: 10px; align-items: center; }
  .controls .hint { flex: 1 1 100%; }

  .legenda-tabeli {
    max-width: 1240px; margin: 0 auto 18px;
    font-size: 12px; line-height: 1.7; color: var(--muted);
    border-top: 1px solid var(--line); border-bottom: 1px solid var(--line);
    padding: 9px 2px;
  }
  .legenda-tabeli b {
    font-family: var(--data); font-weight: 700; color: #5a6066;
    letter-spacing: .02em;
  }
  .legenda-tabeli span { margin-right: 14px; white-space: nowrap; }
  .hint-h2h {
    max-width: 1240px; margin: 0 auto 14px; font-size: 12px;
    color: #5a6066; font-weight: 700; padding: 0 2px;
  }
  .hint-h2h .h2h-toggle { color: var(--muted); font-weight: 700; }

  /* forma z 5 ostatnich meczow */
  .forma {
    max-width: 1240px; margin: 0 auto 26px;
    display: flex; align-items: center; gap: 14px; flex-wrap: wrap;
  }
  .forma > b {
    font-size: 13px; letter-spacing: .1em; text-transform: uppercase;
    color: var(--muted); font-weight: 600;
  }
  .forma .boxes { display: flex; gap: 6px; }
  .forma .badge {
    width: 34px; height: 34px; display: grid; place-items: center;
    font-family: var(--display); font-size: 16px; font-weight: 600;
    color: #fff; letter-spacing: .02em;
  }
  /* te same kody co w tabeli (rezultat: W/R/P) - jeden alfabet w calej stronie */
  .badge.W { background: var(--win); }
  .badge.P { background: var(--loss); }
  .badge.R { background: var(--draw); }
  .badge.q { background: var(--line); color: #9aa1a7; }
  .forma .legenda { font-size: 11.5px; color: var(--muted); }

  /* dom/wyjazd: ta sama konwencja co tabele sezonow - obecny sezon po lewej.
     section>h2 dziedziczy styl naglowka z tabel sezonow (selektor jest ogolny). */
  .domwyjazd {
    max-width: 1240px; margin: 0 auto 26px;
    display: grid; grid-template-columns: 1fr 1fr; gap: 18px;
  }
  .dw-body { padding: 4px 14px 8px; }
  .dw-line {
    display: flex; align-items: baseline; gap: 10px;
    padding: 9px 0; border-bottom: 1px solid #eceae6;
  }
  .dw-line:last-child { border-bottom: none; }
  .dw-line .etyk {
    flex: 1 1 auto; font-family: var(--label); font-size: 12px;
    font-weight: 600; letter-spacing: .05em; text-transform: uppercase;
    color: var(--muted);
  }
  .dw-line .bil {
    font-family: var(--data); font-size: 18px; font-weight: 600;
    color: var(--signal);
  }
  .dw-line .pkt {
    font-family: var(--data); font-size: 11.5px; color: #6f7479;
    white-space: nowrap;
  }

  /* wykres pozycji */
  .charts {
    max-width: 1240px; margin: 0 auto 22px;
  }
  .charts[hidden] { display: none; }
  .chart-taby {
    display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px;
  }
  .chart-tab {
    font-family: var(--label); font-size: 12px; font-weight: 500;
    padding: 6px 12px; cursor: pointer;
    background: var(--panel); color: var(--ink);
    border: 1px solid var(--line); border-radius: 0;
  }
  .chart-tab[aria-pressed="true"] {
    background: var(--oxblood); color: #fff; border-color: var(--oxblood);
  }
  .chart-wyjasnienie {
    font-size: 12px; line-height: 1.6; color: var(--muted);
    margin: 0 0 14px; padding: 8px 10px; background: #f2efe9;
    border-left: 3px solid var(--oxblood);
  }
  .chart-wyjasnienie b { color: #5a6066; font-family: var(--data); }
  .chart-kolumny {
    display: grid; grid-template-columns: 1fr 1fr; gap: 18px;
  }
  .chart { background: var(--panel); border: 1px solid var(--line); }
  .chart h3 {
    font-family: var(--display); text-transform: uppercase; font-weight: 500;
    font-size: 13px; letter-spacing: .12em; margin: 0;
    padding: 9px 14px; background: var(--oxblood); color: #fff;
  }
  .chart h3 span { float: right; opacity: .75; font-family: var(--data); letter-spacing: 0; }
  .chart .wrap { padding: 10px 12px 6px; }
  .chart svg { width: 100%; height: auto; display: block; }
  .chart .pusto { padding: 20px 14px; font-size: 12.5px; color: var(--muted); }
  .grid-line { stroke: #e4e1dc; stroke-width: 1; }
  .grid-line-100 { stroke: #c2bdb6; stroke-width: 1; stroke-dasharray: 2 2; }
  .grid-label { fill: #a8aeb3; font-family: ui-monospace, monospace; font-size: 9px; }
  .seria { fill: none; stroke: var(--signal); stroke-width: 2; }
  .seria-xg { fill: none; stroke: var(--oxblood); stroke-width: 1.6; stroke-dasharray: 4 3; }
  .seria-strz { fill: none; stroke: #7a7f84; stroke-width: 1.6; stroke-dasharray: 1 3; }
  .kropka { fill: var(--panel); stroke: var(--signal); stroke-width: 1.6; }
  .ostatni { fill: var(--signal); stroke: none; }
  .etykieta { fill: var(--oxblood); font-family: ui-monospace, monospace;
    font-size: 11px; font-weight: 700; }
  .etykieta-xg { fill: var(--oxblood); opacity: .8; }
  .etykieta-strz { fill: #7a7f84; opacity: .9; }
  .chart-legenda {
    margin: 2px 14px 10px; font-size: 10.5px; color: var(--muted);
    display: flex; gap: 12px;
  }
  .chart-legenda .lg-gole { color: var(--signal); font-weight: 700; }
  .chart-legenda .lg-xg { color: var(--oxblood); }
  .chart-legenda .lg-strz { color: #6f7479; }
  @media (max-width: 860px) {
    .chart-kolumny { grid-template-columns: 1fr; }
  }
  button {
    font-family: var(--label); font-size: 13px; font-weight: 500;
    padding: 8px 14px; cursor: pointer;
    background: var(--panel); color: var(--ink);
    border: 1px solid var(--line); border-radius: 0;
  }
  button[aria-pressed="true"] { background: var(--oxblood); color: #fff; border-color: var(--oxblood); }
  button:focus-visible { outline: 2px solid var(--signal); outline-offset: 2px; }
  .hint { font-size: 12px; color: var(--muted); margin: 8px 0 0; }

  .seasons {
    max-width: 1240px; margin: 0 auto;
    display: grid; grid-template-columns: 1fr 1fr; gap: 18px; align-items: start;
  }
  section {
    background: var(--panel); border: 1px solid var(--line);
    min-width: 0;
  }
  section > h2 {
    font-family: var(--display); text-transform: uppercase;
    font-size: 15px; letter-spacing: .12em; margin: 0;
    padding: 11px 14px; background: var(--oxblood); color: #fff; font-weight: 500;
  }
  section > h2 span { float: right; opacity: .72; font-family: var(--data); letter-spacing: 0; }
  .csv-link { color: #fff; opacity: 1; text-decoration: none; border-bottom: 1px dotted rgba(255,255,255,.5); }
  .csv-link:hover { border-bottom-style: solid; }
  .scroll { overflow-x: auto; }
  table { border-collapse: collapse; width: 100%; font-family: var(--data); font-size: 12.5px; }
  thead th {
    font-family: var(--label); font-size: 9.5px; font-weight: 700;
    letter-spacing: .07em; text-transform: uppercase; color: var(--muted);
    text-align: right; padding: 9px 6px 7px; border-bottom: 1px solid var(--line);
    white-space: nowrap; position: sticky; top: 0; background: var(--panel);
  }
  thead th.match, thead th.gutter { text-align: left; }
  thead th.sortowalna { cursor: pointer; user-select: none; }
  thead th.sortowalna:hover { color: var(--oxblood); }
  /* w trybie zestawienia sortowanie psuloby wyrownanie kolejek - wygaszamy */
  .align-mode thead th.sortowalna { cursor: default; opacity: .5; }
  .align-mode thead th.sortowalna:hover { color: var(--muted); }
  td { padding: 6px; border-bottom: 1px solid #eceae6; text-align: right; white-space: nowrap; }
  tbody tr:hover td { background: #f2efe9; }
  .gutter { width: 16px; padding-left: 12px; }
  /* wstazka formy: splot sezonu widoczny przy przegladaniu w dol.
     te same kolory co badge.W/.R/.P - jeden jezyk wizualny dla wyniku w calej stronie */
  .tick { display: block; width: 7px; height: 15px; border: 1.5px solid var(--muted); }
  .tick.W { background: var(--win); border-color: var(--win); }
  .tick.R { background: var(--draw); border-color: var(--draw); }
  .tick.P { background: var(--loss); border-color: var(--loss); }
  .k { color: var(--muted); width: 26px; }
  .match { text-align: left; font-family: var(--label); font-size: 12.5px; white-space: normal; }
  .match .w { font-weight: 700; color: var(--oxblood); }
  .match { cursor: pointer; }
  .match:hover { text-decoration: underline; text-decoration-color: var(--line); }
  .h2h-toggle {
    display: inline-block; width: 12px; color: var(--muted);
    font-size: 10px; margin-right: 2px;
  }

  .h2h-panel td {
    background: #f2efe9; padding: 10px 16px 14px 40px;
    border-bottom: 1px solid var(--line); white-space: normal;
  }
  .h2h-tytul {
    display: flex; justify-content: space-between; align-items: baseline;
    gap: 14px; font-size: 11px; letter-spacing: .06em; text-transform: uppercase;
    color: var(--muted); font-weight: 600; margin-bottom: 7px;
  }
  .h2h-tytul .h2h-nazwa { min-width: 0; overflow-wrap: break-word; }
  .h2h-bilans {
    flex: none; white-space: nowrap; font-size: 12px;
    font-family: var(--data); letter-spacing: 0;
    text-transform: none; color: var(--oxblood); font-weight: 700;
  }
  .h2h-brak { font-size: 12px; color: var(--muted); font-style: italic; margin: 0; }
  .h2h-lista { display: flex; flex-direction: column; gap: 5px; }
  .h2h-linia { display: flex; align-items: baseline; gap: 9px; font-size: 12.5px; }
  .h2h-linia .badge { flex: none; }
  .h2h-sezon {
    font-family: var(--data); color: var(--muted); flex: none; width: 82px;
  }
  .h2h-mecz { flex: 1 1 auto; font-family: var(--label); }
  .h2h-wynik { font-family: var(--data); font-weight: 700; flex: none; }
  .score { font-weight: 700; }
  .wkrotce {
    font-weight: 500; font-style: italic; font-size: 11px;
    color: var(--muted); font-family: var(--label);
  }
  .xg { position: relative; }
  .xg-widzew { color: var(--signal); font-weight: 700; }
  /* xGA - dane rywala, stad przygaszony ton, nie czerwien sygnalowa
     zarezerwowana dla "to jest Widzew" */
  .xga { color: #9aa1a7; }
  /* slad xG pod liczba - dane, nie ozdoba */
  .xg i {
    position: absolute; left: 4px; right: 4px; bottom: 2px; height: 2px;
    background: var(--signal); opacity: .3; transform-origin: left;
  }
  .none { color: #c3bfb9; }
  .empty td { height: 28px; background: repeating-linear-gradient(135deg,
      #f6f4f0 0 4px, var(--panel) 4px 8px); }
  tfoot td {
    font-weight: 700; border-top: 2px solid var(--oxblood);
    border-bottom: none; padding-top: 9px; padding-bottom: 11px;
  }
  tfoot .match { font-family: var(--label); font-size: 10px; letter-spacing: .08em;
    text-transform: uppercase; color: var(--muted); font-weight: 700; }
  @media (max-width: 860px) {
    .seasons { grid-template-columns: 1fr; }
    .domwyjazd { grid-template-columns: 1fr; }
    thead th { position: static; }
  }
  @media (prefers-reduced-motion: no-preference) {
    tbody tr { transition: background .12s ease; }
  }
</style>
</head>
<body>
<header>
  <h1>WSTATZ <span>— widzewskie statystyki</span></h1>
  <p class="sub" id="sub"></p>
</header>

<div class="compare" id="compare"></div>

<div class="forma" id="forma"></div>

<div class="domwyjazd" id="domwyjazd"></div>

<div class="controls">
  <button id="mode" aria-pressed="false">Zestaw kolejka do kolejki</button>
  <button id="wykresy" aria-pressed="false">Pokaż wykresy</button>
  <p class="hint" id="hint">Najnowsza kolejka u góry. Kliknij nagłówek kolumny (np. xG), aby sortować — osobno dla każdego sezonu.</p>
</div>

<div class="charts" id="charts" hidden></div>

<p class="legenda-tabeli">
  <span><b>Wynik</b> — wynik meczu</span>
  <span><b>xG</b> — oczekiwane gole Widzewa</span>
  <span><b>xGA</b> — oczekiwane gole rywala (Expected Goals Against)</span>
  <span><b>Strz</b> — strzały łącznie</span>
  <span><b>N.br</b> — strzały na bramkę</span>
  <span><b>W.sz</b> — wielkie szanse</span>
  <span><b>%Pod</b> — podania celne</span>
  <span><b>Pkt</b> — punkty ligowe narastająco</span>
  <span><b>Poz</b> — miejsce w tabeli po tej kolejce</span>
</p>

<p class="hint-h2h"><span class="h2h-toggle">▸</span> Kliknij na mecz (nazwy drużyn), aby zobaczyć historię spotkań z tym rywalem.</p>

<div class="seasons" id="seasons"></div>

<footer id="stopka"></footer>

<script>
const DANE = __DANE__;
const METRYKI = [
  ["xg", "xG", 2],
  ["shots", "Strzały", 1],
  ["sot", "Na bramkę", 1],
  ["bc", "Wielkie szanse", 2],
  ["pass_pct", "% podań", 1],
];
const sezony = Object.keys(DANE.sezony).sort().reverse();  // biezacy pierwszy
const [teraz, wczesniej] = sezony;
let alignByRound = false;
const sortState = {};  // { "2026/27": {key:"widzew_xg", dir:"asc"} } - per sezon niezaleznie
const h2hOtwarte = new Set();  // zbior fixture_id z rozwinietym panelem H2H

// Historia z danym rywalem, przeszukujaca WSZYSTKIE sezony w DANE (aktywne)
// PLUS archiwum (jesli obecne) - archiwum ma tylko wyniki, bez statystyk,
// ale do H2H to wystarczy. Dziala bez zmian, gdy przybedzie kolejny sezon
// aktywny albo kolejny plik archiwalny.
function nazwySezonowDoH2H() {
  const zArchiwum = DANE.archiwum ? Object.keys(DANE.archiwum) : [];
  return [...sezony, ...zArchiwum];
}

function h2hDlaMeczu(mecz) {
  const rywal = mecz.rywal_nazwa;
  const zAktywnych = sezony
    .flatMap(s => DANE.sezony[s].mecze.map(m => ({ ...m, __sezon: s })));
  const zArchiwum = DANE.archiwum
    ? Object.keys(DANE.archiwum)
        .flatMap(s => DANE.archiwum[s].mecze.map(m => ({ ...m, __sezon: s })))
    : [];
  return [...zAktywnych, ...zArchiwum]
    .filter(m => m.rywal_nazwa === rywal && m.fixture_id !== mecz.fixture_id)
    .sort((a, b) => a.__sezon === b.__sezon
      ? b.kolejka - a.kolejka
      : b.__sezon.localeCompare(a.__sezon));
}

// Definicja kolumn tabeli w jednym miejscu - naglowek, klasa, klucz do sortowania.
// key===null oznacza kolumne nieklikalna (rynsztok, przeciwnik, wynik meczu).
const KOLUMNY = [
  { key: null, label: "", cls: "gutter" },
  { key: "kolejka", label: "K", cls: "k" },
  { key: null, label: "Gospodarz – Gość", cls: "match" },
  { key: null, label: "Wynik", cls: "" },
  { key: "widzew_xg", label: "xG", cls: "" },
  { key: "rywal_xg", label: "xGA", cls: "" },
  { key: "widzew_shots", label: "Strz", cls: "" },
  { key: "widzew_sot", label: "N.br", cls: "" },
  { key: "widzew_bc", label: "W.sz", cls: "" },
  { key: "widzew_pass_pct", label: "%Pod", cls: "" },
  { key: "punkty_do", label: "Pkt", cls: "" },
  { key: "pozycja", label: "Poz", cls: "" },
];

// Braki (null) zawsze na koniec, niezaleznie od kierunku - inaczej mecze bez
// danych "skacza" na gore przy sortowaniu rosnacym, co jest zaskakujace.
function porownaj(a, b, key, dir) {
  const av = a[key], bv = b[key];
  const aNull = av === null || av === undefined;
  const bNull = bv === null || bv === undefined;
  if (aNull && bNull) return 0;
  if (aNull) return 1;
  if (bNull) return -1;
  return dir === "asc" ? av - bv : bv - av;
}

// Bez aktywnego sortowania: naturalna kolejnosc, czyli najnowsza kolejka
// pierwsza - dokladnie tak jak dotad, DANE.mecze juz przychodzi w tym porzadku.
function wierszeSezonu(sezon) {
  const mecze = DANE.sezony[sezon].mecze.slice();
  const stan = sortState[sezon];
  if (!stan) return mecze;
  return mecze.sort((a, b) => porownaj(a, b, stan.key, stan.dir));
}

function fmt(v, d) { return v === null || v === undefined ? "–" : v.toFixed(d); }

// "2026/27" -> "2026/2027"
function pelny(s) {
  const [a, b] = s.split("/");
  return b && b.length === 2 ? `${a}/${a.slice(0, 2)}${b}` : s;
}

function punktyNaMecz(sezon) {
  const s = DANE.sezony[sezon];
  const bil = s && s.srednie.bilans;
  if (!bil || !s.liczba_meczow) return null;
  return (bil.W * 3 + bil.R) / s.liczba_meczow;
}

// Gole strzelone minus suma xG - dodatnia wartosc znaczy, ze Widzew
// wykanacza sytuacje lepiej niz sugeruje ich jakosc.
function nadwyzkaGoli(sezon) {
  const mecze = DANE.sezony[sezon].mecze.filter(m => m.rezultat && m.widzew_xg !== null);
  if (!mecze.length) return null;
  const gole = mecze.reduce((s, m) => s + m.widzew_gole, 0);
  const xg = mecze.reduce((s, m) => s + m.widzew_xg, 0);
  return gole - xg;
}

// Ostatnie n rozegranych meczow, od najstarszego do najnowszego (lewo->prawo).
// Braki po lewej to mecze jeszcze nierozegrane - nie zero, nie pominiecie.
function formaSeria(sezon, n = 5) {
  const grane = DANE.sezony[sezon].mecze  // juz posortowane malejaco po kolejce
    .filter(m => m.rezultat)
    .slice(0, n)
    .reverse();
  const braki = n - grane.length;
  return Array(braki).fill(null).concat(grane);
}

function renderForma() {
  const el = document.getElementById("forma");
  if (!teraz) { el.innerHTML = ""; return; }
  const seria = formaSeria(teraz, 5);
  const boxes = seria.map(m => m
    ? `<span class="badge ${m.rezultat}" title="k${m.kolejka}: ${m.gospodarz} ${m.wynik} ${m.gosc}">${m.rezultat}</span>`
    : `<span class="badge q" title="mecz jeszcze nierozegrany">?</span>`
  ).join("");
  el.innerHTML = `<b>Forma</b><span class="boxes">${boxes}</span>
    <span class="legenda">ostatnie 5 kolejek · ${pelny(teraz)}</span>`;
}

// Bilans liczony wprost z pola venue, ktore juz siedzi w kazdym meczu -
// zero nowych danych, tylko inny przekroj tego, co juz mamy.
function bilansWedlugMiejsca(sezon, venue) {
  const mecze = DANE.sezony[sezon].mecze.filter(m => m.venue === venue && m.rezultat);
  const w = mecze.filter(m => m.rezultat === "W").length;
  const r = mecze.filter(m => m.rezultat === "R").length;
  const p = mecze.filter(m => m.rezultat === "P").length;
  const n = w + r + p;
  const pkt = w * 3 + r;
  return { w, r, p, n, pkt, pktNaMecz: n ? pkt / n : null };
}

function renderDomWyjazd() {
  const el = document.getElementById("domwyjazd");

  function linia(etykieta, b) {
    const bilansTxt = b.n ? `${b.w}-${b.r}-${b.p}` : "–";
    const pktTxt = b.n
      ? `${b.pkt} pkt · ${b.pktNaMecz.toFixed(2)}/mecz`
      : "brak rozegranych";
    return `<div class="dw-line">
      <span class="etyk">${etykieta}</span>
      <span class="bil">${bilansTxt}</span>
      <span class="pkt">${pktTxt}</span>
    </div>`;
  }

  function kolumna(sezon) {
    return `<section>
      <h2>${pelny(sezon)}</h2>
      <div class="dw-body">
        ${linia("W domu", bilansWedlugMiejsca(sezon, "H"))}
        ${linia("Na wyjeździe", bilansWedlugMiejsca(sezon, "A"))}
      </div>
    </section>`;
  }

  // sezony = [teraz, wczesniej] - obecny sezon zawsze pierwszy, wiec ladowany
  // do lewej kolumny gridu; ta sama konwencja co w tabelach ponizej.
  el.innerHTML = sezony.map(kolumna).join("");
}

const ZBUDOWANO = "__ZBUDOWANO__";

function naglowek() {
  const rozgrywki = DANE.sezony[teraz].mecze[0].rozgrywki || "Ekstraklasa";
  const zestaw = wczesniej
    ? `${pelny(teraz)} v ${pelny(wczesniej)}`
    : pelny(teraz);
  document.getElementById("sub").textContent =
    `${rozgrywki} ${zestaw} · kolejka po kolejce · aktualizowano ${ZBUDOWANO}`;
}

function stopka() {
  const daty = sezony.flatMap(s => DANE.sezony[s].mecze.map(m => m.data)).filter(Boolean);
  const ostatnia = daty.sort().slice(-1)[0];
  const braki = sezony.reduce((n, s) =>
    n + DANE.sezony[s].mecze.filter(m => m.pozycja === null).length, 0);
  document.getElementById("stopka").innerHTML =
    `<b>Statystyki meczowe:</b> Flashscore · <b>miejsca w tabeli:</b> Wikipedia<br>` +
    `Ostatni ujęty mecz: ${ostatnia || "—"}.` +
    (braki ? ` Meczów bez miejsca w tabeli: ${braki}.` : "") +
    ` Puste pole oznacza brak danych w źródle, nie zero.`;
}

function compare() {
  const el = document.getElementById("compare");
  const a = DANE.sezony[teraz].srednie;
  const b = wczesniej ? DANE.sezony[wczesniej].srednie : null;

  function box(nazwa, now, was, d) {
    let delta = "";
    if (now !== null && was !== null && now !== undefined && was !== undefined) {
      const diff = now - was;
      const cls = Math.abs(diff) < 0.005 ? "flat" : (diff > 0 ? "up" : "down");
      const znak = diff > 0 ? "+" : "";
      delta = `<span class="delta ${cls}">${znak}${diff.toFixed(d)}</span>`;
    }
    const drugi = wczesniej
      ? `<div class="row was"><span class="sez">${pelny(wczesniej)}</span>
           <span class="val">${fmt(was, d)}</span></div>`
      : "";
    return `<div class="metric"><b>${nazwa}</b>
      <div class="row now"><span class="sez">${pelny(teraz)}</span>
        <span class="val">${fmt(now, d)}</span>${delta}</div>
      ${drugi}</div>`;
  }

  function boxNadwyzka() {
    const t = nadwyzkaGoli(teraz);
    const p = wczesniej ? nadwyzkaGoli(wczesniej) : null;
    function wart(v) {
      if (v === null || v === undefined) return `<span class="val">–</span>`;
      const znak = v > 0 ? "+" : "";
      const klasa = v > 0.05 ? "up" : v < -0.05 ? "down" : "flat";
      return `<span class="val ${klasa}">${znak}${v.toFixed(2)}</span>`;
    }
    const drugi = wczesniej
      ? `<div class="row was"><span class="sez">${pelny(wczesniej)}</span>${wart(p)}</div>`
      : "";
    return `<div class="metric"><b>Gole − xG</b>
      <div class="row now"><span class="sez">${pelny(teraz)}</span>${wart(t)}</div>
      ${drugi}</div>`;
  }

  el.innerHTML =
    METRYKI.map(([k, nazwa, d]) =>
      box(nazwa, a["widzew_" + k], b ? b["widzew_" + k] : null, d)).join("") +
    box("Punkty / mecz", punktyNaMecz(teraz),
        wczesniej ? punktyNaMecz(wczesniej) : null, 2) +
    boxNadwyzka();
}

function wiersz(m) {
  const gospodarz = m.gospodarz === DANE.druzyna
    ? `<span class="w">${m.gospodarz}</span>` : m.gospodarz;
  const gosc = m.gosc === DANE.druzyna
    ? `<span class="w">${m.gosc}</span>` : m.gosc;
  const xgBar = m.widzew_xg !== null
    ? `<i style="transform:scaleX(${Math.min(m.widzew_xg / 2.8, 1)})"></i>` : "";
  const pusto = v => v === null || v === undefined
    ? '<span class="none">–</span>' : v;
  const otwarty = h2hOtwarte.has(m.fixture_id);
  const strzalkaH2H = `<span class="h2h-toggle">${otwarty ? "▾" : "▸"}</span>`;
  return `<tr>
    <td class="gutter"><span class="tick ${m.rezultat || ""}" title="${m.rezultat || ""}"></span></td>
    <td class="k">${m.kolejka}</td>
    <td class="match" data-fixture="${m.fixture_id}" title="Historia z tym rywalem">${strzalkaH2H}${gospodarz} – ${gosc}</td>
    <td class="score">${m.wynik || '<span class="wkrotce">wkrótce</span>'}</td>
    <td class="xg">${m.widzew_xg !== null
      ? `<span class="xg-widzew">${fmt(m.widzew_xg, 2)}</span>${xgBar}`
      : '<span class="none">–</span>'}</td>
    <td class="xga">${pusto(m.rywal_xg)}</td>
    <td>${pusto(m.widzew_shots)}</td>
    <td>${pusto(m.widzew_sot)}</td>
    <td>${pusto(m.widzew_bc)}</td>
    <td>${pusto(m.widzew_pass_pct)}</td>
    <td>${pusto(m.punkty_do)}</td>
    <td>${pusto(m.pozycja)}</td>
  </tr>${otwarty ? wierszH2H(m) : ""}`;
}

// Bilans W-R-P wliczajac klikniety mecz - "w sumie teraz mamy z nimi X-Y-Z",
// nie tylko historie sprzed tego meczu.
function h2hBilans(mecz, historia) {
  const wszystkie = [...historia, mecz];
  const w = wszystkie.filter(h => h.rezultat === "W").length;
  const r = wszystkie.filter(h => h.rezultat === "R").length;
  const p = wszystkie.filter(h => h.rezultat === "P").length;
  return { w, r, p, n: wszystkie.length };
}

function wierszH2H(mecz) {
  const historia = h2hDlaMeczu(mecz);
  const kolspan = KOLUMNY.length;
  let wnetrze, bilansHtml = "";
  if (!historia.length) {
    const listaSezonow = nazwySezonowDoH2H().map(pelny).join(", ");
    wnetrze = `<p class="h2h-brak">Brak innych spotkań z ${mecz.rywal_nazwa}
      w zebranych danych (sezony: ${listaSezonow}).</p>`;
  } else {
    const b = h2hBilans(mecz, historia);
    bilansHtml = `<span class="h2h-bilans">${b.n} m. · ${b.w}-${b.r}-${b.p}</span>`;
    wnetrze = `<div class="h2h-lista">` + historia.map(h => `
      <div class="h2h-linia">
        <span class="badge ${h.rezultat}">${h.rezultat}</span>
        <span class="h2h-sezon">${pelny(h.__sezon)} k${h.kolejka}</span>
        <span class="h2h-mecz">${h.gospodarz} – ${h.gosc}</span>
        <span class="h2h-wynik">${h.wynik || "–"}</span>
      </div>`).join("") + `</div>`;
  }
  return `<tr class="h2h-panel"><td colspan="${kolspan}">
    <div class="h2h-tytul"><span class="h2h-nazwa">Historia z ${mecz.rywal_nazwa}</span>${bilansHtml}</div>
    ${wnetrze}
  </td></tr>`;
}

function naglowekKolumny(sezon, col) {
  if (!col.key) {
    return `<th${col.cls ? ` class="${col.cls}"` : ""}>${col.label}</th>`;
  }
  const stan = sortState[sezon];
  const aktywna = stan && stan.key === col.key;
  const strzalka = aktywna ? (stan.dir === "asc" ? " ▲" : " ▼") : "";
  const klasy = ["sortowalna", col.cls].filter(Boolean).join(" ");
  return `<th class="${klasy}" data-key="${col.key}" data-sezon="${sezon}"
    title="Sortuj po ${col.label}">${col.label}${strzalka}</th>`;
}

const GITHUB_RAW = "https://raw.githubusercontent.com/fajny-heniu/wstatz/main/";

// "2025/26" -> "2025-26.csv" - odwzorowanie nazwy sezonu na nazwe pliku,
// dokladnie tak jak nazywaja sie pliki w repozytorium.
function nazwaPlikuCSV(sezon) {
  const [a, b] = sezon.split("/");
  return `${a}-${b}.csv`;
}

function tabela(sezon, wiersze) {
  const s = DANE.sezony[sezon];
  const sr = s.srednie;
  const body = wiersze.map(m => m
    ? wiersz(m)
    : `<tr class="empty"><td colspan="${KOLUMNY.length}"></td></tr>`).join("");
  const bil = sr.bilans ? `${sr.bilans.W}-${sr.bilans.R}-${sr.bilans.P}` : "";
  const naglowki = KOLUMNY.map(c => naglowekKolumny(sezon, c)).join("");
  return `<section>
    <h2>${sezon}<span>${s.liczba_meczow} m. · ${bil} ·
      <a class="csv-link" href="${GITHUB_RAW}${nazwaPlikuCSV(sezon)}" target="_blank" rel="noopener">CSV ↓</a></span></h2>
    <div class="scroll"><table>
      <thead><tr>${naglowki}</tr></thead>
      <tbody>${body}</tbody>
      <tfoot><tr>
        <td class="gutter"></td><td></td>
        <td class="match">Średnia z ${s.liczba_meczow} meczów</td><td></td>
        <td>${fmt(sr.widzew_xg, 2)}</td><td class="xga">${fmt(sr.rywal_xg, 2)}</td>
        <td>${fmt(sr.widzew_shots, 1)}</td>
        <td>${fmt(sr.widzew_sot, 1)}</td><td>${fmt(sr.widzew_bc, 2)}</td>
        <td>${fmt(sr.widzew_pass_pct, 1)}</td><td></td><td></td>
      </tr></tfoot>
    </table></div>
  </section>`;
}

function render() {
  const el = document.getElementById("seasons");
  el.classList.toggle("align-mode", alignByRound);
  if (alignByRound) {
    // wspolna os kolejek, rosnaco - kolejka 1 obok kolejki 1.
    // sortowanie po innej kolumnie nie ma tu sensu (psuje wyrownanie), stad wylaczone.
    const maks = Math.max(...sezony.flatMap(s =>
      DANE.sezony[s].mecze.map(m => m.kolejka)));
    const wg = {};
    sezony.forEach(s => {
      wg[s] = {};
      DANE.sezony[s].mecze.forEach(m => wg[s][m.kolejka] = m);
    });
    el.innerHTML = sezony.map(s =>
      tabela(s, Array.from({ length: maks }, (_, i) => wg[s][i + 1] || null))
    ).join("");
  } else {
    el.innerHTML = sezony.map(s => tabela(s, wierszeSezonu(s))).join("");
  }
}

// Tylko kolejki z wypelnionym miejscem w tabeli - wykres narasta
// sam w miare dostarczania danych, bez zadnej dodatkowej pracy.
function pozycjeSeria(sezon) {
  return DANE.sezony[sezon].mecze
    .filter(m => m.pozycja !== null && m.pozycja !== undefined)
    .map(m => ({ k: m.kolejka, p: m.pozycja }))
    .sort((a, b) => a.k - b.k);
}

// Wspolne wymiary dla wszystkich wykresow sezonowych - ten sam rozmiar
// i ta sama os X (34 kolejki) niezaleznie od tego, co akurat rysujemy,
// dzieki czemu wykresy pod soba w jednej kolumnie wygladaja jak jeden zestaw.
const CHART_W = 520, CHART_H = 220;
const CHART_PAD = { l: 26, r: 16, t: 16, b: 24 };
const CHART_MAXK = 34;

function svgWykresPozycji(sezon) {
  const dane = pozycjeSeria(sezon);
  if (!dane.length) {
    return `<div class="pusto">Brak jeszcze danych o pozycji w tabeli dla tego sezonu.</div>`;
  }
  const W = CHART_W, H = CHART_H, padL = CHART_PAD.l, padR = CHART_PAD.r,
        padT = CHART_PAD.t, padB = CHART_PAD.b;
  const maxK = 34;  // pelny sezon Ekstraklasy - wspolna os dla obu wykresow
  const pozycje = dane.map(d => d.p);
  const minP = 1;
  const maxP = Math.max(...pozycje, 6);
  const xOf = k => padL + (k - 1) / (maxK - 1) * (W - padL - padR);
  const yOf = p => padT + (p - minP) / (maxP - minP) * (H - padT - padB);

  const krokP = Math.max(1, Math.round(maxP / 6));
  let siatka = "";
  for (let p = minP; p <= maxP; p += krokP) {
    const y = yOf(p);
    siatka += `<line class="grid-line" x1="${padL}" y1="${y}" x2="${W - padR}" y2="${y}"/>`;
    siatka += `<text class="grid-label" x="2" y="${y + 3}">${p}</text>`;
  }
  let osX = "";
  for (let k = 1; k <= maxK; k += 5) {
    osX += `<text class="grid-label" x="${xOf(k)}" y="${H - 6}" text-anchor="middle">${k}</text>`;
  }

  const punkty = dane.map(d => `${xOf(d.k)},${yOf(d.p)}`).join(" ");
  const kropki = dane.map((d, i) => {
    const ostatni = i === dane.length - 1;
    return `<circle class="${ostatni ? "ostatni" : "kropka"}" cx="${xOf(d.k)}" cy="${yOf(d.p)}" r="${ostatni ? 4.5 : 3}"/>`;
  }).join("");
  const koniec = dane[dane.length - 1];
  const etykieta = `<text class="etykieta" x="${Math.min(xOf(koniec.k) + 8, W - 26)}" y="${yOf(koniec.p) + 4}">${koniec.p}.</text>`;

  return `<svg viewBox="0 0 ${W} ${H}">
    ${siatka}${osX}
    <polyline class="seria" points="${punkty}"/>
    ${kropki}${etykieta}
  </svg>`;
}

// xG per kolejka - jedna linia, ta sama os X co wykres pozycji.
function xgSeria(sezon) {
  return DANE.sezony[sezon].mecze
    .filter(m => m.rezultat && m.widzew_xg !== null)
    .map(m => ({ k: m.kolejka, xg: m.widzew_xg }))
    .sort((a, b) => a.k - b.k);
}

function svgWykresXG(sezon) {
  const dane = xgSeria(sezon);
  if (!dane.length) {
    return `<div class="pusto">Brak jeszcze rozegranych meczów w tym sezonie.</div>`;
  }
  const { l: padL, r: padR, t: padT, b: padB } = CHART_PAD;
  const W = CHART_W, H = CHART_H, maxK = CHART_MAXK;
  const maxY = Math.max(...dane.map(d => d.xg), 1.5);
  const krok = maxY > 3 ? 1 : 0.5;
  const xOf = k => padL + (k - 1) / (maxK - 1) * (W - padL - padR);
  const yOf = v => padT + (1 - v / maxY) * (H - padT - padB);

  let siatka = "";
  for (let y = 0; y <= maxY + 0.001; y += krok) {
    const py = yOf(y);
    siatka += `<line class="grid-line" x1="${padL}" y1="${py}" x2="${W - padR}" y2="${py}"/>`;
    siatka += `<text class="grid-label" x="2" y="${py + 3}">${(Math.round(y * 10) / 10)}</text>`;
  }
  let osX = "";
  for (let k = 1; k <= maxK; k += 5) {
    osX += `<text class="grid-label" x="${xOf(k)}" y="${H - 6}" text-anchor="middle">${k}</text>`;
  }

  const punkty = dane.map(d => `${xOf(d.k)},${yOf(d.xg)}`).join(" ");
  const kropki = dane.map((d, i) => {
    const ostatni = i === dane.length - 1;
    return `<circle class="${ostatni ? "ostatni" : "kropka"}" cx="${xOf(d.k)}" cy="${yOf(d.xg)}" r="${ostatni ? 4.5 : 3}"/>`;
  }).join("");
  const koniec = dane[dane.length - 1];
  const etykieta = `<text class="etykieta" x="${Math.min(xOf(koniec.k) + 8, W - 30)}" y="${yOf(koniec.xg) + 4}">${koniec.xg.toFixed(2)}</text>`;

  return `<svg viewBox="0 0 ${W} ${H}">
    ${siatka}${osX}
    <polyline class="seria" points="${punkty}"/>
    ${kropki}${etykieta}
  </svg>`;
}

// Gole i xG skumulowane narastajaco przez sezon - dwie linie na jednym
// wykresie. Gdy linia goli jest nad linia xG, Widzew wykanacza sytuacje
// lepiej niz sugeruje ich jakosc; gdy pod - trwoni sytuacje.
function goleXgSkumulowane(sezon) {
  const mecze = DANE.sezony[sezon].mecze
    .filter(m => m.rezultat && m.widzew_xg !== null)
    .sort((a, b) => a.kolejka - b.kolejka);
  let sumaGoli = 0, sumaXg = 0;
  return mecze.map(m => {
    sumaGoli += m.widzew_gole;
    sumaXg += m.widzew_xg;
    return { k: m.kolejka, gole: sumaGoli, xg: sumaXg };
  });
}

function svgWykresGoleXG(sezon) {
  const dane = goleXgSkumulowane(sezon);
  if (!dane.length) {
    return `<div class="pusto">Brak jeszcze rozegranych meczów w tym sezonie.</div>`;
  }
  const { l: padL, r: padR, t: padT, b: padB } = CHART_PAD;
  const W = CHART_W, H = CHART_H, maxK = CHART_MAXK;
  const maxY = Math.max(...dane.map(d => Math.max(d.gole, d.xg)), 2);
  const krok = maxY > 20 ? 10 : maxY > 8 ? 5 : 2;
  const xOf = k => padL + (k - 1) / (maxK - 1) * (W - padL - padR);
  const yOf = v => padT + (1 - v / maxY) * (H - padT - padB);

  let siatka = "";
  for (let y = 0; y <= maxY + 0.001; y += krok) {
    const py = yOf(y);
    siatka += `<line class="grid-line" x1="${padL}" y1="${py}" x2="${W - padR}" y2="${py}"/>`;
    siatka += `<text class="grid-label" x="2" y="${py + 3}">${Math.round(y)}</text>`;
  }
  let osX = "";
  for (let k = 1; k <= maxK; k += 5) {
    osX += `<text class="grid-label" x="${xOf(k)}" y="${H - 6}" text-anchor="middle">${k}</text>`;
  }

  const linGole = dane.map(d => `${xOf(d.k)},${yOf(d.gole)}`).join(" ");
  const linXg = dane.map(d => `${xOf(d.k)},${yOf(d.xg)}`).join(" ");
  const koniec = dane[dane.length - 1];
  const etGole = `<text class="etykieta" x="${Math.min(xOf(koniec.k) + 8, W - 26)}" y="${yOf(koniec.gole) + 4}">${koniec.gole}</text>`;
  const etXg = `<text class="etykieta etykieta-xg" x="${Math.min(xOf(koniec.k) + 8, W - 26)}" y="${yOf(koniec.xg) + 4}">${koniec.xg.toFixed(1)}</text>`;

  return `<svg viewBox="0 0 ${W} ${H}">
    ${siatka}${osX}
    <polyline class="seria-xg" points="${linXg}"/>
    <polyline class="seria" points="${linGole}"/>
    ${etGole}${etXg}
  </svg>
  <p class="chart-legenda"><span class="lg-gole">— gole</span><span class="lg-xg">┄ xG</span></p>`;
}

// Punkty rzeczywiste vs maksymalnie mozliwe (3 x kolejka - tyle dalyby same
// wygrane). "Tempo" na koncu wykresu to prosty % realizacji potencjalu,
// ten sam typ liczenia co gole-vs-xG, tylko odniesiony do punktow.
function punktySkumulowane(sezon) {
  return DANE.sezony[sezon].mecze
    .filter(m => m.rezultat && m.punkty_do !== null)
    .map(m => ({ k: m.kolejka, pkt: m.punkty_do, maks: m.kolejka * 3 }))
    .sort((a, b) => a.k - b.k);
}

function svgWykresPunkty(sezon) {
  const dane = punktySkumulowane(sezon);
  if (!dane.length) {
    return `<div class="pusto">Brak jeszcze rozegranych meczów w tym sezonie.</div>`;
  }
  const { l: padL, r: padR, t: padT, b: padB } = CHART_PAD;
  const W = CHART_W, H = CHART_H, maxK = CHART_MAXK;
  const maxY = maxK * 3;  // maksymalna mozliwa linia zawsze siega 3 x 34
  const krok = 20;
  const xOf = k => padL + (k - 1) / (maxK - 1) * (W - padL - padR);
  const yOf = v => padT + (1 - v / maxY) * (H - padT - padB);

  let siatka = "";
  for (let y = 0; y <= maxY + 0.001; y += krok) {
    const py = yOf(y);
    siatka += `<line class="grid-line" x1="${padL}" y1="${py}" x2="${W - padR}" y2="${py}"/>`;
    siatka += `<text class="grid-label" x="2" y="${py + 3}">${Math.round(y)}</text>`;
  }
  let osX = "";
  for (let k = 1; k <= maxK; k += 5) {
    osX += `<text class="grid-label" x="${xOf(k)}" y="${H - 6}" text-anchor="middle">${k}</text>`;
  }

  // linia maksymalna to prosta strzalka od 3 do maxY - nie potrzebuje danych,
  // tylko dwoch koncow
  const linMaks = `${xOf(1)},${yOf(3)} ${xOf(dane[dane.length - 1].k)},${yOf(dane[dane.length - 1].maks)}`;
  const linPkt = dane.map(d => `${xOf(d.k)},${yOf(d.pkt)}`).join(" ");
  const koniec = dane[dane.length - 1];
  const tempo = Math.round(koniec.pkt / koniec.maks * 100);
  const etPkt = `<text class="etykieta" x="${Math.min(xOf(koniec.k) + 8, W - 30)}" y="${yOf(koniec.pkt) + 4}">${koniec.pkt}</text>`;
  const etMaks = `<text class="etykieta etykieta-xg" x="${Math.min(xOf(koniec.k) + 8, W - 30)}" y="${yOf(koniec.maks) + 4}">${koniec.maks}</text>`;

  return `<svg viewBox="0 0 ${W} ${H}">
    ${siatka}${osX}
    <polyline class="seria-xg" points="${linMaks}"/>
    <polyline class="seria" points="${linPkt}"/>
    ${etPkt}${etMaks}
  </svg>
  <p class="chart-legenda"><span class="lg-gole">— punkty</span><span class="lg-xg">┄ maksimum (3×k)</span>
    <span style="margin-left:auto">tempo: ${tempo}%</span></p>`;
}

// Trend z wygaszaniem wykladniczym (polokres 8 kolejek - kazdy kolejny
// mecz w tyl wazy polowe tego, co mecz o 8 kolejek nowszy). Trzy metryki
// (punkty, strzaly, xGA) na wspolnej skali "% sredniej sezonowej", zamiast
// blendowania w jedna liczbe - unika problemu roznych skal (punkty 0-3,
// strzaly 5-25), ktory pokazal, ze prosta suma bylaby zdominowana przez
// strzaly. xGA nizej = lepiej, pozostale dwie wyzej = lepiej - to jest
// jedyna asymetria, ktorej nie da sie ukryc bez zaciemniania liczb.
const POLOKRES_KOLEJEK = 8;
const XI_TREND = Math.log(2) / POLOKRES_KOLEJEK;

function pktMeczu(m) {
  return m.rezultat === "W" ? 3 : m.rezultat === "R" ? 1 : 0;
}

function trendWygaszony(sezon) {
  const mecze = DANE.sezony[sezon].mecze
    .filter(m => m.rezultat && m.widzew_shots !== null)
    .sort((a, b) => a.kolejka - b.kolejka);

  return mecze.map((_, i) => {
    const K = mecze[i].kolejka;
    let sumaW = 0, sumaPkt = 0, sumaStrz = 0, sumaXga = 0;
    for (let j = 0; j <= i; j++) {
      const x = mecze[j];
      const w = Math.exp(-XI_TREND * (K - x.kolejka));
      sumaW += w;
      sumaPkt += w * pktMeczu(x);
      sumaStrz += w * x.widzew_shots;
      sumaXga += w * x.rywal_xg;
    }
    return { k: K, pkt: sumaPkt / sumaW, strz: sumaStrz / sumaW, xga: sumaXga / sumaW };
  });
}

function svgWykresTrend(sezon) {
  const dane = trendWygaszony(sezon);
  if (!dane.length) {
    return `<div class="pusto">Brak jeszcze rozegranych meczów w tym sezonie.</div>`;
  }
  const sr = DANE.sezony[sezon].srednie;
  const srPkt = punktyNaMecz(sezon);
  const srStrz = sr.widzew_shots;
  const srXga = sr.rywal_xg;
  if (!srPkt || !srStrz || !srXga) {
    return `<div class="pusto">Za mało danych do policzenia trendu.</div>`;
  }

  const seria = dane.map(d => ({
    k: d.k,
    pkt: d.pkt / srPkt * 100,
    strz: d.strz / srStrz * 100,
    xga: d.xga / srXga * 100,
  }));

  const { l: padL, r: padR, t: padT, b: padB } = CHART_PAD;
  const W = CHART_W, H = CHART_H, maxK = CHART_MAXK;
  const wszystkie = seria.flatMap(s => [s.pkt, s.strz, s.xga]);
  const maxY = Math.max(...wszystkie, 130);
  const minY = Math.min(...wszystkie, 70, 0);
  const krok = 25;
  const xOf = k => padL + (k - 1) / (maxK - 1) * (W - padL - padR);
  const yOf = v => padT + (1 - (v - minY) / (maxY - minY)) * (H - padT - padB);

  let siatka = "";
  for (let y = Math.ceil(minY / krok) * krok; y <= maxY + 0.001; y += krok) {
    const py = yOf(y);
    siatka += `<line class="grid-line" x1="${padL}" y1="${py}" x2="${W - padR}" y2="${py}"/>`;
    siatka += `<text class="grid-label" x="2" y="${py + 3}">${y}%</text>`;
  }
  // linia odniesienia 100% - "dokladnie srednia sezonu", wyrazniejsza niz zwykla siatka
  const y100 = yOf(100);
  siatka += `<line class="grid-line-100" x1="${padL}" y1="${y100}" x2="${W - padR}" y2="${y100}"/>`;
  let osX = "";
  for (let k = 1; k <= maxK; k += 5) {
    osX += `<text class="grid-label" x="${xOf(k)}" y="${H - 6}" text-anchor="middle">${k}</text>`;
  }

  const linia = (klucz) => seria.map(s => `${xOf(s.k)},${yOf(s[klucz])}`).join(" ");
  const koniec = seria[seria.length - 1];
  const etTxt = (klucz, klasa) =>
    `<text class="etykieta ${klasa}" x="${Math.min(xOf(koniec.k) + 8, W - 30)}" y="${yOf(koniec[klucz]) + 4}">${Math.round(koniec[klucz])}%</text>`;

  return `<svg viewBox="0 0 ${W} ${H}">
    ${siatka}${osX}
    <polyline class="seria-strz" points="${linia("strz")}"/>
    <polyline class="seria-xg" points="${linia("xga")}"/>
    <polyline class="seria" points="${linia("pkt")}"/>
    ${etTxt("pkt", "")}${etTxt("strz", "etykieta-strz")}${etTxt("xga", "etykieta-xg")}
  </svg>
  <p class="chart-legenda">
    <span class="lg-gole">— punkty</span>
    <span class="lg-strz">╍ strzały</span>
    <span class="lg-xg">┄ xGA (niżej = lepiej)</span>
  </p>`;
}

// Definicje wykresow w jednym miejscu - zakladki generuja sie z tej listy,
// dodanie nowego wykresu w przyszlosci to jedna nowa linia tutaj.
const DEFINICJE_WYKRESOW = [
  { id: "pozycja", etykieta: "Pozycja w tabeli", fn: svgWykresPozycji },
  { id: "xg", etykieta: "xG per kolejka", fn: svgWykresXG },
  { id: "gole-xg", etykieta: "Gole vs xG", fn: svgWykresGoleXG },
  { id: "punkty", etykieta: "Punkty vs możliwe", fn: svgWykresPunkty },
  { id: "trend", etykieta: "Trend", fn: svgWykresTrend },
];
let aktywnyWykres = "pozycja";

function renderCharts() {
  const el = document.getElementById("charts");
  const aktywny = DEFINICJE_WYKRESOW.find(d => d.id === aktywnyWykres) || DEFINICJE_WYKRESOW[0];

  const zakladki = DEFINICJE_WYKRESOW.map(d => `<button class="chart-tab"
    data-wykres="${d.id}" aria-pressed="${d.id === aktywny.id}">${d.etykieta}</button>`).join("");

  const wyjasnienie = aktywny.id === "trend"
    ? `<p class="chart-wyjasnienie">Ile procent własnej średniej sezonowej reprezentuje
       bieżąca forma Widzewa — każdy mecz waży tym mniej, im dawniej się odbył
       (nowsze liczą się bardziej, półokres ${POLOKRES_KOLEJEK} kolejek). <b>100%</b> to
       dokładnie średnia całego sezonu, <b>113%</b> znaczy „ostatnio lepiej niż
       przeciętnie w tym sezonie".</p>`
    : "";

  const kolumny = sezony.map(s => {
    const ost = pozycjeSeria(s).slice(-1)[0];
    const info = ost ? `${ost.p}. po k.${ost.k}` : "brak danych";
    return `<div class="chart">
      <h3>${pelny(s)}<span>${info}</span></h3>
      <div class="wrap">${aktywny.fn(s)}</div>
    </div>`;
  }).join("");

  el.innerHTML = `<div class="chart-taby">${zakladki}</div>
    ${wyjasnienie}
    <div class="chart-kolumny">${kolumny}</div>`;
}

document.getElementById("charts").addEventListener("click", e => {
  const tab = e.target.closest(".chart-tab");
  if (!tab) return;
  aktywnyWykres = tab.dataset.wykres;
  renderCharts();
});

document.getElementById("mode").addEventListener("click", e => {
  alignByRound = !alignByRound;
  e.currentTarget.setAttribute("aria-pressed", String(alignByRound));
  e.currentTarget.textContent = alignByRound
    ? "Najnowsza kolejka u góry" : "Zestaw kolejka do kolejki";
  document.getElementById("hint").textContent = alignByRound
    ? "Kolejki zestawione od 1. Kreskowane wiersze to kolejki jeszcze nierozegrane. Sortowanie kolumn wyłączone w tym widoku."
    : "Najnowsza kolejka u góry. Kliknij nagłówek kolumny (np. xG), aby sortować — osobno dla każdego sezonu.";
  render();
});

document.getElementById("wykresy").addEventListener("click", e => {
  const panel = document.getElementById("charts");
  const otwarty = !panel.hasAttribute("hidden");
  if (otwarty) {
    panel.setAttribute("hidden", "");
    e.currentTarget.textContent = "Pokaż wykresy";
    e.currentTarget.setAttribute("aria-pressed", "false");
  } else {
    renderCharts();
    panel.removeAttribute("hidden");
    e.currentTarget.textContent = "Ukryj wykresy";
    e.currentTarget.setAttribute("aria-pressed", "true");
  }
});

document.getElementById("seasons").addEventListener("click", e => {
  const th = e.target.closest("th[data-key]");
  if (th) {
    if (alignByRound) return;  // w trybie zestawienia sortowanie wylaczone
    const sezon = th.dataset.sezon, key = th.dataset.key;
    const obecny = sortState[sezon];
    if (!obecny || obecny.key !== key) {
      sortState[sezon] = { key, dir: "asc" };
    } else if (obecny.dir === "asc") {
      sortState[sezon] = { key, dir: "desc" };
    } else {
      delete sortState[sezon];  // trzeci klik - powrot do najnowszej kolejki na gorze
    }
    render();
    return;
  }

  const td = e.target.closest("td.match[data-fixture]");
  if (td) {
    const fid = td.dataset.fixture;
    if (h2hOtwarte.has(fid)) h2hOtwarte.delete(fid); else h2hOtwarte.add(fid);
    render();
  }
});

naglowek();
compare();
renderForma();
renderDomWyjazd();
stopka();
render();
</script>
</body>
</html>
"""


MIESIACE_PL = ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca",
               "lipca", "sierpnia", "września", "października",
               "listopada", "grudnia"]


def main():
    if not DATA.exists():
        sys.exit("BLAD: brak data.json. Uruchom najpierw: python3 zbuduj.py")
    dane = json.loads(DATA.read_text(encoding="utf-8"))
    if not dane.get("sezony"):
        sys.exit("BLAD: data.json nie zawiera zadnego sezonu.")

    dzis = datetime.date.today()
    zbudowano = f"{dzis.day} {MIESIACE_PL[dzis.month - 1]} {dzis.year} r."

    html = SZABLON.replace("__DANE__", json.dumps(dane, ensure_ascii=False))
    html = html.replace("__ZBUDOWANO__", zbudowano)
    OUT.write_text(html, encoding="utf-8")

    print(f"Zapisano {OUT.name}  ({len(html) // 1024} kB)  [aktualizowano: {zbudowano}]")
    for nazwa, s in sorted(dane["sezony"].items(), reverse=True):
        braki = sum(1 for m in s["mecze"] if m.get("pozycja") is None)
        info = f", bez pozycji: {braki}" if braki else ""
        print(f"  {nazwa}: {s['liczba_meczow']} meczow{info}")


if __name__ == "__main__":
    main()
