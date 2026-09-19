import { test } from 'node:test';
import assert from 'node:assert/strict';
import { ApiClient } from '../src/providers/http/api-client.js';
import { HttpProvider } from '../src/providers/http/http-provider.js';

/** A fake backend: records each request and answers from `routes` ("GET /path" -> [status, body]). */
function fakeFetch(routes) {
  const seen = [];
  const fetchFn = async (url, init) => {
    const route = `${init.method} ${url.pathname}${url.search}`;
    seen.push({ route, body: init.body && JSON.parse(init.body) });
    const [status, body] = routes[route] ?? [404, {}];
    return { ok: status < 400, status, json: async () => body };
  };
  return { fetchFn, seen };
}

test('requests resolve against the base URL and send JSON', async () => {
  const { fetchFn, seen } = fakeFetch({ 'POST /api/search': [200, { frames: [] }] });
  const api = new ApiClient('http://host/api/', fetchFn);
  assert.deepEqual(await api.post('search', { text: 'x' }), { frames: [] });
  assert.deepEqual(seen, [{ route: 'POST /api/search', body: { text: 'x' } }]);
});

test('an optional endpoint may be missing, any other failure is reported', async () => {
  const api = new ApiClient('http://host/', fakeFetch({ 'GET /boom': [500, {}] }).fetchFn);
  assert.equal(await api.get('queries', { optional: true }), null);
  await assert.rejects(api.get('queries'), /GET \/queries: HTTP 404/);
  await assert.rejects(api.get('boom'), /GET \/boom: HTTP 500/);
});

test('the http provider maps each method to its endpoint', async () => {
  const shot = { video: 'V1', frame: 7, time: 0.3, image: 'http://img/V1/7.jpg' };
  const { fetchFn, seen } = fakeFetch({
    'GET /capabilities': [200, { freeText: true }],
    'POST /search': [200, { frames: [shot] }],
    'POST /events': [200, { stages: [[shot]], chains: [[shot, shot]] }],
    'GET /keyword?q=b%C3%A3o%20l%C5%A9': [200, { frames: [] }],
    'GET /frames/V1/7/similar': [200, { frames: [shot] }],
    'GET /videos/V1': [200, { title: 'News', youtube: 'y', embed: true }],
    'GET /videos/V1/frames': [200, { frames: [shot] }],
    'GET /videos/V1/transcript': [200, { onScreen: [], speech: [] }],
  });
  const provider = new HttpProvider('http://host/', fetchFn);
  assert.equal((await provider.capabilities()).freeText, true);
  assert.equal(await provider.catalog(), null);
  const [frame] = await provider.search({ task: 'kis', text: 'a dog' });
  assert.deepEqual({ ...frame }, { videoId: 'V1', frameIdx: 7, time: 0.3, image: { url: shot.image } });
  assert.equal((await provider.searchEvents({ text: 't', stages: ['a', 'b'] })).chains[0].length, 2);
  assert.deepEqual(await provider.searchKeyword('bão lũ'), []);
  assert.equal((await provider.similar(frame))[0].key, 'V1/7');
  assert.equal((await provider.video('V1')).title, 'News');
  assert.equal((await provider.videoFrames('V1')).length, 1);
  assert.deepEqual(await provider.transcript('V1'), { onScreen: [], speech: [] });
  assert.deepEqual(seen.filter((r) => r.body).map((r) => r.body),
    [{ task: 'kis', text: 'a dog' }, { text: 't', stages: ['a', 'b'] }]);
});
