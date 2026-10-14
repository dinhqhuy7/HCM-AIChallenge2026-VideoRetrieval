/**
 * What a video's files say around one moment: the scene whose words were read on screen, the lines
 * heard nearby, and the frame closest to a given second. Plain functions over the file's data, so a
 * view only has to draw the answers.
 */

/** The entry of `onScreen` ({ time, until, text }) that holds `time`, or null. */
export const sceneAt = (onScreen, time) => onScreen.find((scene) => scene.time <= time && time <= scene.until) ?? null;

/** A scene's words as the separate lines the reader found, in the order it found them. */
export const ocrLines = (text) => text.split(' · ').map((line) => line.trim()).filter(Boolean);

/** The speech lines ({ time, text }) within `seconds` of `time`. */
export const speechAround = (speech, time, seconds) => speech.filter((line) => Math.abs(line.time - time) <= seconds);

/** The frame whose time is closest to `time`; the earlier one when two are equally close. */
export function nearestFrame(frames, time) {
  let best = null;
  for (const frame of frames) {
    if (best === null || Math.abs(frame.time - time) < Math.abs(best.time - time)) best = frame;
  }
  return best;
}

/** `count` of the `items`, evenly spread from the first to the last (all of them when there are no more than `count`). */
export function evenly(items, count) {
  if (items.length <= count) return [...items];
  return Array.from({ length: count }, (_, i) => items[Math.round((i * (items.length - 1)) / (count - 1))]);
}

/** The frames within `radius` places of `frame` in `frames` (itself included); empty if it is not among them. */
export function around(frames, frame, radius) {
  const at = frames.findIndex((candidate) => candidate.key === frame.key);
  return at < 0 ? [] : frames.slice(Math.max(0, at - radius), at + radius + 1);
}
