import { LocalStore } from '../answers/local-store.js';
import { GRID_SIZES, gridSize } from '../core/grid-size.js';
import { View, el } from './view.js';

/**
 * Frames for any search or for one whole video. A heading says what is shown (and what the query
 * said), a switch sets how large the pictures are, and choosing a frame emits `open-frame`. While
 * a list takes more than a moment to arrive, grey tiles hold its place. `ranked` lists, those in
 * order of match, number their pictures; a whole video is in time order and does not, and has the
 * switch to its scenes (give its `videoId`).
 */
export class ResultGrid extends View {
  static TILES = 12;
  #store;
  #size;

  constructor(element, store = new LocalStore('system-demo.grid-size')) {
    super(element);
    this.#store = store;
    this.#size = gridSize(store.read(null));
    element.dataset.size = this.#size;
  }

  render({ title, subtitle = '', echo = false, badge = '', frames, ranked = true, empty = 'Nothing found.', videoId = null, focusSwitch = false }) {
    this.draw(
      this.#head({ title, subtitle, echo, badge, count: frames.length, videoId }),
      frames.length
        ? el('ol', { className: 'grid' }, frames.map((frame, i) => el('li', {}, this.frameCard(frame, null, ranked ? i + 1 : null))))
        : el('p', { className: 'message empty' }, empty),
    );
    this.keepSwitchFocus(focusSwitch);
    this.emit('announce', frames.length ? `${title}: ${frames.length} ${frames.length === 1 ? 'frame' : 'frames'}` : `${title}: ${empty}`);
  }

  #head({ title, subtitle, echo, badge, count, videoId }) {
    return el('div', { className: 'head' },
      el('div', { className: 'titles' },
        el('h2', {}, title, badge && el('span', { className: 'badge' }, badge)),
        subtitle && el('p', { className: echo ? 'sub echo' : 'sub' }, subtitle)),
      (count > 0 || videoId) && el('div', { className: 'tools' },
        count > 0 && el('span', { className: 'count' }, `${count} ${count === 1 ? 'frame' : 'frames'}`),
        videoId && this.videoSwitch(videoId, 'frames'),
        count > 0 && this.#sizeSwitch()));
  }

  #sizeSwitch() {
    return el('div', { className: 'sizes', role: 'group', ariaLabel: 'Picture size' },
      Object.entries(GRID_SIZES).map(([size, name]) => el('button', {
        title: name,
        ariaLabel: name,
        ariaPressed: String(size === this.#size),
        className: size === this.#size ? 'selected' : '',
        onclick: (event) => this.#choose(size, event.currentTarget.parentElement),
      }, size.toUpperCase())));
  }

  /** Marks the choice in place, so the pictures already drawn are not loaded again. */
  #choose(size, group) {
    this.#size = size;
    this.element.dataset.size = size;
    this.#store.write(size);
    for (const button of group.children) {
      const chosen = button.textContent.toLowerCase() === size;
      button.classList.toggle('selected', chosen);
      button.setAttribute('aria-pressed', String(chosen));
    }
  }

  skeleton() {
    return el('div', { className: 'skeleton', ariaHidden: 'true' },
      el('div', { className: 'bar wide' }),
      el('div', { className: 'bar' }),
      el('div', { className: 'grid' }, Array.from({ length: ResultGrid.TILES }, () => el('div', { className: 'ghost' }))));
  }
}
