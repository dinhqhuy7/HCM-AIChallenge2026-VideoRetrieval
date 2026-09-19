import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { StaticDataset } from '../src/providers/static/static-dataset.js';
import { KeywordIndex } from '../src/providers/static/keyword-index.js';
import { QueryCatalog } from '../src/providers/static/query-catalog.js';
import { Query } from '../src/core/models.js';

const site = fileURLToPath(new URL('./fixtures/site/', import.meta.url));
const readJson = async (path) => JSON.parse(await readFile(path, 'utf8'));

test('a frame tuple points at its own image, or at a cell of a sprite strip when tiled', () => {
  const data = new StaticDataset('site/', readJson);
  assert.deepEqual(data.frame(['V', 7, 0.3, null]).image, { url: 'site/img/V/7.webp' });
  assert.deepEqual(data.frame(['V', 7, 0.3, 23]).image, { url: 'site/sprites/V/2.webp', cell: 3 });
});

test('each file is loaded once, and a failed load is retried', async () => {
  let calls = 0;
  const data = new StaticDataset(site, async (path) => {
    calls += 1;
    if (calls === 1) throw new Error('offline');
    return readJson(path);
  });
  await assert.rejects(data.json('data/videos.json'), /offline/);
  await data.json('data/videos.json');
  await data.json('data/videos.json');
  assert.equal(calls, 2);
});

test('videos are looked up by id, and an unknown id is named', async () => {
  const data = new StaticDataset(site, readJson);
  assert.equal((await data.video('L01_V002')).title, 'Cooking show');
  await assert.rejects(data.video('L09_V009'), /unknown video L09_V009/);
});

test('keywords match with or without accents, frames matching more words first', async () => {
  const index = new KeywordIndex(new StaticDataset(site, readJson));
  const keys = async (text) => (await index.search(text)).map((f) => f.key);
  assert.deepEqual(await keys('Bão lũ miền Trung'), ['L01_V001/10', 'L01_V002/10']);
  assert.deepEqual(await keys('lu bao'), ['L01_V001/10', 'L01_V002/10']);
  assert.deepEqual(await keys('banh xeo'), []);
});

test('among frames matching as many words, videos take turns', async () => {
  const files = {
    'data/keywords/index.json': ['lu'],
    'data/keywords/w-lu.json': { lu: [['A', 1, 0, 0], ['A', 2, 0, 1], ['A', 3, 0, 2], ['B', 1, 0, 0]] },
  };
  const index = new KeywordIndex(new StaticDataset('', async (path) => files[path]));
  assert.deepEqual((await index.search('lu')).map((f) => f.key), ['A/1', 'B/1', 'A/2', 'A/3']);
});

test('a word whose file does not exist is never downloaded', async () => {
  const fetched = [];
  const index = new KeywordIndex(new StaticDataset(site, (path) => {
    fetched.push(path.slice(site.length));
    return readJson(path);
  }));
  await index.search('xeo bao');
  assert.deepEqual(fetched.sort(), ['data/keywords/index.json', 'data/keywords/w-bao.json']);
});

test('sample queries split by task, then by round', async () => {
  const rows = await readJson(`${site}data/queries.json`);
  const catalog = new QueryCatalog([...rows, { id: 'r3-p2-1', round: 3, task: 'kis', text: 'x' }].map((row) => new Query(row)));
  assert.deepEqual(catalog.tasks(), [{ task: 'kis', count: 2 }, { task: 'qa', count: 1 }, { task: 'trake', count: 1 }]);
  const labels = (task) => catalog.groups(task).map((g) => `${g.label}: ${g.queries.map((q) => q.id)}`);
  assert.deepEqual(labels('kis'), ['Round 1: r1-p1-1', 'Round 3: r3-p2-1']);
  assert.deepEqual(labels('trake'), ['Round 2: r2-p2-8']);
});
