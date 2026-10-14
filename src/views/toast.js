import { View } from './view.js';

/**
 * A short note at the bottom of the page for what a click just did when the thing it changed is out
 * of sight (a line added to a list under a panel, say). It is a status region, so a screen reader
 * says it too, and it goes away by itself.
 */
export class Toast extends View {
  static SHOWN_MS = 2600;
  static CLEARED_MS = 300;
  #timer = null;

  render(text) {
    clearTimeout(this.#timer);
    this.element.textContent = text;
    this.element.classList.add('show');
    this.#timer = setTimeout(() => {
      this.element.classList.remove('show');
      // Emptied once it has faded, so the same note said twice is read twice.
      this.#timer = setTimeout(() => { this.element.textContent = ''; }, Toast.CLEARED_MS);
    }, Toast.SHOWN_MS);
  }

  show(text) {
    this.render(text);
  }
}
