// Kontrola strony po kazdej zmianie danych. Trzymana w katalogu wyjsciowym
// (i w repo), bo /home/claude zeruje sie miedzy sesjami.
const fs = require('fs');
const js = fs.readFileSync(__dirname + '/index.html','utf8').split('<script>')[1].split('</script>')[0];
const el = () => ({ innerHTML:'', style:{}, dataset:{}, hidden:false, offsetWidth:100, value:'',
  classList:{toggle(){},add(){},remove(){},contains(){return false;}}, addEventListener(){},
  appendChild(){}, setAttribute(){}, getAttribute(){return null;}, querySelector(){return el();},
  querySelectorAll(){return [];}, getBoundingClientRect(){return {left:0,top:0,width:520,height:220};},
  closest(){return null;}, remove(){} });
global.document={getElementById(){return el();},querySelector(){return el();},querySelectorAll(){return [];},
  addEventListener(){},createElement(){return el();},documentElement:el(),body:el(),title:''};
global.window={matchMedia:()=>({matches:false}),addEventListener(){},innerWidth:390,
  navigator:{userAgent:'iPhone Safari',standalone:false}};
global.localStorage={getItem(){return null;},setItem(){},removeItem(){}};
Object.defineProperty(global,'navigator',{value:{userAgent:'iPhone Safari'},writable:true,configurable:true});

const A = new Function(`${js}\nreturn {DANE, teraz, wczesniej, odpowiedzNaPytanie, najblizszyMecz,
  formaSeria, h2hDlaMeczu, h2hBilans, wiersz, wierszeSezonu, statystykiKadencji, renderKadencje,
  znajdzDruzyne, znajdzTrenera, tabela};`)();
let bledy=0;
const ok=(n,w,d='')=>{console.log((w?'OK   ':'BLAD ')+n+(d?'  -> '+d:'')); if(!w)bledy++;};
const odp=q=>{const r=A.odpowiedzNaPytanie(q);return r?r.tekst.replace(/<[^>]+>/g,''):null;};

const grane = A.DANE.sezony[A.teraz].mecze.filter(m=>m.rezultat);
const nm = A.najblizszyMecz(A.teraz);

console.log('--- dane sezonu ---');
ok('kolejnosc malejaca, brak dziur',
   grane.every((m,i)=> i===0 || grane[i-1].kolejka === m.kolejka+1));
ok('wszystkie rozegrane maja pozycje', grane.every(m=>m.pozycja>0),
   grane.filter(m=>!m.pozycja).map(m=>'k'+m.kolejka).join(',')||'komplet');
ok('punkty zgodne z bilansem', (()=>{const b=A.DANE.sezony[A.teraz].srednie.bilans;
   return b.W*3+b.R === grane[0].punkty_do;})(), `${grane[0].punkty_do} pkt`);

console.log('\n--- zapowiedz i H2H ---');
ok('jest dokladnie jedna zapowiedz jako najblizsza', !!nm, nm?`k${nm.kolejka} ${nm.rywal_nazwa}`:'brak');
const hist = nm ? A.h2hDlaMeczu(nm) : [];
const autoPanel = A.wierszeSezonu(A.teraz).filter(m=>A.wiersz(m,A.teraz).includes('h2h-auto'));
ok('auto-panel tylko gdy jest historia',
   hist.length ? autoPanel.length===1 : autoPanel.length===0,
   `historia ${hist.length} m., paneli ${autoPanel.length}`);
if (hist.length) { const b=A.h2hBilans(nm,hist); ok('bilans H2H sumuje sie', b.n===b.w+b.r+b.p,
   `${b.n} m. ${b.w}-${b.r}-${b.p}`); }

console.log('\n--- forma ---');
const seria = A.formaSeria(A.teraz,5);
ok('forma: zapowiedz + 5 rozegranych', seria.length===6 && !seria[0].rezultat,
   seria.map(m=>`k${m.kolejka}${m.rezultat||'?'}`).join(' '));

console.log('\n--- kadencje ---');
const suma = (A.DANE.kadencje||[]).reduce((s,o)=>s+o.n,0);
const wszystkieMecze = [A.DANE.sezony, A.DANE.archiwum||{}].reduce((s,g)=>
  s+Object.values(g).reduce((x,v)=>x+v.mecze.filter(m=>m.rezultat).length,0),0);
ok('kadencje pokrywaja wszystkie mecze', suma===wszystkieMecze, `${suma} z ${wszystkieMecze}`);
ok('panel kadencji bez NaN', !/NaN|undefined/.test(A.renderKadencje()));

console.log('\n--- pytania ---');
[['kiedy następny mecz', /Kolejka/], ['ile mamy punktów', /pkt/],
 ['ile bramek zdobyliśmy', /strzelone/], ['średnie xG', /xG, sezon/],
 ['jak nam idzie z Legią', /Legia/], ['w domu czy na wyjeździe', /U siebie/],
 ['ile meczów bez porażki', /[Ss]eria|przegrany/], ['najlepszy mecz sezonu', /Rekord/],
 ['xG w 2023', /nie mam danych|nie mam/], ['kto jest najlepszym strzelcem', /zawodnik/]]
 .forEach(([q,wz])=>{const r=odp(q); ok(`"${q}"`, !!r && wz.test(r), (r||'null').slice(0,80));});
ok('pytanie spoza zakresu -> null', A.odpowiedzNaPytanie('stolica Francji')===null);

console.log('\n--- calosc ---');
ok('tabela sezonu bez NaN/undefined',
   !/NaN|undefined/.test(A.tabela(A.teraz, A.wierszeSezonu(A.teraz))));

console.log(bledy?`\n${bledy} BLEDOW`:'\nWszystkie testy przeszly');
process.exit(bledy?1:0);
