import { TASK_NAMES } from '../../core/models.js';

/** The sample queries by task, then by round, in the order they were published. */
export class QueryCatalog {
  #queries;

  constructor(queries) {
    this.#queries = queries;
  }

  /** The tasks that have queries, in `TASK_NAMES` order, with how many each has. */
  tasks() {
    return Object.keys(TASK_NAMES)
      .map((task) => ({ task, count: this.#queries.filter((query) => query.task === task).length }))
      .filter(({ count }) => count > 0);
  }

  /** One task's queries, grouped by round. */
  groups(task) {
    const groups = new Map();
    for (const query of this.#queries.filter((q) => q.task === task)) {
      const label = `Round ${query.round}`;
      groups.set(label, [...(groups.get(label) ?? []), query]);
    }
    return [...groups].map(([label, queries]) => ({ label, queries }));
  }
}
