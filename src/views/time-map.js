import { stretchAt, ticks } from '../core/anatomy.js';
import { clock, el } from './view.js';

/**
 * The map of one video's time line: a lane each for its frames, the words read on screen and its
 * speech, drawn to the scale of the whole video, with a band that can be put over one stretch (see
 * `cut`). Only a pointer uses it; whatever it shows is also listed elsewhere, so it is hidden from
 * assistive technology. `onPick(i)` is told which stretch a click lands on (or the next to begin);
 * without it the map is just a picture.
 *
 * @returns {{ element: HTMLElement, mark: (i: number) => void }} `mark(i)` puts the band over stretch `i`
 */
export function timeMap({ stretches, frames, speech, length, onPick = null }) {
  const end = Math.max(length, 1); // a video with nothing past its first second still has a scale
  const { step, times } = ticks(end);
  const left = (time) => `${((time / end) * 100).toFixed(2)}%`;
  const piece = (time, until = time) => {
    const node = el('i');
    Object.assign(node.style, { left: left(time), width: `${(((until - time) / end) * 100).toFixed(2)}%` });
    return node;
  };
  const lanes = [
    ['lane-frames', 'Frames', frames.map((f) => piece(f.time))],
    ['lane-text', 'On screen', stretches.filter((s) => s.kind === 'scene').map((s) => piece(s.from, s.to))],
    ['lane-speech', 'Speech', speech.map((line) => piece(line.time))],
  ];
  const band = el('div', { className: 'band' });
  const tracks = el('div', {
    className: 'tracks',
    title: onPick ? 'Click to jump to that moment' : '',
    onclick: onPick && ((event) => {
      const box = tracks.getBoundingClientRect();
      const time = ((event.clientX - box.left) / box.width) * end;
      onPick(stretchAt(stretches, Math.min(end, Math.max(0, time))));
    }),
  }, lanes.map(([className, , marks]) => el('div', { className: `track ${className}` }, marks)), band);
  tracks.style.setProperty('--tick', `${((step / end) * 100).toFixed(3)}%`);
  const axis = el('div', { className: 'axis' }, times.map((time) => {
    const label = el('span', {}, clock(time));
    label.style.left = left(time);
    return label;
  }));
  let shown = -1;
  return {
    element: el('div', { className: onPick ? 'overview' : 'overview still', ariaHidden: 'true' },
      el('div', { className: 'names' }, lanes.map(([className, name]) => el('span', { className }, name))),
      el('div', { className: 'map' }, tracks, axis)),
    mark(i) {
      const stretch = stretches[i];
      if (!stretch || i === shown) return;
      shown = i;
      Object.assign(band.style, { left: left(stretch.from), width: `${(((stretch.to - stretch.from) / end) * 100).toFixed(2)}%` });
    },
  };
}
