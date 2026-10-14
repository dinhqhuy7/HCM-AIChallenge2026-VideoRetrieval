import { ticks } from '../core/anatomy.js';
import { gapLabel, lay, orderNote, overlapNote } from '../core/chains.js';
import { TASK_NAMES } from '../core/models.js';
import { icon } from './icons.js';
import { View, clock, el, svg } from './view.js';

/**
 * TRAKE results: the events named once, then each video that holds a chain. A video's chains are
 * drawn on its time line, one lane per event, with the frames they use as numbered pins, so the
 * order and the gaps of the events can be seen; below, every chain as a row of frames, addable
 * as an answer (`add-answer`). Last, every event's own ranking over all videos, folded: a ranking
 * draws its cards when first opened, so it loads no pictures until someone looks at it.
 */
export class EventChainView extends View {
  /** The height of one lane of the time line, in pixels. */
  static LANE = 34;
  #provider;
  #docs;

  constructor(element, provider, docsUrl = null) {
    super(element);
    this.#provider = provider;
    this.#docs = docsUrl;
  }

  open(query) {
    return this.load(async () => {
      const found = await this.#provider.searchEvents(query);
      const groups = lay(found);
      const videos = await Promise.all(groups.map((group) => Promise.resolve().then(() => this.#provider.video(group.videoId)).catch(() => null)));
      return { query, ...found, groups, videos };
    });
  }

  skeleton() {
    return el('div', { className: 'skeleton', ariaHidden: 'true' },
      el('div', { className: 'bar wide' }),
      el('div', { className: 'bar' }),
      el('div', { className: 'ghost block' }),
      el('div', { className: 'ghost row' }));
  }

  render({ query, stages, chains, groups, videos }) {
    const names = stages.map((_, e) => query.stages[e] ?? `Event ${e + 1}`);
    this.draw(
      this.#head(query, chains.length, groups.length),
      el('ol', { className: 'events' }, names.map((name, e) => el('li', {}, num(e), name))),
      groups.length > 0 && el('p', { className: 'hint' },
        `Each frame shows its time and its rank among the ${Math.max(...stages.map((frames) => frames.length))} frames recorded for its event.`),
      groups.length > 0
        ? el('ol', { className: 'groups' }, groups.map((group, i) => this.#group(group, videos[i], names)))
        : el('p', { className: 'message empty' }, 'No chain is recorded for this query.'),
      stages.length > 0 && el('h3', { className: 'section' }, 'Each event on its own, over all videos'),
      ...stages.map((frames, e) => this.#stage(names[e], frames, e)),
    );
    this.emit('announce', `${query.id ?? 'Your search'}: ${count(chains.length, 'chain')} in ${count(groups.length, 'video')}.`);
  }

  #head(query, chains, videos) {
    return el('div', { className: 'head' },
      el('div', { className: 'titles' },
        el('h2', {}, query.id ?? 'Your search', el('span', { className: 'badge' }, TASK_NAMES.trake)),
        query.text && el('p', { className: 'sub echo' }, query.text)),
      el('div', { className: 'tools' }, el('span', { className: 'count' }, `${count(chains, 'chain')} · ${count(videos, 'video')}`)));
  }

  /** One video: where its chains fall on its time line, what that shows, and the chains themselves. */
  #group(group, video, names) {
    const [reference] = group.chains;
    const order = orderNote(group);
    const overlap = overlapNote(group);
    return el('li', { className: 'group' },
      el('div', { className: 'group-head' },
        el('div', { className: 'titles' },
          el('h3', {}, group.videoId),
          video?.title && el('p', { className: 'sub' }, video.title)),
        el('button', {
          className: 'act',
          ariaLabel: `Look inside ${group.videoId}`,
          onclick: () => this.emit('browse-video', { videoId: group.videoId, frame: reference.frames[0] }),
        }, icon('film'), 'Look inside')),
      this.#chart(group, names),
      order && el('p', { className: 'remark' }, order, ' ', this.#guide('why-the-chain-is-searched-as-a-whole', 'Why the chain is searched as a whole')),
      overlap && el('p', { className: 'remark' }, `Chains of one video overlap. ${overlap} `,
        this.#guide('what-the-100-rows-are-and-are-not', 'How the main branch’s rows overlap')),
      el('ol', { className: 'chain-list' }, group.chains.map((chain) => el('li', {}, this.#chain(chain, group, reference)))));
  }

  #guide(anchor, label) {
    return this.#docs
      ? el('a', { className: 'guide', href: `${this.#docs}trake.md#${anchor}`, target: '_blank', rel: 'noopener' }, label)
      : null;
  }

  /**
   * The time line: a lane for each event and the time across, the frames of the chains as numbered
   * pins (the first chain filled, frames only other chains use outlined) joined by a line for each
   * chain, and where the best frame of an event is on its own when no chain takes it (dashed).
   */
  #chart(group, names) {
    const { from, to } = group.window;
    const lane = EventChainView.LANE;
    const [reference] = group.chains;
    const across = (time) => `${(((time - from) / (to - from)) * 100).toFixed(2)}%`;
    const centre = (e) => (e + 0.5) * lane;
    const { step, times } = ticks(to, 5, from);
    const place = (node, time, e) => {
      Object.assign(node.style, { left: across(time), top: `${centre(e)}px` });
      return node;
    };

    const pins = group.events.flatMap((event, e) => {
      const drawn = event.frames.map((used) => {
        const mine = used.chains.includes(reference.number);
        const says = `Event ${e + 1}: ${clock(used.frame.time)}, frame ${used.frame.frameIdx}${used.rank ? `, ranked #${used.rank}` : ''}, in ${used.chains.length > 1 ? 'chains' : 'chain'} ${list(used.chains)}`;
        return place(el('button', {
          className: mine ? 'pin' : 'pin alt', ariaLabel: says, title: says, onclick: () => this.emit('open-frame', used.frame),
        }, String(e + 1)), used.frame.time, e);
      });
      const { best } = event;
      if (best && !event.frames.some((used) => used.frame.key === best.frame.key)) {
        const says = `Event ${e + 1}: the best frame of this video on its own, ${clock(best.frame.time)}, frame ${best.frame.frameIdx}, ranked #${best.rank}`;
        drawn.push(place(el('button', {
          className: 'pin best', ariaLabel: says, title: says, onclick: () => this.emit('open-frame', best.frame),
        }, String(e + 1)), best.frame.time, e));
      }
      return drawn;
    });

    const paths = svg('svg', {
      class: 'paths', viewBox: `0 0 100 ${group.events.length * lane}`, preserveAspectRatio: 'none', 'aria-hidden': 'true',
    }, [...group.chains].reverse().map((chain) => svg('polyline', {
      class: chain === reference ? 'path' : 'path other',
      points: chain.frames.map((frame, e) => `${(((frame.time - from) / (to - from)) * 100).toFixed(2)},${centre(e)}`).join(' '),
    })));

    const anyOther = group.events.some((event) => event.frames.some((used) => !used.chains.includes(reference.number)));
    const anyBest = pins.some((pin) => pin.classList.contains('best'));
    const body = el('div', { className: 'chart-body' },
      el('div', { className: 'nums', ariaHidden: 'true' }, names.map((name, e) => el('span', { title: name }, num(e)))),
      el('div', { className: 'plot' },
        el('div', { className: 'rails', ariaHidden: 'true' }, group.events.map(() => el('div', { className: 'rail' }))),
        paths,
        pins,
        el('div', { className: 'axis', ariaHidden: 'true' }, times.map((time) => {
          const label = el('span', {}, clock(time));
          label.style.left = across(time);
          return label;
        }))));
    body.style.setProperty('--lane', `${lane}px`);
    body.style.setProperty('--lanes', String(group.events.length));
    body.style.setProperty('--tick', `${((step / (to - from)) * 100).toFixed(3)}%`);
    body.style.setProperty('--tick-start', times.length ? across(times[0]) : '0%');
    return el('figure', { className: 'chart', role: 'group', ariaLabel: `Where the frames of each event fall in ${group.videoId}` },
      body,
      el('figcaption', { className: 'legend' },
        el('span', {}, el('i', { className: 'key used' }), group.chains.length > 1 ? `Frame of chain ${reference.number}` : 'Frame of the chain'),
        anyOther && el('span', {}, el('i', { className: 'key alt' }), 'Frame only another chain uses'),
        anyBest && el('span', {}, el('i', { className: 'key best' }), 'Best frame of the event in this video, on its own')));
  }

  #chain(chain, group, reference) {
    const differs = (e) => chain !== reference && chain.frames[e].key !== reference.frames[e]?.key;
    const changed = chain.frames.flatMap((_, e) => (differs(e) ? [`E${e + 1}`] : []));
    return el('div', { className: 'chain' },
      el('div', { className: 'chain-head' },
        el('h4', {}, `Chain ${chain.number}`,
          el('span', { className: 'kind' }, `${chain.span.toFixed(1)} s from E1 to E${chain.frames.length}`),
          changed.length > 0 && el('span', { className: 'kind' }, `differs in ${list(changed)}`)),
        el('button', {
          className: 'add', ariaLabel: `Add chain ${chain.number} to the answers`, onclick: () => this.emit('add-answer', { frames: chain.frames }),
        }, 'Add chain')),
      el('ol', { className: 'steps' }, chain.frames.map((frame, e) => {
        const used = group.events[e].frames.find((entry) => entry.frame.key === frame.key);
        return el('li', { className: differs(e) ? 'step differs' : 'step' },
          el('div', { className: 'step-head' },
            num(e),
            e > 0 && el('span', { className: 'gap' }, gapLabel(chain.gaps[e - 1])),
            differs(e) && el('span', { className: 'sr-only' }, `Differs from chain ${reference.number}`)),
          this.frameCard(frame, used?.rank ? `${clock(frame.time)} · ranked #${used.rank}` : clock(frame.time)));
      })));
  }

  #stage(name, frames, e) {
    const row = el('div', { className: 'row' });
    const details = el('details', {}, el('summary', {}, num(e), name, el('span', { className: 'kind' }, ` · ${frames.length} frames`)), row);
    details.addEventListener('toggle', () => {
      if (details.open && !row.firstChild) row.append(...frames.map((frame) => this.frameCard(frame)));
    });
    return details;
  }
}

/** The number of an event, as a small badge a screen reader reads as "Event 2". */
const num = (e) => el('span', { className: 'num' }, el('span', { className: 'sr-only' }, 'Event '), String(e + 1));

const count = (n, noun) => `${n} ${noun}${n === 1 ? '' : 's'}`;

/** 1, 2 and 3. */
const list = (items) => (items.length < 2 ? items.join('') : `${items.slice(0, -1).join(', ')} and ${items.at(-1)}`);
