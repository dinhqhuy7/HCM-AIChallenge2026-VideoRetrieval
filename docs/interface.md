# The interface

What each part of the page does, so that a change keeps what is deliberate. The
code is in `src/views/`; each view owns one element and talks to the rest of the
page by events that bubble from it ([architecture.md](architecture.md)).

## Two parts, one address

The search and the guide are two parts of one page. `#how-it-works` in the
address shows the guide, anything else the search. A part that is left keeps its
content and its place on the page. What the guide offers to try (`look-inside`,
`try-words`, `open-query`, …) goes back to the search as a new step of the
history, so Back returns to the guide. Without `how` in `config.js` there is no
guide and no switch.

## The search

Three columns: the queries, the results, and the viewer above the answer list.
Under 1100 px they stack, the query panel folds into a line about what was asked,
and the viewer rises over the page like a sheet (Escape or its button closes it).

| Event | Sent by | What happens |
|---|---|---|
| `search` (a query) | query panel | the recorded ranking, or for TRAKE the chains; the marked words are cleared and the answer list is the query's |
| `search-keyword` (words) | query panel | frames that show or say the words, most first; the words are marked in the frames opened next |
| `show-similar` (frame) | viewer, guide | the frames that look like it |
| `browse-video` (`{ videoId, frame }`) | viewer, TRAKE card, switch | the video taken apart; scrolls to `frame` and marks it |
| `browse-frames` (`{ videoId }`) | the Scenes / All frames switch | every frame of the video, in a grid |
| `look-inside` (`{ videoId }`) | query panel, start panel, guide | puts the viewer away and opens the video |
| `open-frame` (frame) | any picture, pin or speech line | the viewer |
| `add-answer` (`{ frames }`) | viewer, chain row | one line in the answer list |
| `try-words`, `open-query` | guide | the word search as if typed, the sample query as if clicked |
| `announce`, `toast` | any view | a line for screen readers; a short note on screen |

A new list is shown from its top, and when two requests cross, the newest into an
element wins (`View.load`): a slow answer never draws over a newer one. A failure
is a plain sentence with *Try again*; the reason goes to the console.

## A video taken apart

`cut()` (`src/core/anatomy.js`) lays a video out from three files: the frames that
have a picture, the scenes in which words were read on screen, and the speech.
Every scene is a stretch of its own, holding the frames and speech that fall in
it. The time between two scenes had no words read; it becomes a stretch ("No text
read on screen") only when a frame or a spoken line falls there.

Above the stretches is a map with a lane for frames, words and speech, drawn to
the scale of the video. A band marks the stretch being read, which is the one at
a line just under the map, or the one the pointer or keyboard is on. Clicking the
map goes to that moment. The map is for the pointer and is hidden from assistive
technology; the list holds everything it shows.

## TRAKE

Each video that holds a chain gets a time line with a lane per event. A pin is a
frame a chain uses (filled for the first chain, outlined when only another chain
uses it); a dashed ring is the best-ranked frame of an event in that video, shown
when no chain takes it. Two notes are worked out from the recorded rankings
(`src/core/chains.js`): whether the best frames on their own are in time order,
and which frames the chains of the video share. A frame shows its rank in its
event's ranking over all videos.

## How it works

Six cards in the order of the `main` branch's README. Examples are of two kinds,
each tagged: data read through the provider, and output copied from the `main`
branch's guides, which lives in one file (`src/core/main-output.js`) with the
guide each piece came from. `how` in `config.js` names the video, frame, words and
queries the examples use; an example that cannot be read leaves its card without
it, not the page without cards.

## Look and feel

- Colours, spacing and radii are custom properties at the top of
  `assets/style.css`. Light and dark follow the system setting. Text is at least
  4.5:1 against its background, graphics at least 3:1.
- Every control is a real button or link with a name, and shows its focus.
  Motion is short, and switched off when the system asks for less (a jump to a
  stretch is then marked by a plain outline for a moment).
- Classes are global: before adding one, search `index.html` and `style.css`
  for it. The header's `.links` and a chain's `.chain` were each taken twice.

## Checking a change

Run `node --test`, open the page from a static server, and look at it about 420,
900 and 1400 px wide in both themes. Look at the states as well as the content:
loading (grey tiles), failure, empty, and a long video (`L22_V016` has 461
stretches; `L25_V054` has a stretch of 606 speech lines).
