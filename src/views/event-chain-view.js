import { View, el } from './view.js';

/**
 * TRAKE results: the events named once, then whole event chains, each one
 * addable as an answer, then every event's own ranking folded underneath. A
 * folded ranking draws its cards when first opened, so it loads no pictures
 * until someone looks at it.
 */
export class EventChainView extends View {
  render({ names, stages, chains }) {
    this.draw(
      el('h2', {}, `Event chains · ${chains.length}`),
      el('ol', { className: 'events' }, names.map((name) => el('li', {}, name))),
      el('ol', { className: 'chains' }, chains.map((chain) => el('li', {}, this.#chain(chain)))),
      ...stages.map((frames, i) => this.#stage(names[i], frames)),
    );
  }

  #stage(name, frames) {
    const row = el('div', { className: 'row' });
    const details = el('details', {}, el('summary', {}, `${name} · ${frames.length}`), row);
    details.addEventListener('toggle', () => {
      if (details.open && !row.firstChild) row.append(...frames.map((frame) => this.frameCard(frame)));
    });
    return details;
  }

  #chain(chain) {
    return el('div', { className: 'row' },
      chain.map((frame) => this.frameCard(frame)),
      el('button', { className: 'add', onclick: () => this.emit('add-answer', { frames: chain }) }, 'Add chain'));
  }
}
