import { cut, stretchHolding } from '../core/anatomy.js';
import { nearestFrame, ocrLines } from '../core/transcript.js';
import { timeMap } from './time-map.js';
import { View, clock, el, span } from './view.js';

/**
 * One video taken apart along its time line. Above, a map of where its frames, the words read on
 * screen and its speech fall; below, the video cut into stretches in time order (see `cut`), each
 * with its frames, words and speech. The map follows the scrolling and answers a click by taking
 * you to that moment. Frames and speech lines emit `open-frame`; the switch asks for the plain
 * grid of every frame instead (`browse-frames`).
 */
export class VideoAnatomy extends View {
  static FIRST = { frames: 8, lines: 8, speech: 4 };
  static CHUNK = { frames: 16, lines: 40, speech: 20 };
  #provider;
  #docs;
  #unfollow = null;

  constructor(element, provider, docsUrl = null) {
    super(element);
    this.#provider = provider;
    this.#docs = docsUrl;
  }

  /** Lays out `videoId`. `frame`, when there is one, is scrolled to and marked; `focusSwitch` keeps the keyboard on the switch. */
  open(videoId, { frame = null, focusSwitch = false } = {}) {
    return this.load(async () => {
      const [frames, transcript, video] = await Promise.all([
        this.#provider.videoFrames(videoId),
        this.#provider.transcript(videoId),
        Promise.resolve().then(() => this.#provider.video(videoId)).catch(() => null),
      ]);
      return { videoId, frames, transcript, video, frame, focusSwitch };
    });
  }

  skeleton() {
    return el('div', { className: 'skeleton', ariaHidden: 'true' },
      el('div', { className: 'bar wide' }),
      el('div', { className: 'bar' }),
      el('div', { className: 'ghost block' }),
      ...Array.from({ length: 3 }, () => el('div', { className: 'ghost row' })));
  }

  render({ videoId, frames, transcript, video, frame, focusSwitch }) {
    this.#unfollow?.();
    const { stretches, end } = cut({ frames, ...transcript });
    const scenes = stretches.filter((stretch) => stretch.kind === 'scene').length;
    const list = el('ol', { className: 'stretches', ariaLabel: `Parts of ${videoId}, in time order` },
      stretches.map((stretch, i) => this.#stretch(stretch, i, frames, frame)));
    const map = stretches.length
      ? timeMap({ stretches, frames, speech: transcript.speech, length: end, onPick: (i) => this.#jump(list, i) })
      : null;
    this.draw(
      this.#head(videoId, video),
      el('dl', { className: 'stats' },
        stat(frames.length, 'frame', 'frames'),
        stat(scenes, 'scene with text', 'scenes with text'),
        stat(transcript.speech.length, 'speech line', 'speech lines')),
      this.#source(),
      map?.element,
      stretches.length ? list : el('p', { className: 'message empty' }, 'Nothing is recorded for this video.'),
    );
    if (map) this.#follow(list, map);
    const at = frame ? stretchHolding(stretches, frame) : -1;
    if (at >= 0) list.children[at].scrollIntoView({ block: 'start' });
    this.keepSwitchFocus(focusSwitch);
    this.emit('announce', `${videoId}: ${count(scenes, 'scene')} with text, ${count(frames.length, 'frame')}, ${count(transcript.speech.length, 'speech line')}.`);
  }

  #head(videoId, video) {
    return el('div', { className: 'head' },
      el('div', { className: 'titles' },
        el('h2', {}, videoId),
        el('p', { className: 'sub' }, video?.title ?? 'The scenes of one video, with the frames, words and speech of each.')),
      el('div', { className: 'tools' }, this.videoSwitch(videoId, 'scenes')));
  }

  /** Where the layers come from, with a way to the guides that build them. */
  #source() {
    const guide = (file, label) => (this.#docs
      ? el('a', { href: `${this.#docs}offline/${file}`, target: '_blank', rel: 'noopener' }, label)
      : label);
    return el('p', { className: 'source' },
      'Recorded in advance from the competition system. This repository’s main branch builds the same layers: ',
      guide('01-shots-and-keyframes.md', 'shots and keyframes'), ', ',
      guide('03-ocr.md', 'text on screen'), ' and ',
      guide('04-asr.md', 'speech'), '.');
  }

  /**
   * The band follows the stretch at a line just under the map, which is where a jump brings its
   * stretch to, and what the pointer or the keyboard is on.
   */
  #follow(list, map) {
    let reading = 0;
    const index = (target) => {
      const item = target.closest?.('.stretch');
      return item ? Number(item.dataset.i) : -1;
    };
    const on = (event) => { const i = index(event.target); if (i >= 0) map.mark(i); };
    const off = () => map.mark(reading);
    list.addEventListener('pointerover', on);
    list.addEventListener('focusin', on);
    list.addEventListener('pointerleave', off);
    list.addEventListener('focusout', off);

    // where a jump puts a stretch, plus a little: a stretch beginning above this line is the one being read
    const line = () => parseFloat(getComputedStyle(document.documentElement).scrollPaddingTop)
      + parseFloat(getComputedStyle(list.firstElementChild).scrollMarginTop) + 24;
    /** The last stretch that begins at or above the line, by halving. */
    const find = () => {
      const y = line();
      let low = 0;
      let high = list.children.length - 1;
      while (low < high) {
        const middle = Math.ceil((low + high) / 2);
        if (list.children[middle].getBoundingClientRect().top <= y) low = middle;
        else high = middle - 1;
      }
      return low;
    };
    const onScroll = () => {
      if (!list.isConnected) {
        this.#unfollow?.();
        return;
      }
      reading = find();
      map.mark(reading);
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    this.#unfollow = () => { window.removeEventListener('scroll', onScroll); this.#unfollow = null; };
    reading = find();
    map.mark(reading);
  }

  #jump(list, i) {
    const item = list.children[i];
    if (!item) return;
    item.scrollIntoView({ block: 'start' });
    item.classList.remove('flash');
    void item.offsetWidth;
    item.classList.add('flash');
    setTimeout(() => item.classList.remove('flash'), 1600);
  }

  #stretch(stretch, i, frames, current) {
    const { kind, from, to, text } = stretch;
    const tally = [stretch.frames.length > 0 && count(stretch.frames.length, 'frame'), stretch.speech.length > 0 && count(stretch.speech.length, 'speech line')]
      .filter(Boolean).join(' · ');
    const item = el('li', { className: `stretch ${kind}` },
      el('div', { className: 'stretch-head' },
        el('h3', {}, el('span', { className: 'when' }, span(from, to)), el('span', { className: 'kind' }, text ? 'Text on screen' : 'No text read on screen')),
        tally && el('span', { className: 'tally' }, tally)),
      el('div', { className: 'stretch-body' },
        stretch.frames.length > 0 && this.#pictures(stretch.frames, current),
        (text || stretch.speech.length > 0) && el('div', { className: 'evidence' },
          text && this.#words(text),
          stretch.speech.length > 0 && this.#heard(stretch.speech, frames))));
    item.dataset.i = i;
    return item;
  }

  /** The stretch's frames. The one the visit came from is always among those drawn, and marked. */
  #pictures(frames, current) {
    const at = current ? frames.findIndex((f) => f.key === current.key) : -1;
    const box = el('div', { className: 'frames' });
    const more = reveal(box, frames.length, Math.max(VideoAnatomy.FIRST.frames, at + 1), VideoAnatomy.CHUNK.frames, 'pictures', (i) => {
      const card = this.frameCard(frames[i], clock(frames[i].time));
      if (i === at) {
        card.classList.add('current');
        card.setAttribute('aria-current', 'true');
      }
      return card;
    });
    return el('div', { className: 'pictures' }, box, more);
  }

  #words(text) {
    const lines = ocrLines(text);
    const list = el('ul', { className: 'lines' });
    const more = reveal(list, lines.length, VideoAnatomy.FIRST.lines, VideoAnatomy.CHUNK.lines, 'lines', (i) => el('li', {}, lines[i]));
    return el('section', { className: 'ev on-screen' }, el('h4', {}, 'On screen'), list, more);
  }

  #heard(lines, frames) {
    const list = el('ol', { className: 'speech' });
    const more = reveal(list, lines.length, VideoAnatomy.FIRST.speech, VideoAnatomy.CHUNK.speech, 'lines', (i) => el('li', {}, el('button', {
      className: 'line',
      title: 'Open the nearest frame',
      onclick: () => {
        const near = nearestFrame(frames, lines[i].time);
        if (near) this.emit('open-frame', near);
      },
    }, el('time', {}, clock(lines[i].time)), el('span', {}, lines[i].text))));
    return el('section', { className: 'ev heard' }, el('h4', {}, 'Speech'), list, more);
  }
}

/**
 * Draws the first `first` of `total` things into `host` (`make(i)` builds the i-th) and returns a
 * "Show more" button for the rest, or null when all of them fit. Each press draws up to `chunk`
 * more and moves the keyboard to the first of those, so it is not lost with the button.
 */
function reveal(host, total, first, chunk, noun, make) {
  let drawn = 0;
  const draw = (upTo) => {
    const items = Array.from({ length: Math.min(upTo, total) - drawn }, (_, i) => make(drawn + i));
    drawn += items.length;
    host.append(...items);
    return items[0];
  };
  const label = () => `Show ${Math.min(chunk, total - drawn)} more ${noun}`;
  draw(first);
  if (drawn >= total) return null;
  const more = el('button', {
    className: 'more',
    onclick: () => {
      const next = draw(drawn + chunk);
      if (drawn >= total) more.remove();
      else more.textContent = label();
      if (!next.matches('button, a[href]')) next.tabIndex = -1;
      next.focus();
    },
  }, label());
  return more;
}

const count = (n, noun) => `${n.toLocaleString('en-US')} ${noun}${n === 1 ? '' : 's'}`;

const stat = (n, one, many) => el('div', {}, el('dt', {}, n === 1 ? one : many), el('dd', {}, n.toLocaleString('en-US')));
