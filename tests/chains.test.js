import { test } from 'node:test';
import assert from 'node:assert/strict';
import { gapLabel, lay, orderNote, overlapNote } from '../src/core/chains.js';
import { Frame } from '../src/core/models.js';

const frame = (video, idx, time) => new Frame(video, idx, time, { url: `${idx}.webp` });

// The numbers of a recorded query: four events in one video, two chains that differ only in the last event.
const A = 'L30_V031';
const chain1 = [frame(A, 2116, 84.6), frame(A, 2164, 86.5), frame(A, 2421, 96.8), frame(A, 2471, 98.8)];
const chain2 = [chain1[0], chain1[1], chain1[2], frame(A, 2989, 119.5)];
const stages = [
  [frame('X', 1, 5), chain1[0], frame(A, 2303, 92.1)],
  [frame('X', 2, 6), frame('X', 3, 7), frame('X', 4, 8), frame('X', 5, 9), chain1[1]],
  [frame(A, 623, 24.9), chain1[2], frame('X', 6, 7)],
  [frame(A, 2164, 86.5), frame('X', 7, 1), frame('X', 8, 2), frame('X', 9, 3), frame('X', 10, 4), frame('X', 11, 5), frame('X', 12, 6), chain1[3], frame('X', 13, 7), chain2[3]],
];

test('a gap between events reads as seconds, or as a clock when long, with its sign', () => {
  assert.equal(gapLabel(1.24), '+1.2 s');
  assert.equal(gapLabel(38.3), '+38.3 s');
  assert.equal(gapLabel(125), '+2:05');
  assert.equal(gapLabel(-0.5), '−0.5 s');
});

test('chains are grouped by video in order of first appearance, numbered over the whole list', () => {
  const other = [frame('B', 1, 10), frame('B', 2, 20)];
  const groups = lay({ chains: [chain1, other, chain2], stages: [[], []] });
  assert.deepEqual(groups.map((g) => [g.videoId, g.chains.map((c) => c.number)]), [[A, [1, 3]], ['B', [2]]]);
  assert.deepEqual(groups[1].chains[0].gaps, [10]);
  assert.equal(groups[1].chains[0].span, 10);
  assert.deepEqual(groups[0].chains[0].gaps.map((g) => Number(g.toFixed(1))), [1.9, 10.3, 2]);
});

test('an empty chain is left out, and the others keep their numbers', () => {
  const groups = lay({ chains: [[], chain1], stages });
  assert.deepEqual(groups.map((g) => g.chains.map((c) => c.number)), [[2]]);
});

test('an event lists the different frames its chains use, with their rank and which chains use them', () => {
  const [group] = lay({ chains: [chain1, chain2], stages });
  assert.deepEqual(group.events.map((e) => e.frames.length), [1, 1, 1, 2]);
  assert.deepEqual(group.events[0].frames.map((u) => [u.frame.frameIdx, u.rank, u.chains]), [[2116, 2, [1, 2]]]);
  assert.deepEqual(group.events[3].frames.map((u) => [u.frame.frameIdx, u.rank, u.chains]), [[2471, 8, [1]], [2989, 10, [2]]]);
});

test('the best frame of an event on its own is the highest ranked one that lies in this video', () => {
  const [group] = lay({ chains: [chain1, chain2], stages });
  assert.deepEqual(group.events.map((e) => [e.best.frame.frameIdx, e.best.rank]), [[2116, 2], [2164, 5], [623, 1], [2164, 1]]);
  const [lonely] = lay({ chains: [[frame('Z', 1, 3), frame('Z', 2, 4)]], stages: [[], []] });
  assert.deepEqual(lonely.events.map((e) => e.best), [null, null]);
  assert.deepEqual(lonely.events.map((e) => e.frames[0].rank), [0, 0]);
});

test('the window holds every frame shown, with room around, and is never narrower than ten seconds', () => {
  const [group] = lay({ chains: [chain1, chain2], stages });
  assert.ok(group.window.from < 24.9 && group.window.to > 119.5);
  const [near] = lay({ chains: [[frame('Z', 1, 3), frame('Z', 2, 3.5)]], stages: [[], []] });
  assert.equal(near.window.from, 1);
  assert.ok(near.window.to - near.window.from >= 10);
  const [start] = lay({ chains: [[frame('Z', 1, 0.5), frame('Z', 2, 1)]], stages: [[], []] });
  assert.equal(start.window.from, 0);
});

test('when the best frames on their own are out of order, the note says which, and which frames the chain takes instead', () => {
  const [group] = lay({ chains: [chain1, chain2], stages });
  assert.equal(orderNote(group),
    'Taken one at a time, the best frame of E3 in this video (0:24) comes before that of E2 (1:26). '
    + 'A chain has to keep the order, so chain 1 takes the one ranked #2 for E3 (1:36) and the one ranked #8 for E4 (1:38).');
});

test('when they are in order the chain is just them; with nothing known, or a different chain, there is no note', () => {
  const inOrder = [frame('V', 1, 10), frame('V', 2, 20), frame('V', 3, 30)];
  const [fine] = lay({ chains: [inOrder], stages: inOrder.map((f) => [f]) });
  assert.equal(orderNote(fine), 'Taken one at a time, the best frame of each event in this video is already in time order, so chain 1 is made of them.');
  const [unknown] = lay({ chains: [inOrder], stages: [[], [], []] });
  assert.equal(orderNote(unknown), null);
  const [later] = lay({ chains: [inOrder], stages: [[frame('V', 9, 5), inOrder[0]], [inOrder[1]], [inOrder[2]]] });
  assert.equal(orderNote(later), null);
});

test('chains of one video say how much they share', () => {
  const [group] = lay({ chains: [chain1, chain2], stages });
  assert.equal(overlapNote(group), 'E1, E2 and E3 use the same frame in both chains; E4 has 2 different frames.');
  const [single] = lay({ chains: [chain1], stages });
  assert.equal(overlapNote(single), null);
  const third = [frame(A, 5, 50), frame(A, 6, 60), chain1[2], chain1[3]];
  const [three] = lay({ chains: [chain1, chain2, third], stages });
  assert.equal(overlapNote(three), 'E3 uses the same frame in all 3 chains; E1 has 2, E2 has 2 and E4 has 2 different frames.');
  const [same] = lay({ chains: [chain1, chain1], stages });
  assert.equal(overlapNote(same), 'These 2 chains use the same frame for every event.');
  const apart = [frame(A, 7, 1), frame(A, 8, 2), frame(A, 9, 3), frame(A, 10, 4)];
  const [none] = lay({ chains: [chain1, apart], stages });
  assert.equal(overlapNote(none), 'No event keeps the same frame in both chains; E1 has 2, E2 has 2, E3 has 2 and E4 has 2 different frames.');
});
