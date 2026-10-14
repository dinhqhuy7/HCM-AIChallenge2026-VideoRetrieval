import { highlight } from '../core/highlight.js';
import { around, nearestFrame, ocrLines, sceneAt, speechAround } from '../core/transcript.js';
import { icon } from './icons.js';
import { VideoPlayer } from './video-player.js';
import { View, clock, el, span, thumbnail } from './view.js';

/**
 * One frame up close: the picture, the frames around it, the words read on screen in its scene and
 * the speech near it (the words of the last word search marked), and what can be done with it. Asks
 * the page to act through `add-answer`, `show-similar`, `browse-video` and `open-frame` events.
 * Beside the results it is a panel; on a narrow screen it rises over the page like a sheet, and
 * closes with its button or the Escape key.
 */
export class FrameViewer extends View {
  static RADIUS = 4;
  static SPEECH_WINDOW = 10;
  static OCR_LINES = 12;
  static SHEET = '(max-width: 1100px)';
  #provider;
  #can;
  #docs;
  #opener = null;
  #latest = 0;

  constructor(element, provider, capabilities, docsUrl = null) {
    super(element);
    this.#provider = provider;
    this.#can = capabilities;
    this.#docs = docsUrl;
    element.ownerDocument.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && this.isOpen && !event.target.matches?.('input, textarea, select')) this.close();
    });
  }

  get isOpen() {
    return this.element.classList.contains('open');
  }

  /** `words` is the last word search, if any: its words are marked in the text. */
  show(frame, words = '') {
    if (!this.isOpen) this.#opener = this.element.ownerDocument.activeElement;
    this.element.classList.add('open');
    if (!this.element.firstChild) this.message('Loading frame…');
    const turn = ++this.#latest;
    return this.load(async () => {
      const [frames, transcript, video] = await Promise.all([
        this.#provider.videoFrames(frame.videoId),
        this.#can.transcript ? this.#provider.transcript(frame.videoId) : null,
        Promise.resolve().then(() => this.#provider.video(frame.videoId)).catch(() => null),
      ]);
      // A newer choice, or a close, came while this was loading: it must not be drawn over them.
      return turn === this.#latest ? { frame, frames, transcript, video, words } : null;
    });
  }

  /** A note in place of the frame (loading, or a failure): the way out stays, and a late one does not reopen a closed panel. */
  message(text, kind = 'empty', retry = null) {
    if (!this.isOpen) return;
    this.draw(
      el('div', { className: 'viewer-head' }, el('p', { className: `message ${kind}` }, text), this.#closeButton()),
      retry && el('button', { className: 'retry', onclick: retry }, 'Try again'),
    );
  }

  /** Puts the panel away. The page's focus goes back to what opened it, unless a new search is why it closes. */
  close(restoreFocus = true) {
    this.#latest += 1;
    if (!this.isOpen) return;
    this.element.classList.remove('open');
    this.draw();
    if (restoreFocus) this.#opener?.focus?.();
    this.#opener = null;
  }

  render(model) {
    if (!model || !this.isOpen) return;
    const { frame, frames, transcript, video, words } = model;
    this.emit('announce', `Frame ${frame.frameIdx} of ${frame.videoId} at ${clock(frame.time)} is open.`);
    const player = new VideoPlayer(el('div', { className: 'player' }));
    const play = () => player.load(async () => ({ video: video ?? await this.#provider.video(frame.videoId), time: frame.time }));
    this.draw(
      this.#head(frame, video),
      thumbnail(frame),
      player.element,
      el('div', { className: 'actions' },
        action('add', 'Add to answers', () => this.emit('add-answer', { frames: [frame] }), 'primary'),
        action('play', 'Play video', play),
        this.#can.similar && action('similar', 'More like this', () => this.#leave('show-similar', frame)),
        this.#can.browse && action('film', 'Whole video', () => this.#leave('browse-video', { videoId: frame.videoId, frame })),
        video && el('a', { className: 'btn', href: video.watchUrl(frame.time), target: '_blank', rel: 'noopener' },
          icon('external'), 'YouTube')),
      this.#strip(frames, frame),
      transcript && this.#words(transcript, frames, frame, words),
    );
    const strip = this.element.querySelector('.strip');
    const current = strip?.querySelector('.current');
    if (current) strip.scrollLeft = current.offsetLeft - (strip.clientWidth - current.offsetWidth) / 2;
    if (this.#sheet()) this.element.querySelector('.who')?.focus();
  }

  #sheet() {
    return globalThis.matchMedia?.(FrameViewer.SHEET).matches ?? false;
  }

  /** A choice that fills the results list: where the viewer is a sheet over them, it steps aside. */
  #leave(type, detail) {
    this.emit(type, detail);
    if (this.#sheet()) this.close(false);
  }

  #head(frame, video) {
    return el('div', { className: 'viewer-head' },
      el('div', { className: 'who', tabIndex: -1 },
        el('h2', {}, frame.videoId, el('span', { className: 'when' }, clock(frame.time))),
        el('p', { className: 'where' }, `frame ${frame.frameIdx}`, video?.title && ` · ${video.title}`)),
      this.#closeButton());
  }

  #closeButton() {
    return el('button', { className: 'close', title: 'Close (Esc)', ariaLabel: 'Close', onclick: () => this.close() }, icon('close'));
  }

  /** The frames either side of this one, with this one marked and scrolled to the middle. */
  #strip(frames, frame) {
    return el('div', { className: 'row strip', role: 'group', ariaLabel: 'Frames around this one' },
      around(frames, frame, FrameViewer.RADIUS).map((neighbour) => {
        const card = this.frameCard(neighbour);
        if (neighbour.key === frame.key) {
          card.classList.add('current');
          card.setAttribute('aria-current', 'true');
        }
        return card;
      }));
  }

  #words({ onScreen, speech }, frames, frame, words) {
    const scene = sceneAt(onScreen, frame.time);
    const heard = speechAround(speech, frame.time, FrameViewer.SPEECH_WINDOW);
    return el('div', { className: 'words' },
      this.#onScreen(scene, words),
      el('section', {},
        el('h3', {}, 'Speech', el('span', { className: 'range' }, `within ${FrameViewer.SPEECH_WINDOW} s`)),
        heard.length
          ? el('ol', { className: 'speech' }, heard.map((line) => el('li', {}, el('button', {
            className: 'line',
            title: 'Go to the nearest frame',
            onclick: () => this.emit('open-frame', nearestFrame(frames, line.time)),
          }, el('time', {}, clock(line.time)), el('span', {}, marked(line.text, words))))))
          : el('p', { className: 'none' }, 'Nothing was said close to this moment.')));
  }

  #onScreen(scene, words) {
    const lines = scene ? ocrLines(scene.text) : [];
    const list = el('ul', { className: 'lines' });
    const draw = (all) => list.replaceChildren(...lines.slice(0, all ? lines.length : FrameViewer.OCR_LINES)
      .map((line) => el('li', {}, marked(line, words))));
    draw(false);
    const hidden = lines.length - FrameViewer.OCR_LINES;
    const more = hidden > 0 && el('button', {
      className: 'more',
      onclick: (event) => { draw(true); event.currentTarget.remove(); },
    }, `Show ${hidden} more`);
    return el('section', {},
      el('h3', {}, 'On screen', scene && el('span', { className: 'range' }, span(scene.time, scene.until))),
      lines.length ? [list, more] : el('p', { className: 'none' }, 'No text was read on screen in this scene.'),
      lines.length > 0 && this.#docs && el('a', {
        className: 'why', href: `${this.#docs}offline/03-ocr.md#lessons`, target: '_blank', rel: 'noopener',
      }, 'Why are some letters missing?'));
  }
}

/** A text with the words of the last search in `<mark>`. */
const marked = (text, words) => highlight(text, words).map((piece) => (piece.hit ? el('mark', {}, piece.text) : piece.text));

const action = (name, label, onclick, kind = '') => el('button', { className: `act ${kind}`.trim(), onclick }, icon(name), label);
