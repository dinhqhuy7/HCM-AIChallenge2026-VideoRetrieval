import { cut } from '../core/anatomy.js';
import { lay, gapLabel } from '../core/chains.js';
import { rrf } from '../core/fusion.js';
import { MAIN } from '../core/main-output.js';
import { Answer } from '../core/models.js';
import { evenly, nearestFrame, ocrLines, sceneAt } from '../core/transcript.js';
import { icon } from './icons.js';
import { timeMap } from './time-map.js';
import { View, clock, el } from './view.js';

/** The six steps, in the order of the main branch's README, each with the guide that describes it. */
const STEPS = [
  {
    id: 'shots', name: 'Shots and keyframes',
    sentence: 'A video is cut into shots and one or more frames are picked inside each one; every picked frame is recorded with its frame number and time, so any hit can be traced back to an exact moment.',
    guides: [['Shots and keyframes', 'offline/01-shots-and-keyframes.md']],
  },
  {
    id: 'visual', name: 'Visual index',
    sentence: 'Each picked frame becomes a vector made by an image model (SigLIP 2 or PE-Core) and stored in Milvus, and a description is turned into a vector the same way, so the closest vectors answer what the picture shows.',
    guides: [['Visual index', 'offline/02-visual-index.md']],
  },
  {
    id: 'text', name: 'Text on screen',
    sentence: 'PaddleOCR reads the text on every picked frame and the lines of each shot are indexed for keyword search, because a picture vector cannot promise to match an exact caption, sign or number.',
    guides: [['Text on screen', 'offline/03-ocr.md']],
  },
  {
    id: 'speech', name: 'Speech',
    sentence: 'faster-whisper writes down what is said, with times on the same clock as the frames, and the words of each shot are indexed like the text on screen.',
    guides: [['Speech', 'offline/04-asr.md']],
  },
  {
    id: 'fusion', name: 'Search and fusion',
    sentence: 'A query goes into up to four boxes (what is seen, written on screen, said, and which objects appear), each box is searched by its own lane, and the lanes are merged by Reciprocal Rank Fusion over shots into at most 100 rows.',
    note: 'The objects box is weak and has not been checked by hand, so it is left off.',
    guides: [['Online search', 'online.md']],
  },
  {
    id: 'trake', name: 'TRAKE and answers',
    sentence: 'A TRAKE query lists events in order: each event is searched alone to find candidate videos, then the best chain of frames in time order is picked inside each candidate and written as a row of the answer file.',
    guides: [['TRAKE', 'trake.md'], ['Submission', 'submission.md']],
  },
];

/**
 * The guide: what each step of the main branch does, with an example under it. Examples are of two
 * kinds and say so: data recorded by the competition system for this page (read through the
 * provider), and output copied from the main branch's own guides (`MAIN`). Choosing a frame, a
 * query or a video asks the page to open it, with the same events as the search page uses; the
 * parts that need a search (`try-words`, `open-query`) are routed by the page.
 */
export class HowItWorks extends View {
  static NEIGHBOURS = 5;
  static ROWS = 5;
  static FILM = 5;
  #provider;
  #catalog;
  #docs;
  #how;
  #opened = false;

  /** `how` names the examples: `{ video, titleFrame, words, ranked, chain }`. */
  constructor(element, { provider, catalog, docsUrl = null, how }) {
    super(element);
    this.#provider = provider;
    this.#catalog = catalog;
    this.#docs = docsUrl;
    this.#how = how;
  }

  /** Reads and draws the page the first time it is wanted, so a visit to the search never pays for it. */
  open() {
    if (this.#opened) return null;
    this.#opened = true;
    return this.load(() => this.#read());
  }

  skeleton() {
    return el('div', { className: 'skeleton', ariaHidden: 'true' },
      el('div', { className: 'bar wide' }),
      el('div', { className: 'bar' }),
      el('div', { className: 'ghost block' }),
      ...Array.from({ length: 2 }, () => el('div', { className: 'ghost row' })));
  }

  /** Every example on its own: one that cannot be read leaves its card without it, not the page without cards. */
  async #read() {
    const { video, titleFrame, ranked, chain } = this.#how;
    const provider = this.#provider;
    const quietly = async (work) => {
      try {
        return await work();
      } catch {
        return null;
      }
    };
    const film = await quietly(async () => {
      const [frames, transcript, info] = await Promise.all([
        provider.videoFrames(video),
        provider.transcript(video),
        Promise.resolve().then(() => provider.video(video)).catch(() => null),
      ]);
      return { frames, transcript, info };
    });
    const title = film?.frames.find((frame) => frame.frameIdx === titleFrame) ?? null;
    const [near, rows, trake] = await Promise.all([
      quietly(async () => (title ? (await provider.similar(title)).slice(0, HowItWorks.NEIGHBOURS) : null)),
      quietly(async () => {
        const query = this.#catalog?.find(ranked);
        return query ? { query, frames: await provider.search(query) } : null;
      }),
      quietly(async () => {
        const query = this.#catalog?.find(chain);
        return query ? { query, group: lay(await provider.searchEvents(query))[0] } : null;
      }),
    ]);
    return { film, title, near, rows, trake };
  }

  render({ film, title, near, rows, trake }) {
    const cards = [
      this.#shots(film), this.#visual(title, near), this.#text(film, title), this.#speech(film), this.#fusion(rows), this.#trake(trake),
    ];
    this.draw(
      this.#intro(film),
      this.#flow(),
      el('ol', { className: 'how-cards' }, cards.map((card, i) => this.#card(STEPS[i], i + 1, card))),
    );
    this.emit('announce', 'How it works: six steps from videos to answers.');
  }

  #intro(film) {
    const { video } = this.#how;
    let map = null;
    if (film) {
      const { stretches, end } = cut({ frames: film.frames, ...film.transcript });
      map = timeMap({ stretches, frames: film.frames, speech: film.transcript.speech, length: end });
    }
    return el('header', { className: 'how-head' },
      el('h2', {}, 'How it works'),
      el('p', { className: 'lede' }, 'Follow a query through the system on the main branch: each step says what it does and shows an example you can open.'),
      el('dl', { className: 'how-legend' },
        el('dt', {}, tag('recorded')), el('dd', {}, 'Data the competition system made for this page.'),
        el('dt', {}, tag('main')), el('dd', {}, 'Output copied from the main branch’s guides.')),
      map && example('recorded', `${video}, laid out on one clock: its frames, the words read on screen and its speech. The steps below build these layers.`, map.element));
  }

  #flow() {
    const go = (id) => () => {
      const card = this.element.querySelector(`#how-${id}`);
      card?.scrollIntoView({ block: 'start' });
      card?.querySelector('h3')?.focus({ preventScroll: true });
    };
    const part = (label, from, to) => el('div', { className: 'how-part' },
      el('h3', {}, label),
      el('ol', {}, STEPS.slice(from, to).map((step, i) => el('li', {},
        el('button', { onclick: go(step.id) }, el('span', { className: 'num' }, String(from + i + 1)), step.name)))));
    return el('nav', { className: 'how-flow', ariaLabel: 'The steps' },
      part('Offline, once per collection', 0, 4), part('Online, for each query', 4, 6));
  }

  /** A step: its number and name, one sentence, the guides, what to try, and the examples beside them. */
  #card(step, number, { actions = [], examples = [] }) {
    return el('li', { className: 'how-card', id: `how-${step.id}` },
      el('div', { className: 'how-text' },
        el('div', { className: 'how-title' },
          el('span', { className: 'how-number', ariaHidden: 'true' }, String(number)),
          el('h3', { tabIndex: -1 }, step.name)),
        el('p', { className: 'lede' }, step.sentence),
        step.note && el('p', { className: 'hint' }, step.note),
        this.#docs && el('p', { className: 'how-links' }, step.guides.map(([label, path]) => el('a', {
          href: `${this.#docs}${path}`, target: '_blank', rel: 'noopener',
        }, icon('external'), `${label} guide`))),
        actions.length > 0 && el('div', { className: 'how-actions' }, actions)),
      el('div', { className: 'how-examples' }, examples));
  }

  #guide(path, hash, label) {
    return this.#docs ? el('a', { href: `${this.#docs}${path}${hash}`, target: '_blank', rel: 'noopener' }, label) : null;
  }

  #shots(film) {
    const { video } = this.#how;
    return {
      actions: [this.#lookInside()],
      examples: [
        film && example('recorded', `${HowItWorks.FILM} of the ${film.frames.length} frames kept for ${video}, in time order.`,
          el('div', { className: 'how-film' }, evenly(film.frames, HowItWorks.FILM).map((frame) => this.frameCard(frame, clock(frame.time))))),
        example('main', 'Shot 1 of the same video, and the keyframe taken inside it (shortened).', code(MAIN.shot.lines, 'A shot and a keyframe, as the main branch writes them')),
      ],
    };
  }

  #visual(title, near) {
    return {
      actions: title ? [el('button', { className: 'act', onclick: () => this.emit('show-similar', title) }, icon('similar'), 'More like this frame')] : [],
      examples: [
        title && near && example('recorded', `Frames that look like the title card at ${clock(title.time)} of ${title.videoId}, most alike first.`,
          el('div', { className: 'how-pair' },
            this.frameCard(title, `${title.videoId} · ${clock(title.time)}`),
            el('span', { className: 'how-arrow', ariaHidden: 'true' }, icon('arrow')),
            el('div', { className: 'how-neighbours' }, near.map((frame) => this.frameCard(frame, `${frame.videoId} · ${clock(frame.time)}`))))),
      ],
    };
  }

  #text(film, title) {
    const scene = film && title ? sceneAt(film.transcript.onScreen, title.time) : null;
    return {
      actions: [el('button', {
        className: 'act', onclick: () => this.emit('try-words', { text: this.#how.words }),
      }, icon('search'), `Search “${this.#how.words}”`)],
      examples: [
        scene && title && example('recorded', `What the competition system read on a title card, ${clock(scene.time)}–${clock(scene.until)} of ${title.videoId}.`,
          el('div', { className: 'how-pair' },
            this.frameCard(title, `${title.videoId} · ${clock(title.time)}`),
            el('ul', { className: 'lines' }, ocrLines(scene.text).map((line) => el('li', {}, line))))),
        example('main', `Five lines of keyframe ${MAIN.ocr.keyframe}, the same card, as the text step wrote them. It says “thương hiệu quản lý cân nặng”: both lose letters from the same words.`,
          el('ul', { className: 'lines' }, MAIN.ocr.lines.map((line) => el('li', {}, line))),
          el('p', { className: 'how-remark' }, this.#guide('offline/03-ocr.md', '#lessons', 'Why are some letters missing?'))),
      ],
    };
  }

  #speech(film) {
    const lines = film?.transcript.speech.slice(0, 3) ?? [];
    return {
      actions: [this.#lookInside()],
      examples: [
        lines.length > 0 && example('recorded', 'The first lines recorded for the video, each with its start. Click one to open the frame nearest to it.',
          el('ol', { className: 'speech' }, lines.map((line) => el('li', {}, el('button', {
            className: 'line',
            onclick: () => this.emit('open-frame', nearestFrame(film.frames, line.time)),
          }, el('time', {}, clock(line.time)), el('span', {}, line.text)))))),
        example('main', 'The first three segments of the same video, as the speech step wrote them: the same sentences, timed differently.', code(MAIN.asr.lines, 'Speech segments, as the main branch writes them')),
      ],
    };
  }

  #fusion(rows) {
    const { k, query, visual, ocr } = MAIN.fusion;
    const ordinal = ['Best', 'Second', 'Third'];
    const shots = [
      { name: 'The title card', ranks: [visual.card, ocr.card] },
      ...visual.others.map((rank, i) => ({ name: `${ordinal[i] ?? `Number ${rank}`} visual match`, ranks: [rank, null] })),
    ];
    const sum = (ranks) => ranks.filter((rank) => rank != null).map((rank) => `1/${k + rank}`).join(' + ');
    const table = el('table', { className: 'how-table' },
      el('caption', { className: 'sr-only' }, 'Scores of four shots'),
      el('thead', {}, el('tr', {}, ['Shot', 'Visual box', 'OCR box', `Score, k = ${k}`].map((heading) => el('th', { scope: 'col' }, heading)))),
      el('tbody', {}, shots.map(({ name, ranks }) => el('tr', {},
        el('th', { scope: 'row' }, name),
        el('td', {}, `${ranks[0]}`),
        el('td', {}, ranks[1] == null ? '–' : `${ranks[1]}`),
        el('td', {}, `${sum(ranks)} = ${rrf(k, ranks).toFixed(4)}`)))));
    return {
      actions: rows ? [this.#openQuery(rows.query.id)] : [],
      examples: [
        example('main', ['For ', el('code', {}, query), ', the guide reports the title card 5th in the visual box and 1st in the OCR box. Only ranks are used, so the lanes need no common scale.'], table),
        rows && example('recorded', `The first ${HowItWorks.ROWS} of the ${rows.frames.length} rows recorded for ${rows.query.id}, best first.`,
          el('div', { className: 'how-film' }, rows.frames.slice(0, HowItWorks.ROWS).map((frame, i) => this.frameCard(frame, null, i + 1)))),
      ],
    };
  }

  #trake(trake) {
    const chain = trake?.group?.chains[0];
    return {
      actions: trake ? [this.#openQuery(trake.query.id)] : [],
      examples: [
        chain && example('recorded', `Chain 1 of ${trake.query.id}: a frame for each of its ${chain.frames.length} events, in time order, and the row it becomes.`,
          el('ol', { className: 'steps how-chain' }, chain.frames.map((frame, e) => el('li', { className: 'step' },
            el('div', { className: 'step-head' },
              el('span', { className: 'num' }, el('span', { className: 'sr-only' }, 'Event '), String(e + 1)),
              e > 0 && el('span', { className: 'gap' }, gapLabel(chain.gaps[e - 1]))),
            this.frameCard(frame, clock(frame.time))))),
          code([new Answer('trake', chain.frames).cells().join(',')], 'The row of the answer file for this chain')),
        example('main', 'The row of each task in the answer file, one file per query, at most 100 rows, best first, no header.',
          el('table', { className: 'how-table' },
            el('caption', { className: 'sr-only' }, 'The row of each task'),
            el('thead', {}, el('tr', {}, ['Task', 'Row', 'Example'].map((heading) => el('th', { scope: 'col' }, heading)))),
            el('tbody', {}, MAIN.rows.map(({ task, row, example: sample }) => el('tr', {},
              el('th', { scope: 'row' }, task), el('td', {}, el('code', {}, row)), el('td', {}, el('code', {}, sample))))))),
      ],
    };
  }

  #lookInside() {
    const { video } = this.#how;
    return el('button', { className: 'act', onclick: () => this.emit('look-inside', { videoId: video }) }, icon('film'), `Look inside ${video}`);
  }

  #openQuery(id) {
    return el('button', { className: 'act', onclick: () => this.emit('open-query', { id }) }, icon('arrow'), `Open ${id}`);
  }
}

const tag = (kind) => (kind === 'main'
  ? el('span', { className: 'tag main' }, icon('branch'), 'Output of the main branch')
  : el('span', { className: 'tag recorded' }, icon('record'), 'Recorded · competition system'));

/** One example: where it comes from, a line on what it shows, and the thing itself. */
const example = (kind, caption, ...content) => el('figure', { className: `example ${kind}` },
  el('figcaption', {}, tag(kind), el('span', { className: 'caption' }, caption)),
  ...content);

/** Lines of output, in a box that can be scrolled with the keyboard. */
const code = (lines, label) => el('pre', { className: 'how-code', tabIndex: 0, role: 'region', ariaLabel: label }, lines.join('\n'));
