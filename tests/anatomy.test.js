import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { cut, stretchAt, stretchHolding, ticks } from '../src/core/anatomy.js';
import { span } from '../src/core/clock.js';
import { Frame } from '../src/core/models.js';
import { StaticProvider } from '../src/providers/static/static-provider.js';

const frame = (idx, time) => new Frame('V', idx, time, { url: `${idx}.webp` });
const line = (time, text = 'x') => ({ time, text });
const scene = (time, until, text = 'words') => ({ time, until, text });

test('a range is two clock times, or one when they read the same', () => {
  assert.equal(span(11.7, 13.2), '0:11–0:13');
  assert.equal(span(7.1, 7.1), '0:07');
  assert.equal(span(12.1, 12.9), '0:12');
  assert.equal(span(59.5, 61), '0:59–1:01');
});

test('an axis has the finest step that needs at most six labels', () => {
  assert.deepEqual(ticks(65), { step: 15, times: [0, 15, 30, 45, 60] });
  assert.deepEqual(ticks(36.5), { step: 10, times: [0, 10, 20, 30] });
  assert.deepEqual(ticks(5), { step: 1, times: [0, 1, 2, 3, 4, 5] });
  assert.deepEqual(ticks(2734.5).times, [0, 600, 1200, 1800, 2400]);
  assert.equal(ticks(100000).step, 3600);
  assert.deepEqual(ticks(0), { step: 1, times: [0] });
});

test('an axis that starts late has the labels that fall on it', () => {
  assert.deepEqual(ticks(203.3, 5, 151), { step: 15, times: [165, 180, 195] });
  assert.deepEqual(ticks(127.1, 5, 17.3), { step: 30, times: [30, 60, 90, 120] });
  assert.deepEqual(ticks(12, 5, 11.5), { step: 1, times: [12] });
});

test('every scene is a stretch, and frames and speech go to the scene that holds them, its ends included', () => {
  const frames = [frame(1, 1), frame(2, 4), frame(3, 4.5), frame(4, 10)];
  const { stretches, end } = cut({
    frames, onScreen: [scene(1, 2), scene(4, 5)], speech: [line(1.5), line(4), line(5)],
  });
  const scenes = stretches.filter((s) => s.kind === 'scene');
  assert.deepEqual(scenes.map((s) => [s.from, s.to]), [[1, 2], [4, 5]]);
  assert.deepEqual(scenes.map((s) => s.frames.map((f) => f.frameIdx)), [[1], [2, 3]]);
  assert.deepEqual(scenes.map((s) => s.speech.map((l) => l.time)), [[1.5], [4, 5]]);
  assert.equal(scenes[0].text, 'words');
  assert.equal(end, 10);
});

test('what lies between scenes is a stretch only when a frame or a line falls there, and it reaches the scenes next to it', () => {
  const { stretches } = cut({
    frames: [frame(1, 0.5), frame(2, 8), frame(3, 20)],
    onScreen: [scene(1, 2), scene(3, 4), scene(10, 12)],
    speech: [line(2.5), line(15)],
  });
  assert.deepEqual(stretches.map((s) => [s.kind, s.from, s.to]), [
    ['between', 0, 1], // the frame before the first scene
    ['scene', 1, 2],
    ['between', 2, 3], // the line between the first two
    ['scene', 3, 4],
    ['between', 4, 10], // the frame at 8, between the last two
    ['scene', 10, 12],
    ['between', 12, 20], // the line at 15 and the frame at 20, after the last
  ]);
  assert.equal(stretches[0].text, null);
  assert.deepEqual(stretches[6].frames.map((f) => f.frameIdx), [3]);
  assert.deepEqual(stretches[6].speech.map((l) => l.time), [15]);
});

test('a gap holding nothing is left out, and the stretches come in time order whatever the order of the input', () => {
  const { stretches } = cut({
    frames: [frame(2, 6), frame(1, 1.5)],
    onScreen: [scene(5, 7), scene(1, 2)],
    speech: [line(6.5), line(1.2)],
  });
  assert.deepEqual(stretches.map((s) => [s.kind, s.from]), [['scene', 1], ['scene', 5]]);
  assert.deepEqual(stretches[0].frames.map((f) => f.frameIdx), [1]);
  assert.deepEqual(stretches[1].speech.map((l) => l.time), [6.5]);
});

test('a video with no scene is one stretch of what there is, and one with nothing has none', () => {
  const only = cut({ frames: [frame(1, 2), frame(2, 9)], onScreen: [], speech: [line(5)] });
  assert.deepEqual(only.stretches.map((s) => [s.kind, s.from, s.to, s.frames.length, s.speech.length]), [['between', 0, 9, 2, 1]]);
  assert.deepEqual(cut({ frames: [], onScreen: [], speech: [] }), { stretches: [], end: 0 });
});

test('a moment is looked up as the stretch that holds it, else the next to begin, else the last', () => {
  const { stretches } = cut({ frames: [frame(1, 1)], onScreen: [scene(1, 2), scene(10, 12)], speech: [] });
  assert.equal(stretchAt(stretches, 1.5), 0);
  assert.equal(stretchAt(stretches, 5), 1);
  assert.equal(stretchAt(stretches, 0), 0);
  assert.equal(stretchAt(stretches, 99), 1);
  assert.equal(stretchAt([], 3), -1);
});

test('a frame is found in the stretch that holds it, by its key', () => {
  const frames = [frame(1, 1), frame(2, 11)];
  const { stretches } = cut({ frames, onScreen: [scene(1, 2), scene(10, 12)], speech: [] });
  assert.equal(stretchHolding(stretches, frame(2, 11)), 1);
  assert.equal(stretchHolding(stretches, frame(9, 50)), -1);
});

test('a recorded video is cut so that no frame and no line is lost or counted twice', async () => {
  const site = fileURLToPath(new URL('./fixtures/site/', import.meta.url));
  const provider = new StaticProvider(site, async (path) => JSON.parse(await readFile(path, 'utf8')));
  for (const id of ['L01_V001', 'L01_V002', 'L01_V003']) {
    const frames = await provider.videoFrames(id);
    const transcript = await provider.transcript(id);
    const { stretches } = cut({ frames, ...transcript });
    assert.deepEqual(stretches.flatMap((s) => s.frames.map((f) => f.key)).sort(), frames.map((f) => f.key).sort(), id);
    assert.equal(stretches.reduce((sum, s) => sum + s.speech.length, 0), transcript.speech.length, id);
    assert.equal(stretches.filter((s) => s.kind === 'scene').length, transcript.onScreen.length, id);
  }
});
