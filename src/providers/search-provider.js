import { Capabilities } from '../core/models.js';

/**
 * Where views get their data. StaticProvider answers from files, HttpProvider
 * from a backend; views hold only this type and never learn which one it is.
 * A method a provider cannot serve keeps the throwing default below, and its
 * `capabilities()` tells views not to offer that feature.
 */
export class SearchProvider {
  /** @returns {Promise<Capabilities>} */
  async capabilities() {
    return new Capabilities();
  }

  /** Sample queries to choose from, or null when users type their own. */
  async catalog() {
    return null;
  }

  /** @returns {Promise<Frame[]>} best first */
  async search(query) {
    return this.#missing('search');
  }

  /** @returns {Promise<{stages: Frame[][], chains: Frame[][]}>} per-stage results and chained events */
  async searchEvents(query) {
    return this.#missing('searchEvents');
  }

  /** @returns {Promise<Frame[]>} frames whose on-screen text or speech holds the words */
  async searchKeyword(text) {
    return this.#missing('searchKeyword');
  }

  /** @returns {Promise<Frame[]>} frames that look like `frame` */
  async similar(frame) {
    return this.#missing('similar');
  }

  /** @returns {Promise<Video>} */
  async video(videoId) {
    return this.#missing('video');
  }

  /** @returns {Promise<Frame[]>} every frame of the video that has a picture, in time order */
  async videoFrames(videoId) {
    return this.#missing('videoFrames');
  }

  /** @returns {Promise<{onScreen: {time, until, text}[], speech: {time, text}[]}>} in time order */
  async transcript(videoId) {
    return this.#missing('transcript');
  }

  #missing(method) {
    throw new Error(`${this.constructor.name} does not provide ${method}()`);
  }
}
