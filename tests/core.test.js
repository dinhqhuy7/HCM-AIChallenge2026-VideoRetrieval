import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { VietnameseText } from '../src/core/vietnamese-text.js';
import { Answer, Capabilities, Frame, Video } from '../src/core/models.js';

const cases = JSON.parse(readFileSync(new URL('./fixtures/normalize.json', import.meta.url)));
const frame = (idx) => new Frame('L21_V001', idx, idx / 25, { url: 'x.webp' });

test('words match the build-side index for every shared case', () => {
  for (const { text, words } of cases) assert.deepEqual(VietnameseText.words(text), words, text);
});

test('a frame is keyed by video and frame index', () => {
  assert.equal(frame(120).key, 'L21_V001/120');
});

test('video links start at the whole second', () => {
  const video = new Video('L21_V001', { title: 't', youtube: 'abc', embed: true });
  assert.equal(video.watchUrl(12.9), 'https://www.youtube.com/watch?v=abc&t=12s');
  assert.equal(video.embedUrl(12.9), 'https://www.youtube.com/embed/abc?start=12&autoplay=1');
});

test('answers follow the submission format of each task', () => {
  assert.deepEqual(new Answer('kis', [frame(5)]).cells(), ['L21_V001', 5]);
  assert.deepEqual(new Answer('qa', [frame(5)], '7').cells(), ['L21_V001', 5, '7']);
  assert.deepEqual(new Answer('trake', [frame(5), frame(9)]).cells(), ['L21_V001', 5, 9]);
});

test('capabilities default to off', () => {
  assert.deepEqual({ ...new Capabilities({ keyword: true }) },
    { freeText: false, keyword: true, similar: false, events: false, browse: false, transcript: false });
});
