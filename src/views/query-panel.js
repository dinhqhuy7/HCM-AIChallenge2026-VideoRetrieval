import { Query, TASK_NAMES } from '../core/models.js';
import { View, el } from './view.js';

/**
 * Where a search starts: the sample queries of one task at a time, picked with a KIS / Q&A / TRAKE
 * switch and narrowed by typed words (when the provider has a catalog), a keyword box with a few
 * example words, a few videos to look inside, and a free-text box (when it supports them). Emits
 * `search` with a Query, `search-keyword` with the typed words, or `look-inside` with a video's id.
 * On a narrow screen the whole panel folds into a line about what was just asked, so the results
 * are not pushed below the fold.
 */
export class QueryPanel extends View {
  static NARROW = '(max-width: 1100px)';
  #catalog;
  #can;
  #examples;
  #videos;
  #task;
  #selected = null;
  #filter = '';
  #part = { summary: el('div', { className: 'summary' }) };

  /** `videos` are `{ id, note }`: videos worth opening first, and why. */
  constructor(element, catalog, capabilities, examples = [], videos = []) {
    super(element);
    this.#catalog = catalog;
    this.#can = capabilities;
    this.#examples = examples;
    this.#videos = videos;
    this.#task = catalog?.tasks()[0]?.task;
  }

  render() {
    this.draw(
      this.#catalog && this.#samples(),
      this.#part.summary,
      this.#can.keyword && this.#keywordForm(),
      this.#can.browse && this.#can.transcript && this.#videos.length > 0 && this.#lookInside(),
      this.#can.freeText && this.#freeTextForm(),
    );
    if (this.#catalog) this.#fill();
  }

  /** Searches these words as if they had been typed into the box: for a button elsewhere on the page. */
  searchWords(text) {
    if (this.#part.words) this.#part.words.value = text;
    this.#runWords(text);
  }

  /** Chooses the sample query with this id as if it had been clicked, for a button elsewhere on the page. */
  choose(id) {
    const query = this.#catalog?.find(id);
    if (!query) return false;
    this.#task = query.task;
    this.#filter = '';
    if (this.#part.filter) this.#part.filter.value = '';
    this.#fill();
    const button = [...this.#part.list.querySelectorAll('.query')].find((node) => node.querySelector('.qid')?.firstChild?.textContent === id);
    if (!button) return false;
    this.#choose(query, button);
    button.scrollIntoView({ block: 'nearest' });
    return true;
  }

  /** The parts that live as long as the panel: redrawing the box would lose what is typed in it. */
  #samples() {
    const part = this.#part;
    part.tasks = el('div', { className: 'tasks', role: 'group', ariaLabel: 'Task' });
    part.filter = el('input', {
      type: 'search', className: 'filter', placeholder: 'Filter these queries', ariaLabel: 'Filter sample queries',
      autocomplete: 'off', oninput: (event) => { this.#filter = event.target.value; this.#fill(); },
    });
    part.note = el('p', { className: 'note' });
    part.list = el('div', { className: 'list' });
    return el('section', { className: 'samples' },
      el('h2', {}, 'Sample queries'), part.tasks, part.filter, part.note, part.list);
  }

  /** Redraws the switch, the note and the list, not the filter box. */
  #fill() {
    const { tasks, note, list } = this.#part;
    const counts = this.#catalog.tasks(this.#filter);
    tasks.replaceChildren(...counts.map(({ task, count }) => el('button', {
      className: task === this.#task ? 'selected' : '',
      ariaPressed: String(task === this.#task),
      onclick: () => { this.#task = task; this.#fill(); },
    }, TASK_NAMES[task], el('span', {}, count))));

    const groups = this.#catalog.groups(this.#task, this.#filter);
    const shown = groups.reduce((sum, group) => sum + group.queries.length, 0);
    const total = this.#catalog.tasks().find(({ task }) => task === this.#task)?.count ?? 0;
    note.textContent = this.#noteText(shown, total, counts);
    list.replaceChildren(...groups.flatMap(({ label, queries }) => [
      el('h3', {}, label),
      el('ul', {}, queries.map((query) => el('li', {}, this.#item(query)))),
    ]));
  }

  #noteText(shown, total, counts) {
    const name = TASK_NAMES[this.#task];
    if (!this.#filter.trim()) return `${total} ${name} ${total === 1 ? 'query' : 'queries'}`;
    if (shown) return `${shown} of ${total} match`;
    const elsewhere = counts.filter(({ count }) => count > 0).map(({ task, count }) => `${count} in ${TASK_NAMES[task]}`);
    return `No ${name} query matches.${elsewhere.length ? ` ${elsewhere.join(', ')}.` : ''}`;
  }

  #item(query) {
    const events = query.stages.length;
    return el('button', {
      className: query.id === this.#selected?.id ? 'query selected' : 'query',
      ariaCurrent: query.id === this.#selected?.id ? 'true' : 'false',
      onclick: (event) => this.#choose(query, event.currentTarget),
    },
    el('span', { className: 'qid' }, query.id, events > 0 && el('span', { className: 'qevents' }, `${events} events`)),
    el('span', { className: 'qtext' }, query.text));
  }

  /** Marks the choice in place: redrawing the list would scroll it back to the top. */
  #choose(query, button) {
    this.#selected = query;
    const before = this.#part.list.querySelector('.query.selected');
    before?.classList.remove('selected');
    before?.setAttribute('aria-current', 'false');
    button.classList.add('selected');
    button.setAttribute('aria-current', 'true');
    this.#fold(query.id ?? TASK_NAMES[query.task], query.text);
    this.emit('search', query);
  }

  /**
   * On a narrow screen, replaces the panel by a line saying what was asked and a way back to it.
   * A wide screen shows everything all the time, so there it only keeps the line ready.
   */
  #fold(label, text) {
    const { summary } = this.#part;
    summary.replaceChildren(
      el('span', { className: 'qid' }, label),
      el('span', { className: 'qtext' }, text),
      el('button', {
        className: 'change',
        onclick: () => {
          this.element.classList.remove('folded');
          this.#part.list?.querySelector('.selected')?.scrollIntoView({ block: 'nearest' });
        },
      }, 'Change search'));
    this.element.classList.toggle('folded', globalThis.matchMedia?.(QueryPanel.NARROW).matches ?? false);
  }

  #keywordForm() {
    const words = el('input', {
      type: 'search', placeholder: 'e.g. bao lu', ariaLabel: 'Words to search for', autocomplete: 'off',
    });
    this.#part.words = words;
    const run = (text) => this.#runWords(text);
    return form('Search OCR and transcript', [words], () => run(words.value),
      el('p', { className: 'hint' }, 'Words read on screen or heard in speech. Frames with more of your words come first.'),
      this.#examples.length > 0 && el('p', { className: 'examples' }, 'Try ',
        this.#examples.map((word) => el('button', {
          type: 'button', className: 'chip', onclick: () => { words.value = word; run(word); },
        }, word))));
  }

  #runWords(text) {
    if (!text.trim()) return;
    this.#fold('Words', text.trim());
    this.emit('search-keyword', text.trim());
  }

  /** A way into the scenes of a video for a visit that does not start from a frame. */
  #lookInside() {
    return el('section', { className: 'inside' },
      el('h2', {}, 'Look inside a video'),
      el('p', { className: 'hint' }, 'See a video cut into scenes, with the frames, words on screen and speech of each.'),
      el('ul', {}, this.#videos.map(({ id, note }) => el('li', {}, el('button', {
        className: 'query',
        onclick: () => { this.#fold(id, note); this.emit('look-inside', { videoId: id }); },
      }, el('span', { className: 'qid' }, id), el('span', { className: 'qtext' }, note))))));
  }

  /** TRAKE takes one event per line; the other tasks take the whole text. */
  #freeTextForm() {
    const task = el('select', {}, Object.entries(TASK_NAMES).map(([value, name]) => el('option', { value }, name)));
    const text = el('textarea', { rows: 3, placeholder: 'Describe the scene' });
    return form('Describe the scene', [task, text], () => {
      const lines = text.value.split('\n').map((line) => line.trim()).filter(Boolean);
      if (!lines.length) return;
      const stages = task.value === 'trake' ? lines : [];
      const query = new Query({ task: task.value, text: lines.join(' '), stages });
      this.#fold(TASK_NAMES[query.task], query.text);
      this.emit('search', query);
    });
  }
}

const form = (label, fields, submit, ...extras) => el('form', { onsubmit: (e) => { e.preventDefault(); submit(); } },
  el('label', {}, label, fields), el('button', {}, 'Search'), extras);
