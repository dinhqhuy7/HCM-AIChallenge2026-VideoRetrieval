import { AnswerList } from '../answers/answer-list.js';
import { CsvExporter } from '../answers/csv-exporter.js';
import { Answer, TASK_NAMES } from '../core/models.js';
import { icon } from './icons.js';
import { View, el, thumbnail } from './view.js';

const FORMATS = { kis: 'video,frame', qa: 'video,frame,answer', trake: 'video,frame 1,frame 2,…' };
const EMPTY = {
  kis: 'Open a frame and choose Add to answers.',
  qa: 'Open a frame and choose Add to answers. The answer text is written on every line.',
  trake: 'Add a whole chain with Add chain: a TRAKE line is a video and one frame for each event.',
};

/**
 * The current query's answers: add, reorder, remove, see the file they make, and download it as the
 * submission CSV. What a click did is said in a short note, because the list may be out of sight.
 */
export class AnswerPanel extends View {
  static PREVIEW_LINES = 6;
  #answers;
  #query = null;
  #text = '';
  #confirming = false;
  #after = null;

  constructor(element, answers) {
    super(element);
    this.#answers = answers;
    answers.addEventListener('change', () => this.render());
  }

  /** Free-text queries have no id; their answers share one list. */
  get #id() {
    return this.#query.id ?? 'free-text';
  }

  setQuery(query) {
    this.#query = query;
    this.#confirming = false;
    this.render();
  }

  add(frames) {
    if (!this.#query) return this.#say('Choose a query first: answers are kept for each query.');
    if (this.#query.task === 'trake' && frames.length < 2) {
      return this.#say('A TRAKE line needs a chain of frames: use Add chain on an event chain.');
    }
    const count = this.#answers.of(this.#id).length;
    if (count >= AnswerList.LIMIT) return this.#say(`The list is full: ${AnswerList.LIMIT} lines is the most the competition takes.`);
    if (!this.#answers.add(this.#id, new Answer(this.#query.task, frames, this.#text))) return this.#say('Already in the list.');
    return this.#say(`Added · ${count + 1}/${AnswerList.LIMIT}`);
  }

  render() {
    if (!this.#query) return this.message('Answers appear here once a query is chosen.');
    const task = this.#query.task;
    const answers = this.#answers.of(this.#id);
    this.draw(
      el('div', { className: 'answers-head' },
        el('h2', {}, 'Answers', el('span', { className: 'badge' }, TASK_NAMES[task])),
        el('span', { className: answers.length >= AnswerList.LIMIT ? 'quota full' : 'quota' }, `${answers.length}/${AnswerList.LIMIT}`)),
      task === 'qa' && el('label', { className: 'field' }, 'Answer text, written on each new line',
        el('input', { placeholder: 'e.g. 5', value: this.#text, oninput: (event) => { this.#text = event.target.value; } })),
      answers.length
        ? el('ol', { className: 'answers' }, answers.map((answer, i) => this.#line(answer, i, answers.length)))
        : el('p', { className: 'message note' }, EMPTY[task]),
      answers.length > 0 && this.#preview(task, answers),
      this.#actions(answers),
    );
    this.#restoreFocus();
  }

  #say(text) {
    this.emit('toast', text);
  }

  #line(answer, i, count) {
    const { video, detail } = answer.summary();
    // `to` is where the focus belongs afterwards: with the moved line, or with the line that took a removed one's place
    const act = (name, label, disabled, to, onclick) =>
      el('button', { className: 'icon-button', title: label, ariaLabel: label, disabled, onclick: () => { this.#after = { index: to, label }; onclick(); } }, icon(name));
    return el('li', {},
      thumbnail(answer.frames[0], ''),
      el('span', { className: 'what' }, el('b', {}, video), el('span', {}, detail)),
      el('span', { className: 'row-actions' },
        act('up', 'Move up', i === 0, i - 1, () => this.#answers.move(this.#id, i, i - 1)),
        act('down', 'Move down', i === count - 1, i + 1, () => this.#answers.move(this.#id, i, i + 1)),
        act('remove', 'Remove', false, i, () => this.#answers.remove(this.#id, i))));
  }

  /** The file as it will be downloaded, so the competition's format is there to see. */
  #preview(task, answers) {
    const lines = CsvExporter.text(answers).trimEnd().split('\n');
    const shown = lines.slice(0, AnswerPanel.PREVIEW_LINES);
    const more = lines.length - shown.length;
    return el('details', { className: 'csv', open: true },
      el('summary', {}, 'CSV preview'),
      el('p', { className: 'format' }, `${FORMATS[task]}. One line per answer, best first, no header.`),
      el('pre', {}, more > 0 ? `${shown.join('\n')}\n… ${more} more` : shown.join('\n')));
  }

  #actions(answers) {
    if (this.#confirming) {
      return el('div', { className: 'answers-actions confirm' },
        el('span', {}, `Remove all ${answers.length} ${answers.length === 1 ? 'line' : 'lines'}?`),
        el('button', { className: 'danger', onclick: () => { this.#confirming = false; this.#answers.clear(this.#id); } }, 'Remove all'),
        el('button', { className: 'keep', onclick: () => { this.#confirming = false; this.render(); this.element.querySelector('.clear')?.focus(); } }, 'Cancel'));
    }
    return el('div', { className: 'answers-actions' },
      el('button', { className: 'primary', disabled: !answers.length, onclick: () => CsvExporter.download(`${this.#id}.csv`, answers) },
        icon('download'), answers.length ? `Download CSV (${answers.length})` : 'Download CSV'),
      el('button', { className: 'clear', disabled: !answers.length, onclick: () => { this.#confirming = true; this.render(); this.element.querySelector('.keep')?.focus(); } },
        icon('trash'), 'Clear'));
  }

  /** A row's buttons are drawn again after every change: focus goes to the same place in the list. */
  #restoreFocus() {
    if (!this.#after) return;
    const { index, label } = this.#after;
    this.#after = null;
    const rows = this.element.querySelectorAll('.answers > li');
    const row = rows[Math.min(index, rows.length - 1)];
    const target = row?.querySelector(`button[aria-label="${label}"]:not(:disabled)`)
      ?? row?.querySelector('button:not(:disabled)') ?? this.element.querySelector('.primary:not(:disabled)');
    target?.focus();
  }
}
