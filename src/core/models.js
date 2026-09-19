/** The competition's three tasks, by the names users see. */
export const TASK_NAMES = { kis: 'KIS', qa: 'Q&A', trake: 'TRAKE' };

/** One moment of one video. Searches return these; answers name them. */
export class Frame {
  /** `image` is `{ url }`, or `{ url, cell }` when the picture is one cell of a sprite strip. */
  constructor(videoId, frameIdx, time, image) {
    Object.assign(this, { videoId, frameIdx, time, image });
  }

  get key() {
    return `${this.videoId}/${this.frameIdx}`;
  }
}

/** A source video and where to watch it from a given second. */
export class Video {
  constructor(id, { title, youtube, embed }) {
    Object.assign(this, { id, title, youtube, embed });
  }

  watchUrl(time) {
    return `https://www.youtube.com/watch?v=${this.youtube}&t=${Math.floor(time)}s`;
  }

  embedUrl(time) {
    return `https://www.youtube.com/embed/${this.youtube}?start=${Math.floor(time)}&autoplay=1`;
  }
}

/** What the user asked: one description, or one per event for TRAKE. */
export class Query {
  constructor({ id = null, round = null, task, text, stages = [] }) {
    Object.assign(this, { id, round, task, text, stages });
  }
}

/** One line of a submission, in the competition's column order. */
export class Answer {
  constructor(task, frames, text = '') {
    Object.assign(this, { task, frames, text });
  }

  cells() {
    const [{ videoId, frameIdx }] = this.frames;
    if (this.task === 'trake') return [videoId, ...this.frames.map((f) => f.frameIdx)];
    return this.task === 'qa' ? [videoId, frameIdx, this.text] : [videoId, frameIdx];
  }
}

/** The features a provider offers. Views show only these, so none checks the provider type. */
export class Capabilities {
  constructor({ freeText = false, keyword = false, similar = false, events = false, browse = false,
    transcript = false } = {}) {
    Object.assign(this, { freeText, keyword, similar, events, browse, transcript });
  }
}
