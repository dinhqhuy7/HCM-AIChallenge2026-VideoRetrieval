import { VideoPlayer } from './video-player.js';
import { View, clock, el, thumbnail } from './view.js';

/**
 * One frame up close: its neighbours in the video, the words on screen and
 * spoken around it, and the actions the provider supports. Asks the page to
 * act through `add-answer`, `show-similar` and `browse-video` events.
 */
export class FrameViewer extends View {
  static RADIUS = 2;
  static SPEECH_WINDOW = 10;
  #provider;
  #can;

  constructor(element, provider, capabilities) {
    super(element);
    this.#provider = provider;
    this.#can = capabilities;
  }

  show(frame) {
    return this.load(async () => {
      const [frames, transcript] = await Promise.all([
        this.#provider.videoFrames(frame.videoId),
        this.#can.transcript && this.#provider.transcript(frame.videoId),
      ]);
      const at = frames.findIndex((f) => f.key === frame.key);
      const neighbors = at < 0 ? [] : frames.slice(Math.max(0, at - FrameViewer.RADIUS), at + FrameViewer.RADIUS + 1);
      return { frame, neighbors, transcript };
    });
  }

  render({ frame, neighbors, transcript }) {
    const player = new VideoPlayer(el('div', { className: 'player' }));
    const play = () => player.load(async () => ({
      video: await this.#provider.video(frame.videoId), time: frame.time,
    }));
    this.draw(
      el('h2', {}, `${frame.videoId} · ${clock(frame.time)} · frame ${frame.frameIdx}`),
      thumbnail(frame),
      el('div', { className: 'actions' },
        button('Add to answers', () => this.emit('add-answer', { frames: [frame] })),
        button('Play video', play),
        this.#can.similar && button('More like this', () => this.emit('show-similar', frame)),
        this.#can.browse && button('Whole video', () => this.emit('browse-video', frame.videoId))),
      el('div', { className: 'row' }, neighbors.map((n) => this.frameCard(n))),
      transcript && this.#words(transcript, frame.time),
      player.element,
    );
  }

  #words({ onScreen, speech }, time) {
    const shown = onScreen.find((line) => line.time <= time && time <= line.until)?.text;
    const heard = speech.filter((line) => Math.abs(line.time - time) <= FrameViewer.SPEECH_WINDOW);
    return el('dl', { className: 'words' },
      shown ? [el('dt', {}, 'OCR'), el('dd', {}, shown)] : null,
      heard.length ? [el('dt', {}, 'Transcript'), heard.map((l) => el('dd', {}, `${clock(l.time)} ${l.text}`))] : null);
  }
}

const button = (label, onclick) => el('button', { onclick }, label);
