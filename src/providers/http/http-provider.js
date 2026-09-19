import { Capabilities, Frame, Query, Video } from '../../core/models.js';
import { SearchProvider } from '../search-provider.js';
import { QueryCatalog } from '../static/query-catalog.js';
import { ApiClient } from './api-client.js';

/**
 * Answers from your own backend. Each method is one endpoint of docs/api.md;
 * a frame travels as `{ video, frame, time, image }`.
 */
export class HttpProvider extends SearchProvider {
  #api;

  constructor(base, fetchFn) {
    super();
    this.#api = new ApiClient(base, fetchFn);
  }

  async capabilities() {
    return new Capabilities(await this.#api.get('capabilities'));
  }

  async catalog() {
    const rows = await this.#api.get('queries', { optional: true });
    return rows && new QueryCatalog(rows.map((row) => new Query(row)));
  }

  async search({ task, text }) {
    return toFrames((await this.#api.post('search', { task, text })).frames);
  }

  async searchEvents({ text, stages }) {
    const found = await this.#api.post('events', { text, stages });
    return { stages: found.stages.map(toFrames), chains: found.chains.map(toFrames) };
  }

  async searchKeyword(text) {
    return toFrames((await this.#api.get(`keyword?q=${encodeURIComponent(text)}`)).frames);
  }

  async similar({ videoId, frameIdx }) {
    return toFrames((await this.#api.get(`frames/${videoId}/${frameIdx}/similar`)).frames);
  }

  async video(videoId) {
    return new Video(videoId, await this.#api.get(`videos/${videoId}`));
  }

  async videoFrames(videoId) {
    return toFrames((await this.#api.get(`videos/${videoId}/frames`)).frames);
  }

  transcript(videoId) {
    return this.#api.get(`videos/${videoId}/transcript`);
  }
}

const toFrame = ({ video, frame, time, image }) => new Frame(video, frame, time, { url: image });
const toFrames = (list) => list.map(toFrame);
