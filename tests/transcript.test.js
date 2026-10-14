import { test } from 'node:test';
import assert from 'node:assert/strict';
import { Answer, Frame } from '../src/core/models.js';
import { AnswerList } from '../src/answers/answer-list.js';
import { LocalStore } from '../src/answers/local-store.js';
import { clock } from '../src/core/clock.js';
import { highlight } from '../src/core/highlight.js';
import { around, nearestFrame, ocrLines, sceneAt, speechAround } from '../src/core/transcript.js';

const frame = (idx, time) => new Frame('V', idx, time, { url: `${idx}.webp` });
const frames = [frame(1, 0.5), frame(2, 3), frame(3, 4), frame(4, 9.5), frame(5, 20)];

test('the clock shows minutes and zero-padded seconds, from the whole second', () => {
  assert.equal(clock(0), '0:00');
  assert.equal(clock(83.9), '1:23');
  assert.equal(clock(3600), '60:00');
});

test('the scene of a moment is the one whose first and last frame hold it, both included', () => {
  const scenes = [{ time: 0.1, until: 2.5, text: 'a' }, { time: 5.1, until: 6.3, text: 'b' }];
  assert.equal(sceneAt(scenes, 0.1).text, 'a');
  assert.equal(sceneAt(scenes, 6.3).text, 'b');
  assert.equal(sceneAt(scenes, 3), null);
  assert.equal(sceneAt([], 3), null);
});

test('a scene is split into the lines the reader found, and empty pieces are dropped', () => {
  assert.deepEqual(ocrLines('Herbalife · thương hiu ·  · quán ly'), ['Herbalife', 'thương hiu', 'quán ly']);
  assert.deepEqual(ocrLines('one line only'), ['one line only']);
  assert.deepEqual(ocrLines(''), []);
});

test('speech nearby is what lies within the window on either side, edges included', () => {
  const speech = [{ time: 1, text: 'a' }, { time: 10, text: 'b' }, { time: 20, text: 'c' }, { time: 31, text: 'd' }];
  assert.deepEqual(speechAround(speech, 20, 10).map((line) => line.text), ['b', 'c']);
  assert.deepEqual(speechAround(speech, 100, 10), []);
});

test('the nearest frame is by time, the earlier one on a tie, and none when there are no frames', () => {
  assert.equal(nearestFrame(frames, 3.4).frameIdx, 2);
  assert.equal(nearestFrame(frames, 3.6).frameIdx, 3);
  assert.equal(nearestFrame(frames, 6.75).frameIdx, 3);
  assert.equal(nearestFrame(frames, 100).frameIdx, 5);
  assert.equal(nearestFrame([], 5), null);
});

test('the frames around one are its neighbours, cut at the ends of the video', () => {
  assert.deepEqual(around(frames, frames[2], 1).map((f) => f.frameIdx), [2, 3, 4]);
  assert.deepEqual(around(frames, frames[0], 2).map((f) => f.frameIdx), [1, 2, 3]);
  assert.deepEqual(around(frames, frames[4], 9).map((f) => f.frameIdx), [1, 2, 3, 4, 5]);
  assert.deepEqual(around(frames, frame(99, 1), 2), []);
});

const joined = (pieces) => pieces.map((piece) => (piece.hit ? `[${piece.text}]` : piece.text)).join('');

test('the words of a query are marked in the text as written, whatever the accents', () => {
  assert.equal(joined(highlight('Bão lũ ở miền Trung', 'bao lu')), '[Bão] [lũ] ở miền Trung');
  assert.equal(joined(highlight('bao lu', 'BÃO LŨ')), '[bao] [lu]');
  assert.equal(joined(highlight('Đường đi Đà Nẵng', 'duong da')), '[Đường] đi [Đà] Nẵng');
});

test('only whole words are marked, never a piece of one', () => {
  assert.equal(joined(highlight('tuoitre tv.tuoitre.vn', 'tuoitre')), '[tuoitre] tv.[tuoitre].vn');
  assert.equal(joined(highlight('bao baove', 'bao')), '[bao] baove');
});

test('text that is not decomposed the same way is marked all the same, and no letter is lost', () => {
  const decomposed = 'Bão lũ'; // "Bão lũ" with the accents as separate marks
  const pieces = highlight(decomposed, 'bao');
  assert.equal(pieces.map((piece) => piece.text).join(''), 'Bão lũ');
  assert.deepEqual(pieces.filter((piece) => piece.hit).map((piece) => piece.text), ['Bão']);
});

test('with no words in the query, or none in the text, the text comes back whole', () => {
  assert.deepEqual(highlight('Bão lũ', ''), [{ text: 'Bão lũ', hit: false }]);
  assert.deepEqual(highlight('Bão lũ', '?!'), [{ text: 'Bão lũ', hit: false }]);
  assert.deepEqual(highlight('Bão lũ', 'xyz'), [{ text: 'Bão lũ', hit: false }]);
  assert.deepEqual(highlight('', 'bao'), []);
});

test('an answer tells, for a list, which video and which moment, chain or reply it holds', () => {
  const [a, b] = [frame(5, 83.4), frame(9, 90)];
  assert.deepEqual(new Answer('kis', [a]).summary(), { video: 'V', detail: 'frame 5 · 1:23' });
  assert.deepEqual(new Answer('qa', [a], 'năm').summary(), { video: 'V', detail: 'frame 5 · 1:23 · “năm”' });
  assert.deepEqual(new Answer('trake', [a, b]).summary(), { video: 'V', detail: '2 frames: 5, 9' });
});

test('a query\'s answers can all be cleared at once, which is announced like any change', () => {
  const memory = new Map();
  const store = new LocalStore('k', { getItem: (key) => memory.get(key) ?? null, setItem: (key, value) => memory.set(key, value) });
  const list = new AnswerList(store);
  const changes = [];
  list.addEventListener('change', (event) => changes.push(event.detail.queryId));
  list.add('q', new Answer('kis', [frame(1, 1)]));
  list.add('other', new Answer('kis', [frame(2, 2)]));
  list.clear('q');
  assert.equal(list.of('q').length, 0);
  assert.equal(list.of('other').length, 1);
  assert.deepEqual(changes, ['q', 'other', 'q']);
  assert.equal(new AnswerList(store).of('q').length, 0);
});
