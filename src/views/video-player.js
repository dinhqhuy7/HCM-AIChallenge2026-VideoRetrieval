import { View, el } from './view.js';

/** The source video from a frame's moment; a link only, when the owner blocks embedding. */
export class VideoPlayer extends View {
  render({ video, time }) {
    const player = video.embed
      ? el('iframe', { src: video.embedUrl(time), title: video.title, allow: 'autoplay; encrypted-media' })
      : el('p', { className: 'message' }, 'The owner does not allow this video to play here.');
    this.draw(
      el('h3', {}, video.title),
      player,
      el('a', { href: video.watchUrl(time), target: '_blank', rel: 'noopener' }, 'Open on YouTube'),
    );
  }
}
