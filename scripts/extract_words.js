#!/usr/bin/env node
// Extracts every clickable-word text (ruby-anchored expanded terms + pure-kana
// chunks) from index.html's segments data — the exact same units the browser's
// click-to-pronounce feature speaks. Reuses the ACTUAL vendored TinySegmenter and
// PARTICLE_STOP_WORDS straight out of index.html (via eval), rather than a second
// hand-written copy, so this can't silently drift from what the browser does.
// Operates on the raw HTML strings (no DOM) since this runs outside a browser.
//
// Usage: node scripts/extract_words.js [path/to/index.html]
// Prints a JSON array of unique clickable-word strings to stdout.

const fs = require('fs');
const path = process.argv[2] || 'index.html';
const html = fs.readFileSync(path, 'utf8');

const vendoredMatch = html.match(/<script>\s*(function TinySegmenter[\s\S]*?)<\/script>/);
if (!vendoredMatch) throw new Error('TinySegmenter block not found in ' + path);
eval(vendoredMatch[1]);

const stopWordsMatch = html.match(/const PARTICLE_STOP_WORDS = new Set\(\[([\s\S]*?)\]\);/);
if (!stopWordsMatch) throw new Error('PARTICLE_STOP_WORDS not found in ' + path);
const PARTICLE_STOP_WORDS = new Set(eval('[' + stopWordsMatch[1] + ']'));

function isHiraganaOnly(s) { return /^[ぁ-んー]+$/.test(s); }
function isKanaOnly(s) { return /^[ぁ-んァ-ヴーｱ-ﾝﾞ]+$/.test(s); }

const segmenter = new TinySegmenter();

// DOM-free equivalent of the browser's buildOffsetMap: parses one ruby-tagged
// HTML string into its flattened base text (ruby's own text, no <rt>, plus bare
// text) and each <ruby>'s [start,end) offset, in source order.
function buildOffsetMapFromString(str) {
  let text = '';
  const rubies = [];
  const re = /<ruby>([^<]*)<rt>[^<]*<\/rt><\/ruby>/g;
  let last = 0, m;
  while ((m = re.exec(str))) {
    text += str.slice(last, m.index).replace(/<[^>]+>/g, '');
    const start = text.length;
    text += m[1];
    rubies.push({ start, end: text.length });
    last = re.lastIndex;
  }
  text += str.slice(last).replace(/<[^>]+>/g, '');
  return { text, rubies };
}

// Same absorption rule as the browser's resolveSpokenRange.
function resolveSpokenRange(text, rubies, start, end) {
  let tokens;
  try { tokens = segmenter.segment(text); } catch (e) { return [start, end]; }
  let pos = 0;
  const tokOffsets = tokens.map(t => { const o = { text: t, start: pos, end: pos + t.length }; pos += t.length; return o; });
  const nextRubyStart = rubies.reduce((min, r) => (r.start >= end && r.start < min ? r.start : min), text.length);
  const covering = tokOffsets.find(t => t.start <= start && t.end > start);
  let cur = end;
  if (covering && covering.start === start && covering.end > cur) cur = covering.end;
  for (const t of tokOffsets) {
    if (t.start < cur) continue;
    if (t.start !== cur) break;
    if (t.start >= nextRubyStart) break;
    if (!isHiraganaOnly(t.text)) break;
    if (PARTICLE_STOP_WORDS.has(t.text)) break;
    cur = t.end;
  }
  return [start, cur];
}

// Same DOM-adjacency rule as the browser's gluedRubyGroup, applied over offsets.
function gluedGroups(rubies) {
  const groups = [];
  let i = 0;
  while (i < rubies.length) {
    const group = [rubies[i]];
    while (i + 1 < rubies.length && rubies[i + 1].start === group[group.length - 1].end) {
      group.push(rubies[i + 1]); i++;
    }
    groups.push(group);
    i++;
  }
  return groups;
}

function extractFromString(str) {
  const words = new Set();
  const { text, rubies } = buildOffsetMapFromString(str);
  if (!text) return words;

  // Primary translation key is the click-to-pronounce EXPANDED phrase (e.g.
  // "始めましょう", "高くなっていて", "上がり") — that's the word the user actually
  // clicks and hears, so its gloss is what the tooltip should show. Jisho's search
  // lemmatizes inflected forms well (~98% hit on real content), so this reads far
  // more accurately than the bare kanji (e.g. 上 alone → "above, over", but 上がり
  // → "rise, increase"). We ALSO keep each ruby's bare term (高, 上) as a fallback
  // key for the ~2% of phrases Jisho can't lemmatize (続きそう, 同じ日).
  const claimed = [];
  for (const group of gluedGroups(rubies)) {
    const gStart = group[0].start, gEnd = group[group.length - 1].end;
    const [s, e] = resolveSpokenRange(text, rubies, gStart, gEnd);
    claimed.push([s, e]);
    const expanded = text.slice(s, e).trim();
    if (expanded) words.add(expanded);
    for (const r of group) {
      const w = text.slice(r.start, r.end).trim();
      if (w) words.add(w);
    }
  }

  // Pure-kana chunks not already covered by a ruby's claimed range — same rule
  // as the browser's wrapKanaWords.
  const overlapsClaimed = (s, e) => claimed.some(([cs, ce]) => cs < e && ce > s);
  let tokens;
  try { tokens = segmenter.segment(text); } catch (e) { tokens = []; }
  let pos = 0;
  const tokOffsets = tokens.map(t => { const o = { text: t, start: pos, end: pos + t.length }; pos += t.length; return o; });
  let i = 0;
  while (i < tokOffsets.length) {
    const t = tokOffsets[i];
    if (isKanaOnly(t.text) && !PARTICLE_STOP_WORDS.has(t.text) && !overlapsClaimed(t.start, t.end)) {
      let j = i, end = t.end;
      while (j + 1 < tokOffsets.length) {
        const nxt = tokOffsets[j + 1];
        if (nxt.start !== end) break;
        if (!isKanaOnly(nxt.text) || PARTICLE_STOP_WORDS.has(nxt.text)) break;
        if (overlapsClaimed(nxt.start, nxt.end)) break;
        end = nxt.end; j++;
      }
      const w = text.slice(t.start, end).trim();
      if (w) words.add(w);
      i = j + 1;
    } else {
      i++;
    }
  }
  return words;
}

const segStart = html.indexOf('const segments = [');
const segEnd = html.indexOf('\nlet current', segStart);
const segCode = html.slice(segStart, segEnd).replace('const segments', 'global.__segments');

const allWords = new Set();
eval(segCode);
for (const s of global.__segments) {
  (s.narration || []).forEach(str => extractFromString(str).forEach(w => allWords.add(w)));
  (s.reaction || []).forEach(str => extractFromString(str).forEach(w => allWords.add(w)));
  (s.vocab || []).forEach(pair => extractFromString(pair[0]).forEach(w => allWords.add(w)));
  (s.phrases || []).forEach(pair => extractFromString(pair[0]).forEach(w => allWords.add(w)));
}

console.log(JSON.stringify(Array.from(allWords).sort()));
