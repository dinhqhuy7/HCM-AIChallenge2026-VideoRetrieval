import { Query, TASK_NAMES } from '../core/models.js';
import { View, el } from './view.js';

/**
 * Where a search starts: the sample queries of one task at a time, picked with
 * a KIS / Q&A / TRAKE switch (when the provider has a catalog), a keyword box
 * and a free-text box (when it supports them). Emits `search` with a Query, or
 * `search-keyword` with the typed words.
 */
export class QueryPanel extends View {
  #catalog;
  #can;
  #samples = el('section', { className: 'samples' });
  #task;
  #selected = null;

  constructor(element, catalog, capabilities) {
    super(element);
    this.#catalog = catalog;
    this.#can = capabilities;
    this.#task = catalog?.tasks()[0]?.task;
  }

  render() {
    this.draw(
      this.#catalog && this.#samples,
      this.#can.keyword && this.#keywordForm(),
      this.#can.freeText && this.#freeTextForm(),
    );
    if (this.#catalog) this.#fill();
  }

  /** Redraws only the switch and the list, so the boxes below keep what was typed. */
  #fill() {
    this.#samples.replaceChildren(
      el('div', { className: 'tasks' }, this.#catalog.tasks().map(({ task, count }) => el('button', {
        className: task === this.#task ? 'selected' : '',
        ariaPressed: String(task === this.#task),
        onclick: () => { this.#task = task; this.#fill(); },
      }, TASK_NAMES[task], el('span', {}, count)))),
      el('div', { className: 'list' }, this.#catalog.groups(this.#task).flatMap(({ label, queries }) => [
        el('h3', {}, label),
        el('ul', {}, queries.map((query) => el('li', {}, el('button', {
          className: query.id === this.#selected ? 'query selected' : 'query',
          onclick: (event) => this.#choose(query, event.currentTarget),
        }, el('b', {}, query.id), ` ${query.text}`)))),
      ])),
    );
  }

  /** Marks the choice in place: redrawing the list would scroll it back to the top. */
  #choose(query, button) {
    this.#selected = query.id;
    this.#samples.querySelector('.query.selected')?.classList.remove('selected');
    button.classList.add('selected');
    this.emit('search', query);
  }

  #keywordForm() {
    const words = el('input', { type: 'search', placeholder: 'e.g. bao lu (no accents)' });
    return form('Search OCR and transcript', [words], () => {
      if (words.value.trim()) this.emit('search-keyword', words.value.trim());
    });
  }

  /** TRAKE takes one event per line; the other tasks take the whole text. */
  #freeTextForm() {
    const task = el('select', {}, Object.entries(TASK_NAMES).map(([value, name]) => el('option', { value }, name)));
    const text = el('textarea', { rows: 3, placeholder: 'Describe the scene' });
    return form('Describe the scene', [task, text], () => {
      const lines = text.value.split('\n').map((line) => line.trim()).filter(Boolean);
      if (!lines.length) return;
      const stages = task.value === 'trake' ? lines : [];
      this.emit('search', new Query({ task: task.value, text: lines.join(' '), stages }));
    });
  }
}

const form = (label, fields, submit) => el('form', { onsubmit: (e) => { e.preventDefault(); submit(); } },
  el('label', {}, label, fields), el('button', {}, 'Search'));
