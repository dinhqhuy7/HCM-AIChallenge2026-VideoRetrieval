import { clock, span } from '../core/clock.js';

/**
 * A part of the page that owns one element. Subclasses draw it in `render`;
 * `load` marks it busy meanwhile and shows a failure as a message, not a blank.
 * Views talk to the rest of the page only by events that bubble from here.
 */
export class View {
  static SKELETON_AFTER_MS = 120;
  /** What a person is told when something could not be loaded; the reason goes to the console, for whoever builds the page. */
  static FAILED = 'Could not load this. Check your connection and try again.';

  constructor(element) {
    this.element = element;
  }

  render() {
    throw new Error(`${this.constructor.name} must implement render()`);
  }

  /**
   * Draws what `work` gives, or the failure. Some elements are shared (the results panel holds a list
   * of frames, a video's scenes or a TRAKE chain), so the newest `load` into an element wins: one that
   * ends after a newer began draws nothing and clears nothing. A view with a `skeleton()` shows it
   * when the work takes more than a moment.
   */
  async load(work) {
    const turn = (this.element.loadTurn = (this.element.loadTurn ?? 0) + 1);
    const newest = () => this.element.loadTurn === turn;
    const waiting = typeof this.skeleton === 'function'
      ? setTimeout(() => newest() && this.draw(this.skeleton()), View.SKELETON_AFTER_MS)
      : null;
    this.element.setAttribute('aria-busy', 'true');
    try {
      const model = await work();
      if (newest()) this.render(model);
    } catch (error) {
      console.error(error);
      if (newest()) this.message(View.FAILED, 'error', () => this.load(work));
    } finally {
      clearTimeout(waiting);
      if (newest()) this.element.removeAttribute('aria-busy');
    }
  }

  /** Replaces the content, skipping empty parts as `el` does. */
  draw(...parts) {
    this.element.replaceChildren(...present(parts));
  }

  /** A line of text; a failure also offers `retry`, so a dropped connection is not the end of the visit. */
  message(text, kind = 'empty', retry = null) {
    this.draw(
      el('p', { className: `message ${kind}` }, text),
      retry && el('button', { className: 'retry', onclick: retry }, 'Try again'),
    );
  }

  emit(type, detail) {
    this.element.dispatchEvent(new CustomEvent(type, { detail, bubbles: true }));
  }

  /** The switch between the two ways to look at one whole video: cut into scenes, or every frame in a grid. */
  videoSwitch(videoId, current) {
    const ways = [['scenes', 'Scenes', 'browse-video'], ['frames', 'All frames', 'browse-frames']];
    return el('div', { className: 'seg', role: 'group', ariaLabel: 'Show the video as' },
      ways.map(([name, label, type]) => el('button', {
        className: name === current ? 'selected' : '',
        ariaPressed: String(name === current),
        onclick: () => name !== current && this.emit(type, { videoId, focusSwitch: true }),
      }, label)));
  }

  /** After the switch has replaced one view by the other, the keyboard is still on the switch. */
  keepSwitchFocus(wanted) {
    if (wanted) this.element.querySelector('.seg .selected')?.focus();
  }

  /**
   * A clickable picture of `frame` that emits `open-frame`, with the video and the time under
   * it. `rank` (1 for the best) is drawn on the picture when the list is in order of match.
   */
  frameCard(frame, label = null, rank = null) {
    const where = `${frame.videoId} at ${clock(frame.time)}`;
    return el('button', {
      className: 'card',
      ariaLabel: rank == null ? where : `Rank ${rank}: ${where}`,
      title: `${frame.videoId} · ${clock(frame.time)} · frame ${frame.frameIdx}`,
      onclick: () => this.emit('open-frame', frame),
    },
    el('span', { className: 'shot' }, thumbnail(frame, ''), rank != null && el('span', { className: 'rank' }, rank)),
    label == null
      ? el('span', { className: 'meta' }, el('b', {}, frame.videoId), el('time', {}, clock(frame.time)))
      : el('span', { className: 'meta' }, label));
  }
}

/**
 * `el('button', { className: 'x', onclick }, 'Label')`: an element with properties
 * and children. `null`, `undefined`, `false` and `''` children are skipped, so
 * `enabled && el(...)` adds a part only when it applies.
 */
export function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [name, value] of Object.entries(props)) {
    // `ariaLabel`, `role` and the like become real attributes, so a browser without ARIA reflection keeps them
    if (name === 'role') node.setAttribute('role', value);
    else if (/^aria[A-Z]/.test(name)) node.setAttribute(`aria-${name.slice(4).toLowerCase()}`, value);
    else node[name] = value;
  }
  node.append(...present(children));
  return node;
}

/** An SVG element, for the few drawings that need lines: `svg('polyline', { points: '0,0 10,10' })`. */
export function svg(tag, props = {}, ...children) {
  const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [name, value] of Object.entries(props)) node.setAttribute(name, value);
  node.append(...present(children));
  return node;
}

const present = (parts) => parts.flat(Infinity).filter((part) => part != null && part !== false && part !== '');

/**
 * A frame's picture, sized by the CSS `.thumb` box: its own image, or its cell of
 * a sprite strip. A strip as tall as the box is one box wide per cell, so shifting
 * it left by whole box widths shows the cell. `alt` is empty where the picture sits in a
 * control that already names it.
 */
export function thumbnail(frame, alt = `${frame.videoId} at ${clock(frame.time)}`) {
  const { url, cell } = frame.image;
  const img = el('img', { src: url, alt, loading: 'lazy' });
  if (cell !== undefined) Object.assign(img.style, { width: 'auto', height: '100%', left: `${cell * -100}%` });
  return el('div', { className: cell === undefined ? 'thumb' : 'thumb tiled' }, img);
}

export { clock, span };
