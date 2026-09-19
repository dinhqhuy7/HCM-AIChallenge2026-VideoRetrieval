import { test } from 'node:test';
import assert from 'node:assert/strict';
import { LocalStore } from '../src/answers/local-store.js';
import { AnswerList } from '../src/answers/answer-list.js';
import { CsvExporter } from '../src/answers/csv-exporter.js';
import { Answer, Frame } from '../src/core/models.js';

/** The part of the Storage interface LocalStore uses, backed by a Map. */
class MemoryStorage {
  #items = new Map();
  getItem(key) { return this.#items.get(key) ?? null; }
  setItem(key, value) { this.#items.set(key, value); }
}

test('a stored value reads back, and a missing one gives the fallback', () => {
  const store = new LocalStore('k', new MemoryStorage());
  assert.deepEqual(store.read([]), []);
  store.write({ a: 1 });
  assert.deepEqual(store.read(null), { a: 1 });
});

test('blocked, full or corrupt storage never breaks the page', () => {
  const blocked = { getItem() { throw new Error('denied'); }, setItem() { throw new Error('quota'); } };
  const store = new LocalStore('k', blocked);
  assert.doesNotThrow(() => store.write([1]));
  assert.equal(store.read('fallback'), 'fallback');
  assert.equal(new LocalStore('k', null).read('none'), 'none');
  const corrupt = new MemoryStorage();
  corrupt.setItem('k', '{not json');
  assert.equal(new LocalStore('k', corrupt).read('fallback'), 'fallback');
});

const kis = (idx) => new Answer('kis', [new Frame('V', idx, idx / 25, { url: `${idx}.webp` })]);
const ids = (list, query) => list.of(query).map((a) => a.frames[0].frameIdx);

test('answers are added once each, per query, up to the limit', () => {
  const list = new AnswerList(new LocalStore('k', new MemoryStorage()));
  assert.equal(list.add('q1', kis(1)), true);
  assert.equal(list.add('q1', kis(1)), false);
  assert.equal(list.add('q2', kis(1)), true);
  for (let i = 2; i <= AnswerList.LIMIT; i += 1) list.add('q1', kis(i));
  assert.equal(list.add('q1', kis(999)), false);
  assert.equal(list.of('q1').length, AnswerList.LIMIT);
});

test('answers can be removed and reordered, and every change is announced', () => {
  const list = new AnswerList(new LocalStore('k', new MemoryStorage()));
  const changed = [];
  list.addEventListener('change', (e) => changed.push(e.detail.queryId));
  [1, 2, 3].forEach((i) => list.add('q', kis(i)));
  list.move('q', 2, 0);
  assert.deepEqual(ids(list, 'q'), [3, 1, 2]);
  list.remove('q', 1);
  assert.deepEqual(ids(list, 'q'), [3, 2]);
  assert.equal(changed.length, 5);
});

test('answers survive a reload as real answers', () => {
  const storage = new MemoryStorage();
  new AnswerList(new LocalStore('k', storage)).add('q', new Answer('qa', kis(4).frames, '7'));
  const [answer] = new AnswerList(new LocalStore('k', storage)).of('q');
  assert.deepEqual(answer.cells(), ['V', 4, '7']);
  assert.equal(answer.frames[0].key, 'V/4');
});

test('the csv has one line per answer and quotes only where needed', () => {
  const frames = kis(4).frames;
  const answers = [kis(4), new Answer('qa', frames, '5, "năm"'), new Answer('trake', [...frames, ...kis(9).frames])];
  assert.equal(CsvExporter.text(answers), 'V,4\nV,4,"5, ""năm"""\nV,4,9\n');
  assert.equal(CsvExporter.text([]), '');
});
