#!/usr/bin/env node
/* Test af træk-og-slip i indretning (ekstraherer koden direkte fra index.html).
   Køres med: node test-drag.mjs  */
import { readFileSync } from 'fs';

const html = readFileSync(new URL('./index.html', import.meta.url), 'utf8');
const script = html.match(/<script>([\s\S]*)<\/script>/)[1];

function section(start, end) {
  const i = script.indexOf(start);
  const j = script.indexOf(end, i);
  if (i < 0 || j < 0) throw new Error('section ikke fundet: ' + start);
  return script.slice(i, j);
}

const ITEM_TYPE = script.match(/const ITEM_TYPE = \{[^}]*\};/)[0];
const SLOT_TYPE = script.match(/const SLOT_TYPE = \{[^}]*\};/)[0];
const fitsLine = script.match(/function fits\(id, k\)[^\n]*\n/)[0];
const ROOM_SLOTS = section('const ROOM_SLOTS = {', '\nfunction slotHTML');
const dragCode = section('/* ---------- træk og slip (indretning) ---------- */', "document.addEventListener('input'");

/* ---------- fake DOM ---------- */
function mk(tag, cls, attrs) {
  const el = {
    tag, attrs: attrs || {}, style: {}, parent: null, children: [],
    disabled: false, clientWidth: 616, _cls: new Set(cls ? cls.split(' ') : []),
    classList: {
      add: (...c) => c.forEach(x => el._cls.add(x)),
      remove: (...c) => c.forEach(x => el._cls.delete(x)),
      contains: c => el._cls.has(c),
    },
    getAttribute: n => (n in el.attrs ? el.attrs[n] : null),
    setAttribute: (n, v) => { el.attrs[n] = v; },
    appendChild: c => { el.children.push(c); c.parent = el; },
    remove: () => { el.removed = true; },
    querySelector: sel => (sel === 'svg.pynt' ? el._svg : null),
    closest: sel => closest(el, sel),
  };
  el._svg = { setAttribute() {}, style: {}, cloneNode: () => ({ setAttribute() {}, style: {} }) };
  return el;
}
function matches(el, sel) {
  if (!el || !el._cls) return false;
  if (sel === 'button.slot') return el.tag === 'button' && el._cls.has('slot');
  if (sel === '.inv-grid button') {
    if (el.tag !== 'button') return false;
    let n = el;
    while (n) { if (n._cls && n._cls.has('inv-grid')) return true; n = n.parent; }
    return false;
  }
  if (sel === '[data-on]') return 'data-on' in el.attrs;
  if (sel.startsWith('.')) return el._cls.has(sel.slice(1));
  return false;
}
function closest(el, sel) { let n = el; while (n) { if (matches(n, sel)) return n; n = n.parent; } return null; }

let pointee = null;
const listeners = {};
const fakeDoc = {
  addEventListener: (t, fn) => { (listeners[t] ||= []).push(fn); },
  querySelector: sel => (sel === '.room-stage' ? { clientWidth: 616 } : null),
  elementFromPoint: () => pointee,
  body: { appendChild() {}, children: [] },
  createElement: tag => mk(tag),
};
globalThis.document = fakeDoc;

const calls = { place: [], store: [], set: [], sfx: [], click: [] };
const game = {
  state: { screen: 'decorate', place: {}, owned: [], decoSel: null },
  placeItem: (id, k) => calls.place.push([id, k]),
  storeItem: id => calls.store.push(id),
  sfx: n => calls.sfx.push(n),
  setState: o => calls.set.push(o),
};
globalThis.game = game;
globalThis.HANDLERS = [() => calls.click.push(1)];

/* Kode der skal køres i denne kontekst */
(0, eval)(`${ITEM_TYPE}\n${SLOT_TYPE}\n${fitsLine}\n${ROOM_SLOTS}\n${dragCode}`);

/* ---------- scenarier ---------- */
const slot = (k, item) => mk('button', 'slot edit', { 'data-key': 'slot-' + k, 'data-on': '0' });
const inv = id => { const b = mk('button', 'inv', { 'data-key': 'inv-' + id, 'data-on': '0' }); const grid = mk('div', 'inv-grid'); grid.appendChild(b); b.parent = grid; return b; };
const ev = (t, x, y, target) => ({ isPrimary: true, clientX: x, clientY: y, target, preventDefault() {} });
const fire = (t, e) => listeners[t].forEach(fn => fn(e));

function reset(place, owned) {
  for (const k of Object.keys(calls)) calls[k].length = 0;
  game.state = { screen: 'decorate', place: { ...place }, owned, decoSel: null };
  pointee = null;
  fakeTime += 10_000;
}

let fakeTime = 1_000_000;
Date.now = () => fakeTime;

let fails = 0;
function check(name, cond) {
  console.log((cond ? 'PASS' : 'FAIL') + '  ' + name);
  if (!cond) fails++;
}

// 1. Træk kaktus S1 -> D1 (gyldigt: staa -> staa)
reset({ S1: 'kaktus' }, ['kaktus', 'plakat']);
const sS1 = slot('S1', 'kaktus'), sD1 = slot('D1');
fire('pointerdown', ev('pointerdown', 384, 406, sS1));
pointee = sD1;
fire('pointermove', ev('pointermove', 500, 620, sD1));
check('1. drag aktiveret + target markeret dragok', sD1._cls.has('dragok'));
fire('pointerup', ev('pointerup', 512, 632, sD1));
check('1. placeItem(kaktus, D1) kaldt', JSON.stringify(calls.place) === JSON.stringify([['kaktus', 'D1']]));
check('1. klik-undertrykt efter drag', calls.click.length === 0);

// 2. Ugyldig drop: kaktus (staa) -> H1 (haeng)
reset({ S1: 'kaktus' }, ['kaktus']);
const sH1 = slot('H1');
fire('pointerdown', ev('pointerdown', 384, 406, sS1));
pointee = sH1;
fire('pointermove', ev('pointermove', 120, 150, sH1));
check('2. ugyldig target markeret dragbad', sH1._cls.has('dragbad'));
fire('pointerup', ev('pointerup', 120, 150, sH1));
check('2. drag afleverer til placeItem (kaktus, H1)', JSON.stringify(calls.place) === JSON.stringify([['kaktus', 'H1']]));
check('2. fits() afviser kaktus på H1 (spillet ryster af med boing)', fits('kaktus', 'H1') === false);

// 3. Slup på lageret (inventar)
reset({ S1: 'kaktus' }, ['kaktus']);
const sInv = inv('kaktus');
fire('pointerdown', ev('pointerdown', 384, 406, sS1));
pointee = sInv;
fire('pointermove', ev('pointermove', 800, 200, sInv));
fire('pointerup', ev('pointerup', 800, 200, sInv));
check('3. storeItem(kaktus) ved drop på inventar', JSON.stringify(calls.store) === JSON.stringify(['kaktus']));

// 4. Rent tap (ingen bevægelse) -> ingen drag, klikkender
reset({ S1: 'kaktus' }, ['kaktus']);
fire('pointerdown', ev('pointerdown', 384, 406, sS1));
fire('pointerup', ev('pointerup', 384, 406, sS1));
fire('click', ev('click', 384, 406, sS1));
check('4. tap giver klik (gammel flow rører)', calls.click.length === 1 && calls.place.length === 0);

// 5. Træk plakat (haeng) fra inventar -> H1 (gyldigt)
reset({}, ['plakat']);
const sPlakat = inv('plakat');
fire('pointerdown', ev('pointerdown', 800, 200, sPlakat));
pointee = sH1;
fire('pointermove', ev('pointermove', 60, 100, sH1));
fire('pointerup', ev('pointerup', 60, 100, sH1));
check('5. placeItem(plakat, H1) fra inventar', JSON.stringify(calls.place) === JSON.stringify([['plakat', 'H1']]));

// 6. Swap: kaktus S1 -> S2 (optaget af plakat? nej - plakat er haeng og S2 er staa -> ingen swap, flyttes + old på lager)
reset({ S1: 'kaktus', S2: 'kop' }, ['kaktus', 'kop']);
fire('pointerdown', ev('pointerdown', 384, 406, sS1));
pointee = slot('S2');
fire('pointermove', ev('pointermove', 390, 370, pointee));
fire('pointerup', ev('pointerup', 390, 370, pointee));
check('6. placeItem(kaktus, S2) (swap/håndtering i game.placeItem)', JSON.stringify(calls.place) === JSON.stringify([['kaktus', 'S2']]));

console.log(fails === 0 ? '\nALLE TESTER PÅ PLADS' : `\n${fails} FEJLEDE TESTER`);
process.exit(fails === 0 ? 0 : 1);
