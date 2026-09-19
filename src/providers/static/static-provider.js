import { Capabilities, Query } from '../../core/models.js';
import { SearchProvider } from '../search-provider.js';
import { KeywordIndex } from './keyword-index.js';
import { QueryCatalog } from './query-catalog.js';
import { StaticDataset } from './static-dataset.js';

/**
 * Answers from published files: results recorded in advance for the sample
 * queries, plus word and similarity lists. Nothing is computed from pixels,
 * which is why free-text search is the one feature it lacks.
 */
export class StaticProvider extends SearchProvider {
  #data;
  #keywords;

  constructor(base, load) {
    super();
    this.#data = new StaticDataset(base, load);
    this.#keywords = new KeywordIndex(this.#data);
  }

  async capabilities() {
    return new Capabilities({ keyword: true, similar: true, events: true, browse: true, transcript: true });
  }

  async catalog() {
    const rows = await this.#data.json('data/queries.json');
    return new QueryCatalog(rows.map((row) => new Query(row)));
  }

  async search(query) {
    return this.#frames((await this.#result(query)).frames);
  }

  async searchEvents(query) {
    const { stages, chains } = await this.#result(query);
    return { stages: stages.map((list) => this.#frames(list)), chains: chains.map((list) => this.#frames(list)) };
  }

  searchKeyword(text) {
    return this.#keywords.search(text);
  }

  async similar(frame) {
    const row = (await this.#data.videoFile(frame.videoId)).frames.find(([idx]) => idx === frame.frameIdx);
    return this.#frames(row?.[3] ?? []);
  }

  video(videoId) {
    return this.#data.video(videoId);
  }

  async videoFrames(videoId) {
    const { frames } = await this.#data.videoFile(videoId);
    return frames.map(([idx, time, tile]) => this.#data.frame([videoId, idx, time, tile]));
  }

  async transcript(videoId) {
    const { onScreen, speech } = await this.#data.videoFile(videoId);
    return { onScreen, speech };
  }

  #result(query) {
    return this.#data.json(`data/results/${query.id}.json`);
  }

  #frames(tuples) {
    return tuples.map((tuple) => this.#data.frame(tuple));
  }
}
