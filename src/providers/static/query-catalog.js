import { TASK_NAMES } from '../../core/models.js';
import { VietnameseText } from '../../core/vietnamese-text.js';

/** The sample queries by task, then by round, in the order they were published. */
export class QueryCatalog {
  #queries;

  constructor(queries) {
    this.#queries = queries;
  }

  /**
   * The tasks that have queries, in `TASK_NAMES` order. `count` is how many of
   * them match `filter`, so the switch can show what the typed words would find
   * in each task; a task stays listed when it has none.
   */
  tasks(filter = '') {
    return Object.keys(TASK_NAMES)
      .filter((task) => this.#queries.some((query) => query.task === task))
      .map((task) => ({ task, count: this.#of(task, filter).length }));
  }

  /** The query with this id, or null. */
  find(id) {
    return this.#queries.find((query) => query.id === id) ?? null;
  }

  /** One task's queries that match `filter`, grouped by round. A round with no match is left out. */
  groups(task, filter = '') {
    const groups = new Map();
    for (const query of this.#of(task, filter)) {
      const label = `Round ${query.round}`;
      groups.set(label, [...(groups.get(label) ?? []), query]);
    }
    return [...groups].map(([label, queries]) => ({ label, queries }));
  }

  /**
   * Whether `filter` finds `query`. Typed words are matched without accents, as the
   * start of a word of the query (so a half-typed word already finds it), and all of
   * them must be there. Text such as "p1-4" is also looked for in the id.
   */
  static matches(query, filter) {
    const typed = filter.trim();
    if (!typed) return true;
    if (query.id?.toLowerCase().includes(typed.toLowerCase())) return true;
    const words = VietnameseText.words(typed);
    const text = [query.text, ...query.stages].join(' ');
    if (!words.length) return text.toLowerCase().includes(typed.toLowerCase());
    const own = VietnameseText.words(text);
    return words.every((word) => own.some((candidate) => candidate.startsWith(word)));
  }

  #of(task, filter) {
    return this.#queries.filter((query) => query.task === task && QueryCatalog.matches(query, filter));
  }
}
