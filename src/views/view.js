/**
 * A part of the page that owns one element. Subclasses draw it in `render`;
 * `load` marks it busy meanwhile and shows a failure as a message, not a blank.
 * Views talk to the rest of the page only by events that bubble from here.
 */
export class View {
  constructor(element) {
    this.element = element;
  }

  render() {
    throw new Error(`${this.constructor.name} must implement render()`);
  }

  async load(work) {
    this.element.setAttribute('aria-busy', 'true');
    try {
      this.render(await work());
    } catch (error) {
      this.message(`Could not load: ${error.message}`, 'error');
    } finally {
      this.element.removeAttribute('aria-busy');
    }
  }

  /** Replaces the content, skipping empty parts as `el` does. */
  draw(...parts) {
    this.element.replaceChildren(...present(parts));
  }

  message(text, kind = 'empty') {
    this.draw(el('p', { className: `message ${kind}` }, text));
  }

  emit(type, detail) {
    this.element.dispatchEvent(new CustomEvent(type, { detail, bubbles: true }));
  }

  /** A clickable picture of `frame` that emits `open-frame`. */
  frameCard(frame, label = `${frame.videoId} · ${clock(frame.time)}`) {
    return el('button', { className: 'card', onclick: () => this.emit('open-frame', frame) },
      thumbnail(frame), el('span', {}, label));
  }
}

/**
 * `el('button', { className: 'x', onclick }, 'Label')`: an element with properties
 * and children. `null`, `undefined`, `false` and `''` children are skipped, so
 * `enabled && el(...)` adds a part only when it applies.
 */
export function el(tag, props = {}, ...children) {
  const node = Object.assign(document.createElement(tag), props);
  node.append(...present(children));
  return node;
}

const present = (parts) => parts.flat(Infinity).filter((part) => part != null && part !== false && part !== '');

/**
 * A frame's picture, sized by the CSS `.thumb` box: its own image, or its cell of
 * a sprite strip. A strip as tall as the box is one box wide per cell, so shifting
 * it left by whole box widths shows the cell.
 */
export function thumbnail(frame) {
  const { url, cell } = frame.image;
  const img = el('img', { src: url, alt: `${frame.videoId} at ${clock(frame.time)}`, loading: 'lazy' });
  if (cell !== undefined) Object.assign(img.style, { width: 'auto', height: '100%', left: `${cell * -100}%` });
  return el('div', { className: cell === undefined ? 'thumb' : 'thumb tiled' }, img);
}

/** 83.4 seconds -> "1:23". */
export function clock(seconds) {
  const whole = Math.floor(seconds);
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, '0')}`;
}
