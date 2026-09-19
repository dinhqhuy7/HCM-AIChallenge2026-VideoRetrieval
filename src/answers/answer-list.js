import { Answer, Frame } from '../core/models.js';

/**
 * The answers picked for each query, in submission order. Saved after every
 * change and announced with a `change` event, so panels re-render themselves.
 */
export class AnswerList extends EventTarget {
  /** The competition scores at most 100 lines per query. */
  static LIMIT = 100;
  #store;
  #byQuery;

  constructor(store) {
    super();
    this.#store = store;
    this.#byQuery = new Map(Object.entries(store.read({})).map(([id, rows]) => [id, rows.map(revive)]));
  }

  of(queryId) {
    return this.#byQuery.get(queryId) ?? [];
  }

  /** @returns {boolean} false when the list is full or already holds these frames */
  add(queryId, answer) {
    const answers = this.of(queryId);
    const key = keyOf(answer);
    if (answers.length >= AnswerList.LIMIT || answers.some((a) => keyOf(a) === key)) return false;
    this.#save(queryId, [...answers, answer]);
    return true;
  }

  remove(queryId, index) {
    this.#save(queryId, this.of(queryId).filter((_, i) => i !== index));
  }

  move(queryId, from, to) {
    const answers = [...this.of(queryId)];
    answers.splice(to, 0, ...answers.splice(from, 1));
    this.#save(queryId, answers);
  }

  #save(queryId, answers) {
    this.#byQuery.set(queryId, answers);
    this.#store.write(Object.fromEntries(this.#byQuery));
    this.dispatchEvent(new CustomEvent('change', { detail: { queryId } }));
  }
}

const keyOf = (answer) => answer.frames.map((f) => f.key).join(' ');

const revive = ({ task, frames, text }) =>
  new Answer(task, frames.map((f) => new Frame(f.videoId, f.frameIdx, f.time, f.image)), text);
