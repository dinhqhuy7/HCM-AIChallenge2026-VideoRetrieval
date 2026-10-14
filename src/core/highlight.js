import { VietnameseText } from './vietnamese-text.js';

/**
 * `text` cut into pieces, each marked `hit` when it is a word of `query`. Words are compared the way
 * the keyword search compares them (lower case, no accents), so "bao lu" marks "Bão lũ"; the text
 * itself is returned as it was written, accents and all.
 */
export function highlight(text, query) {
  const wanted = new Set(VietnameseText.words(query));
  const chars = [...text.normalize('NFC')];
  if (!wanted.size) return [{ text: chars.join(''), hit: false }];
  // What each character becomes once folded: one letter, or nothing for an accent left on its own.
  const folded = chars.map((char) => VietnameseText.fold(char));
  const isLetter = (value) => /^[a-z0-9]+$/.test(value);

  const pieces = [];
  let plain = 0;
  let at = 0;
  while (at < chars.length) {
    if (!isLetter(folded[at])) {
      at += 1;
      continue;
    }
    let end = at;
    let word = '';
    while (end < chars.length && (isLetter(folded[end]) || folded[end] === '')) word += folded[end++];
    if (wanted.has(word)) {
      if (at > plain) pieces.push({ text: chars.slice(plain, at).join(''), hit: false });
      pieces.push({ text: chars.slice(at, end).join(''), hit: true });
      plain = end;
    }
    at = end;
  }
  if (plain < chars.length) pieces.push({ text: chars.slice(plain).join(''), hit: false });
  return pieces;
}
