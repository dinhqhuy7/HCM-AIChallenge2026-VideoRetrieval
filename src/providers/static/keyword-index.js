import { VietnameseText } from '../../core/vietnamese-text.js';

/**
 * Finds frames by words read on screen or heard. Words live in files named by
 * their first PREFIX letters; `index.json` lists the files that exist, so a word
 * with no file is simply absent rather than a failed download.
 * Frames matching more of the words come first; among equals, videos take
 * turns, so one talkative video cannot fill the page.
 */
export class KeywordIndex {
  static LIMIT = 100;
  static PREFIX = 3;
  #data;

  constructor(data) {
    this.#data = data;
  }

  async search(text) {
    const words = [...new Set(VietnameseText.words(text))];
    const shards = new Set(await this.#data.json('data/keywords/index.json'));
    const postings = await Promise.all(words.map((word) => this.#postings(word, shards)));
    const hits = new Map();
    for (const tuple of postings.flat()) {
      const key = `${tuple[0]}/${tuple[1]}`;
      hits.set(key, { tuple, count: (hits.get(key)?.count ?? 0) + 1 });
    }
    return KeywordIndex.#takeTurns([...hits.values()])
      .slice(0, KeywordIndex.LIMIT)
      .map(({ tuple }) => this.#data.frame(tuple));
  }

  static #takeTurns(hits) {
    const turns = new Map();
    for (const hit of hits) {
      const group = `${hit.count}/${hit.tuple[0]}`;
      hit.turn = turns.get(group) ?? 0;
      turns.set(group, hit.turn + 1);
    }
    return hits.sort((a, b) => b.count - a.count || a.turn - b.turn);
  }

  async #postings(word, shards) {
    const shard = word.slice(0, KeywordIndex.PREFIX);
    return shards.has(shard) ? (await this.#data.json(`data/keywords/${shard}.json`))[word] ?? [] : [];
  }
}
