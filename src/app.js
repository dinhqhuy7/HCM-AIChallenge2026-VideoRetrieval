import { AnswerList } from './answers/answer-list.js';
import { LocalStore } from './answers/local-store.js';
import { ProviderFactory } from './providers/provider-factory.js';
import { AnswerPanel } from './views/answer-panel.js';
import { EventChainView } from './views/event-chain-view.js';
import { FrameViewer } from './views/frame-viewer.js';
import { QueryPanel } from './views/query-panel.js';
import { ResultGrid } from './views/result-grid.js';
import { clock } from './views/view.js';

/**
 * Builds the page from config: one provider, the views that need it, and the
 * answer list. It only routes events between views; no view knows another.
 */
export class App {
  #config;

  constructor(config) {
    this.#config = config;
  }

  async start() {
    const provider = ProviderFactory.create(this.#config);
    const [can, catalog] = await Promise.all([provider.capabilities(), provider.catalog()]);
    const area = (id) => document.getElementById(id);
    const queries = new QueryPanel(area('query'), catalog, can);
    const results = new ResultGrid(area('results'));
    const events = new EventChainView(area('results'));
    const viewer = new FrameViewer(area('viewer'), provider, can);
    const answers = new AnswerPanel(area('answers'), new AnswerList(new LocalStore('system-demo.answers')));
    queries.render();
    answers.render();

    const on = (type, handle) => document.addEventListener(type, (e) => handle(e.detail));
    on('search', (query) => {
      answers.setQuery(query);
      if (query.task === 'trake') {
        events.load(async () => ({ names: query.stages, ...await provider.searchEvents(query) }));
      } else {
        results.load(async () => ({ title: query.id ?? 'Your search', frames: await provider.search(query) }));
      }
    });
    on('search-keyword', (text) => results.load(async () => ({
      title: `Words "${text}"`, frames: await provider.searchKeyword(text),
    })));
    on('show-similar', (frame) => results.load(async () => ({
      title: `Like ${frame.videoId} · ${clock(frame.time)}`, frames: await provider.similar(frame),
    })));
    on('browse-video', (videoId) => results.load(async () => ({
      title: `All of ${videoId}`, frames: await provider.videoFrames(videoId),
    })));
    on('open-frame', (frame) => viewer.show(frame));
    on('add-answer', ({ frames }) => answers.add(frames));
  }
}
