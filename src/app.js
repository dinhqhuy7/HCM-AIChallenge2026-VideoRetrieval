import { AnswerList } from './answers/answer-list.js';
import { LocalStore } from './answers/local-store.js';
import { TASK_NAMES } from './core/models.js';
import { pageOf } from './core/page.js';
import { ProviderFactory } from './providers/provider-factory.js';
import { AnswerPanel } from './views/answer-panel.js';
import { EventChainView } from './views/event-chain-view.js';
import { FrameViewer } from './views/frame-viewer.js';
import { HowItWorks } from './views/how-it-works.js';
import { QueryPanel } from './views/query-panel.js';
import { ResultGrid } from './views/result-grid.js';
import { StartPanel } from './views/start-panel.js';
import { Toast } from './views/toast.js';
import { VideoAnatomy } from './views/video-anatomy.js';
import { clock } from './views/view.js';

/**
 * Builds the page from config: one provider, the views that need it, and the
 * answer list. It only routes events between views; no view knows another.
 * The page has two parts, the search and (when the config names examples) the
 * guide on how it works; the address says which one is shown.
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
    const docs = this.#config.docsUrl ?? null;
    const how = this.#config.how ?? null;
    const videos = this.#config.exampleVideos ?? [];
    const queries = new QueryPanel(area('query'), catalog, can, this.#config.keywordExamples ?? [], videos);
    const results = new ResultGrid(area('results'));
    const events = new EventChainView(area('results'), provider, docs);
    const anatomy = new VideoAnatomy(area('results'), provider, docs);
    const viewer = new FrameViewer(area('viewer'), provider, can, docs);
    const toast = new Toast(area('toast'));
    const answers = new AnswerPanel(area('answers'), new AnswerList(new LocalStore('system-demo.answers')));
    const guide = how ? new HowItWorks(area('how'), { provider, catalog, docsUrl: docs, how }) : null;
    queries.render();
    new StartPanel(area('results'), catalog, can, videos, guide !== null).render();
    answers.render();

    // Which part is shown follows the address. A part that is left keeps its state and its place on the page.
    const title = document.title;
    const skip = document.querySelector('.skip');
    const places = { search: 0, how: 0 };
    let page = 'search';
    area('pages').hidden = guide === null;
    const show = (next, moved) => {
      if (next === page) return;
      places[page] = window.scrollY;
      page = next;
      area('search').hidden = next !== 'search';
      area('how').hidden = next !== 'how';
      for (const link of area('pages').querySelectorAll('a')) {
        const mine = (link.getAttribute('href') === '#how-it-works') === (next === 'how');
        if (mine) link.setAttribute('aria-current', 'page');
        else link.removeAttribute('aria-current');
      }
      document.title = next === 'how' ? `How it works · ${title}` : title;
      skip.href = next === 'how' ? '#how-it-works' : '#results';
      skip.textContent = next === 'how' ? 'Skip to the guide' : 'Skip to results';
      if (next === 'how') guide.open();
      window.scrollTo(0, places[next]);
      if (moved) {
        (next === 'how' ? area('how') : area('results')).focus({ preventScroll: true });
        area('status').textContent = next === 'how' ? 'How it works' : 'Search';
      }
    };
    // The guide's own element has another id than its address, so that opening the address does not scroll to it.
    skip.addEventListener('click', (event) => {
      if (page !== 'how') return;
      event.preventDefault();
      area('how').focus();
    });
    const route = (moved) => show(guide && pageOf(location.hash) === 'how' ? 'how' : 'search', moved);
    window.addEventListener('hashchange', () => route(true));
    window.addEventListener('popstate', () => route(true));
    // Something on the guide that needs the search: go back to it, as a new step in the history.
    const searchPage = () => {
      if (page === 'search') return;
      history.pushState(null, '', location.pathname + location.search);
      route(true);
    };
    route(false);

    const on = (type, handle) => document.addEventListener(type, (e) => handle(e.detail));
    const onSearch = (type, handle) => on(type, (detail) => {
      searchPage();
      handle(detail);
    });
    // A new list replaces the old one where the page stands: if that is below the list's top, bring the top back.
    const fromTop = () => {
      if (area('results').getBoundingClientRect().top < 0) area('results').scrollIntoView({ block: 'start' });
    };
    let words = ''; // the last word search: its words are marked in the text of the frames opened after it
    on('announce', (text) => { area('status').textContent = text; });
    on('toast', (text) => toast.show(text));
    onSearch('search', (query) => {
      words = '';
      viewer.close(false);
      answers.setQuery(query);
      fromTop();
      if (query.task === 'trake') {
        events.open(query);
      } else {
        results.load(async () => ({
          title: query.id ?? 'Your search',
          badge: TASK_NAMES[query.task],
          subtitle: query.text,
          echo: true,
          frames: await provider.search(query),
          empty: 'No result is recorded for this query.',
        }));
      }
    });
    onSearch('search-keyword', (text) => {
      words = text;
      viewer.close(false);
      fromTop();
      results.load(async () => ({
        title: `Words “${text}”`,
        subtitle: 'Frames that show or say the most of these words come first. Accents are optional.',
        frames: await provider.searchKeyword(text),
        empty: 'None of these words is read on screen or heard in speech. Try fewer words.',
      }));
    });
    onSearch('show-similar', (frame) => {
      fromTop();
      results.load(async () => ({
        title: `Like ${frame.videoId} · ${clock(frame.time)}`,
        subtitle: 'Frames that look like this one, most alike first.',
        frames: await provider.similar(frame),
        empty: 'No similar frames are recorded for this one.',
      }));
    });
    // One video, two ways: cut into scenes (when the provider has the words and speech), or every frame in a grid.
    const frames = (videoId, focusSwitch = false) => {
      fromTop();
      return results.load(async () => ({
        title: videoId,
        subtitle: 'Every frame of the video that has a picture, in time order.',
        frames: await provider.videoFrames(videoId),
        ranked: false,
        videoId: can.transcript ? videoId : null,
        focusSwitch,
        empty: 'This video has no frames.',
      }));
    };
    const scenes = ({ videoId, frame = null, focusSwitch = false }) => {
      if (!can.transcript) return frames(videoId, focusSwitch);
      fromTop();
      return anatomy.open(videoId, { frame, focusSwitch });
    };
    onSearch('browse-video', scenes);
    onSearch('browse-frames', ({ videoId, focusSwitch }) => frames(videoId, focusSwitch));
    onSearch('look-inside', ({ videoId }) => {
      viewer.close(false);
      scenes({ videoId });
    });
    // The guide asks for a search as if its words were typed, or a sample query as if it were clicked.
    onSearch('try-words', ({ text }) => queries.searchWords(text));
    onSearch('open-query', ({ id }) => queries.choose(id));
    onSearch('open-frame', (frame) => viewer.show(frame, words));
    on('add-answer', ({ frames: chain }) => answers.add(chain));
  }
}
