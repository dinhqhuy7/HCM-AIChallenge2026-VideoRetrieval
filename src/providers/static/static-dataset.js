import { Frame, Video } from '../../core/models.js';

/**
 * The published files under one base URL. Each file is fetched once, and the
 * compact frame tuple `[videoId, frameIdx, time, tile]` is turned into a Frame
 * whose picture is its own image or, when `tile` is set, one cell of a sprite
 * strip: tile 23 is cell 3 of `sprites/<videoId>/2.webp`.
 */
export class StaticDataset {
  static CELLS = 10;
  #base;
  #load;
  #cache = new Map();

  constructor(base, load = StaticDataset.fetchJson) {
    this.#base = base;
    this.#load = load;
  }

  static async fetchJson(url) {
    const response = await fetch(url);
    if (!response.ok) throw new Error(`${url}: HTTP ${response.status}`);
    return response.json();
  }

  /** A failed load is forgotten, so the next call retries instead of repeating the error. */
  json(path) {
    if (!this.#cache.has(path)) {
      const pending = this.#load(this.#base + path);
      pending.catch(() => this.#cache.delete(path));
      this.#cache.set(path, pending);
    }
    return this.#cache.get(path);
  }

  frame([videoId, frameIdx, time, tile]) {
    const image = tile === null
      ? { url: `${this.#base}img/${videoId}/${frameIdx}.webp` }
      : { url: `${this.#base}sprites/${videoId}/${Math.floor(tile / StaticDataset.CELLS)}.webp`,
        cell: tile % StaticDataset.CELLS };
    return new Frame(videoId, frameIdx, time, image);
  }

  async video(videoId) {
    const fields = (await this.json('data/videos.json'))[videoId];
    if (!fields) throw new Error(`unknown video ${videoId}`);
    return new Video(videoId, fields);
  }

  videoFile(videoId) {
    return this.json(`data/videos/${videoId}.json`);
  }
}
