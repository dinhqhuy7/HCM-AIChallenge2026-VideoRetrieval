import { test } from 'node:test';
import assert from 'node:assert/strict';
import { rrf } from '../src/core/fusion.js';
import { MAIN } from '../src/core/main-output.js';
import { pageOf } from '../src/core/page.js';
import { evenly } from '../src/core/transcript.js';
import { Query } from '../src/core/models.js';
import { QueryCatalog } from '../src/providers/static/query-catalog.js';

test('a shot is scored by the ranks it has in the lanes that returned it, and a lane that did not adds nothing', () => {
  assert.equal(rrf(60, [1]), 1 / 61);
  assert.equal(rrf(60, [5, 1]), 1 / 65 + 1 / 61);
  assert.equal(rrf(60, [3, null]), 1 / 63);
  assert.equal(rrf(60, []), 0);
});

test('the guide\'s example: fifth in the visual box and first in the OCR box beats first in the visual box alone', () => {
  const { k, visual, ocr } = MAIN.fusion;
  const card = rrf(k, [visual.card, ocr.card]);
  assert.ok(visual.others.every((rank) => rank < visual.card && rrf(k, [rank, null]) < card));
  assert.equal(card.toFixed(4), '0.0318');
  assert.equal(rrf(k, [1, null]).toFixed(4), '0.0164');
});

test('the address names the page: only the guide\'s own hash opens the guide', () => {
  assert.equal(pageOf('#how-it-works'), 'how');
  for (const hash of ['', '#', '#results', '#how-it-works-2', '#How-it-works']) assert.equal(pageOf(hash), 'search', hash);
});

test('a few items are picked evenly from first to last, and a short list is kept whole', () => {
  const frames = Array.from({ length: 18 }, (_, i) => i);
  assert.deepEqual(evenly(frames, 6), [0, 3, 7, 10, 14, 17]);
  assert.deepEqual(evenly([1, 2, 3], 6), [1, 2, 3]);
  assert.deepEqual(evenly([], 6), []);
  assert.deepEqual(evenly([7, 8, 9, 10], 2), [7, 10]);
});

test('a sample query is found by its id', () => {
  const catalog = new QueryCatalog([
    new Query({ id: 'a', round: 1, task: 'kis', text: 'one' }),
    new Query({ id: 'b', round: 2, task: 'trake', text: 'two', stages: ['x', 'y'] }),
  ]);
  assert.equal(catalog.find('b').task, 'trake');
  assert.equal(catalog.find('zzz'), null);
});
