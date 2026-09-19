import { AnswerList } from '../answers/answer-list.js';
import { CsvExporter } from '../answers/csv-exporter.js';
import { Answer } from '../core/models.js';
import { View, el, thumbnail } from './view.js';

/** The current query's answers: add, reorder, remove, and download as the submission CSV. */
export class AnswerPanel extends View {
  #answers;
  #query = null;
  #text = '';
  #status = '';

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
    this.#status = '';
    this.render();
  }

  add(frames) {
    if (!this.#query) return this.message('Choose a query first: answers are kept per query.');
    this.#status = '';
    if (!this.#answers.add(this.#id, new Answer(this.#query.task, frames, this.#text))) {
      this.#status = `Not added: already listed, or the list holds ${AnswerList.LIMIT}.`;
      this.render();
    }
  }

  render() {
    if (!this.#query) return this.message('Answers appear here once a query is chosen.');
    const answers = this.#answers.of(this.#id);
    this.draw(
      el('h2', {}, `Answers · ${answers.length}/${AnswerList.LIMIT}`),
      this.#query.task === 'qa' && el('input', {
        placeholder: 'Answer to the question', value: this.#text, oninput: (e) => { this.#text = e.target.value; },
      }),
      el('ol', { className: 'answers' }, answers.map((answer, i) => this.#line(answer, i, answers.length))),
      el('button', { disabled: !answers.length, onclick: () => CsvExporter.download(`${this.#id}.csv`, answers) },
        'Download CSV'),
      this.#status && el('p', { className: 'message' }, this.#status),
    );
  }

  #line(answer, i, count) {
    const act = (symbol, label, disabled, onclick) =>
      el('button', { title: label, ariaLabel: label, disabled, onclick }, symbol);
    return el('li', {}, thumbnail(answer.frames[0]), el('span', {}, answer.cells().join(', ')),
      act('↑', 'Move up', i === 0, () => this.#answers.move(this.#id, i, i - 1)),
      act('↓', 'Move down', i === count - 1, () => this.#answers.move(this.#id, i, i + 1)),
      act('✕', 'Remove', false, () => this.#answers.remove(this.#id, i)));
  }
}
