import { test } from 'node:test';
import assert from 'node:assert/strict';
import { Query } from '../src/core/models.js';
import { DEFAULT_GRID_SIZE, GRID_SIZES, gridSize } from '../src/core/grid-size.js';
import { LocalStore } from '../src/answers/local-store.js';
import { QueryCatalog } from '../src/providers/static/query-catalog.js';

const catalog = new QueryCatalog([
  { id: 'r1-p1-4', round: 1, task: 'kis', text: 'Một đàn sư tử đang nghỉ ngơi trong khu nuôi dưỡng, London Zoo.' },
  { id: 'r1-p1-5', round: 1, task: 'kis', text: 'Đoạn clip bắt đầu bằng việc đậu hà lan được bỏ vào chảo.' },
  { id: 'r3-p2-1', round: 3, task: 'kis', text: 'Cảnh một chiếc xe máy trên đường phố về đêm.' },
  { id: 'r1-p1-9', round: 1, task: 'qa', text: 'Có bao nhiêu con sư tử trong đoạn clip?' },
  { id: 'r2-p2-8', round: 2, task: 'trake', text: 'Bốn cảnh liên tiếp.', stages: ['Cảnh có trái sầu riêng.', 'Cảnh có trái măng cụt.'] },
].map((row) => new Query(row)));

const ids = (task, filter) => catalog.groups(task, filter).flatMap((group) => group.queries.map((query) => query.id));

test('with nothing typed, every query is listed', () => {
  assert.deepEqual(ids('kis', ''), ['r1-p1-4', 'r1-p1-5', 'r3-p2-1']);
  assert.deepEqual(ids('kis', '   '), ['r1-p1-4', 'r1-p1-5', 'r3-p2-1']);
});

test('typed words match without accents, and a half-typed word already finds its query', () => {
  assert.deepEqual(ids('kis', 'su tu'), ['r1-p1-4']);
  assert.deepEqual(ids('kis', 'SƯ TỬ'), ['r1-p1-4']);
  assert.deepEqual(ids('kis', 'dau ha'), ['r1-p1-5']);
  assert.deepEqual(ids('kis', 'london'), ['r1-p1-4']);
});

test('every typed word must be there, and a word must start a word of the query, not sit inside one', () => {
  assert.deepEqual(ids('kis', 'su tu chao'), []);
  assert.deepEqual(ids('kis', 'u tu'), []);
});

test('the id can be typed, and the events of a TRAKE query are searched too', () => {
  assert.deepEqual(ids('kis', 'p1-5'), ['r1-p1-5']);
  assert.deepEqual(ids('kis', 'R3'), ['r3-p2-1']);
  assert.deepEqual(ids('trake', 'sau rieng'), ['r2-p2-8']);
  assert.deepEqual(ids('trake', 'mang cut'), ['r2-p2-8']);
});

test('text with no letters in it is looked for as it is', () => {
  assert.deepEqual(ids('qa', '?'), ['r1-p1-9']);
  assert.deepEqual(ids('kis', '?'), []);
});

test('the task switch shows how many queries each task would list, and keeps a task that has none', () => {
  assert.deepEqual(catalog.tasks(), [{ task: 'kis', count: 3 }, { task: 'qa', count: 1 }, { task: 'trake', count: 1 }]);
  assert.deepEqual(catalog.tasks('su tu'), [{ task: 'kis', count: 1 }, { task: 'qa', count: 1 }, { task: 'trake', count: 0 }]);
});

test('a round with no match is left out of the list', () => {
  assert.deepEqual(catalog.groups('kis', 'xe may').map((group) => group.label), ['Round 3']);
  assert.deepEqual(catalog.groups('kis', 'su tu').map((group) => group.label), ['Round 1']);
});

test('a picture size is one of the three, and anything else is the default', () => {
  assert.deepEqual(Object.keys(GRID_SIZES), ['s', 'm', 'l']);
  for (const size of Object.keys(GRID_SIZES)) assert.equal(gridSize(size), size);
  for (const bad of [null, undefined, '', 'xl', 'toString', 3, {}]) assert.equal(gridSize(bad), DEFAULT_GRID_SIZE);
});

test('a stored size is used, and a corrupt or missing one falls back to the default', () => {
  const memory = (initial) => {
    const data = new Map(initial);
    return { getItem: (key) => data.get(key) ?? null, setItem: (key, value) => data.set(key, value) };
  };
  const stored = (initial) => gridSize(new LocalStore('size', memory(initial)).read(null));
  assert.equal(stored([['size', '"l"']]), 'l');
  assert.equal(stored([['size', '"huge"']]), DEFAULT_GRID_SIZE);
  assert.equal(stored([['size', '{not json']]), DEFAULT_GRID_SIZE);
  assert.equal(stored([]), DEFAULT_GRID_SIZE);
});
