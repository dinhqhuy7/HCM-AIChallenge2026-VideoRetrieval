import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { SearchProvider } from '../src/providers/search-provider.js';
import { StaticProvider } from '../src/providers/static/static-provider.js';
import { ProviderFactory } from '../src/providers/provider-factory.js';

const site = fileURLToPath(new URL('./fixtures/site/', import.meta.url));
const readJson = async (path) => JSON.parse(await readFile(path, 'utf8'));

test('the base provider offers nothing and names what is missing', async () => {
  class Bare extends SearchProvider {}
  const bare = new Bare();
  assert.equal((await bare.capabilities()).keyword, false);
  assert.equal(await bare.catalog(), null);
  await assert.rejects(bare.search({}), /Bare does not provide search\(\)/);
});

test('the static provider replays recorded results and per-video lists', async () => {
  const provider = new StaticProvider(site, readJson);
  const keys = (frames) => frames.map((f) => f.key);
  const catalog = await provider.catalog();
  const [kis, trake] = ['kis', 'trake'].map((task) => catalog.groups(task)[0].queries[0]);
  assert.equal((await provider.capabilities()).freeText, false);
  assert.deepEqual(keys(await provider.search(kis)), ['L01_V001/40', 'L01_V002/10']);
  const { stages, chains } = await provider.searchEvents(trake);
  assert.deepEqual(stages.map(keys), [['L01_V003/10'], ['L01_V003/80']]);
  assert.deepEqual(chains.map(keys), [['L01_V003/10', 'L01_V003/80']]);
  const [first, second] = await provider.videoFrames('L01_V001');
  assert.deepEqual(keys(await provider.similar(first)), ['L01_V002/10']);
  assert.deepEqual(await provider.similar(second), []);
  assert.deepEqual((await provider.transcript('L01_V003')).speech, [{ time: 3, text: 'Măng cụt' }]);
});

test('the factory builds the configured provider and names the valid kinds', () => {
  assert.ok(ProviderFactory.create({ provider: 'static', baseUrl: './' }) instanceof StaticProvider);
  assert.throws(() => ProviderFactory.create({ provider: 'ftp' }), /unknown provider "ftp": use static or http/);
});
