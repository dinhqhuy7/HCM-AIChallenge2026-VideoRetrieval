/**
 * One video laid out along its time line, from what the page knows of it: the frames that have a
 * picture, the scenes in which words were read on screen, and the speech. Plain functions over the
 * video's data, so a view only has to draw what they return.
 */

/** Seconds between the labels of a time axis, from fine to coarse. */
const STEPS = [1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600];

/**
 * The labels of a time axis from `from` to `end` seconds: the finest step that needs no more than
 * `most` of them, and the multiples of it that fall on the axis.
 */
export function ticks(end, most = 6, from = 0) {
  const step = STEPS.find((candidate) => (end - from) / candidate <= most) ?? STEPS.at(-1);
  const first = Math.ceil(from / step);
  return { step, times: Array.from({ length: Math.max(0, Math.floor(end / step) - first + 1) }, (_, i) => (first + i) * step) };
}

/**
 * The video as stretches in time order, and its length in seconds as far as anything is recorded.
 * Every scene with words read in it is a stretch of its own (`kind: 'scene'`), holding the frames and
 * speech that fall inside it. What lies between two scenes had no words read, and is a stretch
 * (`kind: 'between'`) only when a frame or a spoken line falls there. A stretch is
 * `{ kind, from, to, text, frames, speech }`; `text` is the scene's words, null between scenes.
 * Scenes must not overlap, as the published files guarantee.
 */
export function cut({ frames, onScreen, speech }) {
  const scenes = [...onScreen].sort((a, b) => a.time - b.time);
  // slot 2k is what lies before scene k, slot 2k + 1 is scene k, the last slot is what lies after the last scene
  const slots = Array.from({ length: 2 * scenes.length + 1 }, () => ({ frames: [], speech: [] }));
  const place = (items, kind) => {
    let k = 0;
    for (const item of [...items].sort((a, b) => a.time - b.time)) {
      while (k < scenes.length && scenes[k].until < item.time) k += 1;
      const inside = k < scenes.length && scenes[k].time <= item.time;
      slots[2 * k + (inside ? 1 : 0)][kind].push(item);
    }
  };
  place(frames, 'frames');
  place(speech, 'speech');

  const end = Math.max(0, ...frames.map((f) => f.time), ...scenes.map((s) => s.until), ...speech.map((l) => l.time));
  const stretches = [];
  slots.forEach((slot, s) => {
    const k = s >> 1;
    if (s % 2 === 1) {
      stretches.push({ kind: 'scene', from: scenes[k].time, to: scenes[k].until, text: scenes[k].text, ...slot });
    } else if (slot.frames.length || slot.speech.length) {
      stretches.push({
        kind: 'between', from: k === 0 ? 0 : scenes[k - 1].until, to: k === scenes.length ? end : scenes[k].time, text: null, ...slot,
      });
    }
  });
  return { stretches, end };
}

/** The index of the stretch to show for `time`: the one that holds it, else the next one to begin, else the last; -1 with none. */
export function stretchAt(stretches, time) {
  if (!stretches.length) return -1;
  const at = stretches.findIndex((stretch) => time <= stretch.to);
  return at < 0 ? stretches.length - 1 : at;
}

/** The index of the stretch whose frames include `frame`, or -1. */
export const stretchHolding = (stretches, frame) => stretches.findIndex((stretch) => stretch.frames.some((f) => f.key === frame.key));
