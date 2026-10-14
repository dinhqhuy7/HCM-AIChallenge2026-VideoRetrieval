import { View, el } from './view.js';

/**
 * What the results panel says before anything is asked: the ways a visit can begin. Only the ways the
 * provider offers are listed. Choosing a video emits `look-inside`, as the same offer in the query panel does.
 */
export class StartPanel extends View {
  #catalog;
  #can;
  #videos;
  #guide;

  /** `videos` are `{ id, note }`, as the query panel takes them; `guide` says whether there is a page on how it works. */
  constructor(element, catalog, capabilities, videos = [], guide = false) {
    super(element);
    this.#catalog = catalog;
    this.#can = capabilities;
    this.#videos = videos;
    this.#guide = guide;
  }

  render() {
    const can = this.#can;
    const inside = can.browse && can.transcript && this.#videos.length > 0;
    this.draw(el('section', { className: 'start' },
      el('h2', {}, 'Where to start'),
      el('ul', {},
        this.#catalog && way('Pick a sample query', ' from the list to see the frames the system ranked for it, recorded in advance.'),
        can.keyword && way('Search the words', ' read on screen or heard in speech, in every video.'),
        can.freeText && way('Describe a scene', ' in your own words, as the competition does.'),
        inside && way('Look inside a video', ': see it cut into scenes, with the frames, words on screen and speech of each. ',
          el('span', { className: 'examples' }, this.#videos.map(({ id }) => el('button', {
            type: 'button', className: 'chip', onclick: () => this.emit('look-inside', { videoId: id }),
          }, id)))),
        this.#guide && way('See how it works', ': the steps from videos to answers, each with an example. ',
          el('span', { className: 'examples' }, el('a', { className: 'btn', href: '#how-it-works' }, 'How it works'))))));
  }
}

const way = (name, rest, ...extra) => el('li', {}, el('b', {}, name), rest, ...extra);
