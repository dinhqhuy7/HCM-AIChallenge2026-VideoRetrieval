import { clock } from './clock.js';

/**
 * The recorded answers of a TRAKE query, laid out for drawing: the chains grouped by the video they
 * lie in, and for every event of a video the frames its chains use and the frame that matched the
 * event best on its own. Plain functions over frames, so a view only has to draw what they return.
 */

/** Where `frame` stands in an event's own ranking, counted from 1 (0 when it is not in it). */
const rankIn = (ranking, frame) => ranking.findIndex((candidate) => candidate.key === frame.key) + 1;

/** "E1", "E1 and E2", "E1, E2 and E3". */
const named = (events) => (events.length < 2 ? events.join('') : `${events.slice(0, -1).join(', ')} and ${events.at(-1)}`);

/** The seconds from one event to the next, as a label: "+1.2 s", "+1:12", "−1.2 s". */
export const gapLabel = (gap) => `${gap < 0 ? '−' : '+'}${Math.abs(gap) < 100 ? `${Math.abs(gap).toFixed(1)} s` : clock(Math.abs(gap))}`;

/**
 * `chains` (a frame per event, in order) and `stages` (each event's ranking over all videos, best
 * first) as groups, one per video, in the order the videos first appear. A group is
 * `{ videoId, chains, events, window }`:
 * - `chains`: `{ number, frames, gaps, span }`, `number` counting from 1 in the whole list, `gaps` the
 *   seconds from each event to the next, `span` the seconds from the first event to the last;
 * - `events`: for each event `{ frames, best }`: `frames` are the different frames the group's chains
 *   use for it, each `{ frame, rank, chains }` (`chains` the numbers of the chains that use it), and
 *   `best` is the highest-ranked frame of the event that lies in this video, `{ frame, rank }`, or null;
 * - `window`: `{ from, to }`, the seconds that hold every frame above, with some room around them.
 */
export function lay({ chains, stages }) {
  const groups = new Map();
  chains.forEach((frames, i) => {
    const [first] = frames;
    if (!first) return;
    if (!groups.has(first.videoId)) groups.set(first.videoId, { videoId: first.videoId, chains: [] });
    groups.get(first.videoId).chains.push({
      number: i + 1,
      frames,
      gaps: frames.slice(1).map((frame, e) => frame.time - frames[e].time),
      span: frames.at(-1).time - first.time,
    });
  });
  return [...groups.values()].map((group) => {
    const events = Array.from({ length: Math.max(...group.chains.map((chain) => chain.frames.length)) }, (_, e) => {
      const ranking = stages[e] ?? [];
      const used = new Map();
      for (const chain of group.chains) {
        const frame = chain.frames[e];
        if (!frame) continue;
        if (!used.has(frame.key)) used.set(frame.key, { frame, rank: rankIn(ranking, frame), chains: [] });
        used.get(frame.key).chains.push(chain.number);
      }
      const top = ranking.find((frame) => frame.videoId === group.videoId);
      return { frames: [...used.values()], best: top ? { frame: top, rank: rankIn(ranking, top) } : null };
    });
    const times = events.flatMap((event) => [...event.frames.map((used) => used.frame.time), ...(event.best ? [event.best.frame.time] : [])]);
    const low = Math.min(...times);
    const high = Math.max(...times);
    const room = Math.max((high - low) * 0.08, 2);
    const from = Math.max(0, low - room);
    return { ...group, events, window: { from, to: Math.max(high + room, from + 10) } };
  });
}

/**
 * What the best frame of each event on its own says about the chain: when those frames are not in
 * time order, a chain has to settle for others; when they are, the chain is just them. The first
 * chain of the group is the one described. Null when there is nothing to say.
 */
export function orderNote(group) {
  const best = group.events.map((event) => event.best);
  if (best.some((entry) => entry === null)) return null;
  const [chain] = group.chains;
  for (let e = 1; e < best.length; e += 1) {
    if (best[e].frame.time >= best[e - 1].frame.time) continue;
    const settled = chain.frames.flatMap((frame, i) => {
      const used = group.events[i].frames.find((entry) => entry.frame.key === frame.key);
      return frame.key !== best[i].frame.key && used?.rank ? [`the one ranked #${used.rank} for E${i + 1} (${clock(frame.time)})`] : [];
    });
    return `Taken one at a time, the best frame of E${e + 1} in this video (${clock(best[e].frame.time)}) comes before that of E${e} `
      + `(${clock(best[e - 1].frame.time)}). A chain has to keep the order, so chain ${chain.number} takes ${settled.length ? named(settled) : 'other frames'}.`;
  }
  return chain.frames.every((frame, e) => frame.key === best[e].frame.key)
    ? `Taken one at a time, the best frame of each event in this video is already in time order, so chain ${chain.number} is made of them.`
    : null;
}

/** How much the chains of one video repeat each other, as one sentence; null for a single chain. */
export function overlapNote(group) {
  const total = group.chains.length;
  if (total < 2) return null;
  const counts = group.events.map((event) => event.frames.length);
  const same = counts.flatMap((count, e) => (count === 1 ? [`E${e + 1}`] : []));
  const varied = counts.flatMap((count, e) => (count > 1 ? [`E${e + 1} has ${count}`] : []));
  if (!varied.length) return `These ${total} chains use the same frame for every event.`;
  const every = total === 2 ? 'both chains' : `all ${total} chains`;
  const kept = same.length ? `${named(same)} ${same.length === 1 ? 'uses' : 'use'} the same frame in ${every}` : `No event keeps the same frame in ${every}`;
  return `${kept}; ${named(varied)} different frames.`;
}
