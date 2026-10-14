import { test } from 'node:test';
import assert from 'node:assert/strict';
import { View } from '../src/views/view.js';

/** Just enough of an element for `View.load`: the busy flag, and what was drawn into it. */
const element = () => ({
  busy: false,
  placed: [],
  setAttribute(name) { if (name === 'aria-busy') this.busy = true; },
  removeAttribute(name) { if (name === 'aria-busy') this.busy = false; },
  replaceChildren(...nodes) { this.placed.push(nodes); },
});

class Probe extends View {
  drawn = [];
  said = [];
  render(model) { this.drawn.push(model); }
  message(text) { this.said.push(text); }
}

class Greyed extends Probe {
  skeleton() { return 'grey'; }
}

const after = (ms, value, fail = false) => new Promise((resolve, reject) => {
  setTimeout(() => (fail ? reject(new Error(value)) : resolve(value)), ms);
});

test('the newest load into an element is the one drawn, whichever view started it and whichever ends first', async () => {
  const shared = element();
  const list = new Probe(shared);
  const video = new Probe(shared);
  const older = list.load(() => after(30, 'frames'));
  const newer = video.load(() => after(5, 'scenes'));
  await Promise.all([older, newer]);
  assert.deepEqual(list.drawn, []);
  assert.deepEqual(video.drawn, ['scenes']);
  assert.equal(shared.busy, false);
});

test('the element stays busy until the newest load ends, not until an older one does', async () => {
  const shared = element();
  const view = new Probe(shared);
  const older = view.load(() => after(5, 'old'));
  const newer = view.load(() => after(40, 'new'));
  await older;
  assert.equal(shared.busy, true);
  await newer;
  assert.equal(shared.busy, false);
  assert.deepEqual(view.drawn, ['new']);
});

test('a failure of a load that is no longer the newest says nothing; the newest one says so in plain words, and the reason goes to the console', async () => {
  const shared = element();
  const view = new Probe(shared);
  const logged = [];
  const original = console.error;
  console.error = (...what) => logged.push(what);
  try {
    await Promise.all([view.load(() => after(20, 'gone', true)), view.load(() => after(2, 'fine'))]);
    assert.deepEqual(view.said, []);
    assert.deepEqual(view.drawn, ['fine']);
    await view.load(() => after(1, 'no network', true));
  } finally {
    console.error = original;
  }
  assert.deepEqual(view.said, ['Could not load this. Check your connection and try again.']);
  assert.ok(!view.said[0].includes('no network'));
  assert.ok(logged.some(([error]) => error.message === 'no network'));
});

test('grey tiles appear only when the work is slow, and never over a newer list', async () => {
  const original = View.SKELETON_AFTER_MS;
  View.SKELETON_AFTER_MS = 10;
  try {
    const quick = element();
    await new Greyed(quick).load(() => after(1, 'x'));
    assert.deepEqual(quick.placed, []);

    const slow = element();
    await new Greyed(slow).load(() => after(40, 'x'));
    assert.deepEqual(slow.placed, [['grey']]);

    const shared = element();
    const older = new Greyed(shared);
    await Promise.all([older.load(() => after(40, 'old')), new Probe(shared).load(() => after(1, 'new'))]);
    assert.deepEqual(shared.placed, []);
  } finally {
    View.SKELETON_AFTER_MS = original;
  }
});
