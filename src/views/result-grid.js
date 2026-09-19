import { View, el } from './view.js';

/** Frames in rank order, for any search or for one whole video. Choosing one emits `open-frame`. */
export class ResultGrid extends View {
  render({ title, frames }) {
    if (!frames.length) return this.message(`${title}: nothing found.`);
    this.draw(
      el('h2', {}, `${title} · ${frames.length}`),
      el('ol', { className: 'grid' }, frames.map((frame) => el('li', {}, this.frameCard(frame)))),
    );
  }
}
