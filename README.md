# Video Retrieval Demo

A search page for the news videos of the HCM AI Challenge 2026 qualifier: find a
moment in hundreds of videos, collect answers, and download them in the
competition's submission format. A second page, **How it works**, follows a query
through the system documented on this repository's `main` branch.

**Try it:** https://dinhqhuy7.github.io/HCM-AIChallenge2026-VideoRetrieval/

The results are **recorded in advance** by the competition system; nothing is
computed in your browser. The `main` branch documents a system of the same kind
that you can run, and where this page shows output of that branch it says so.

## What you can do

**Search**

- Pick one of 70 qualifier queries (KIS, Q&A and TRAKE, in the organisers'
  Vietnamese), filter them, and see the frames the system ranked for it.
- Search the words shown on screen or spoken, in all 873 videos. Vietnamese
  accents are optional: `bao lu` finds the accented words too, and the words
  found are marked in the text.
- Open a frame to see its neighbours, the words on screen in its scene and the
  speech near it; play the video from that second, find similar frames, or look
  inside the video.
- Keep an answer list per query (at most 100 lines, as the competition accepts),
  see the CSV it will be, and download it.

**Look inside a video.** A video taken apart along its time line. A map shows
where its frames, the words read on screen and its speech fall; below it the video
is cut into stretches, each with its own frames, words and speech. `L30_V040` is a
good first one.

**TRAKE chains.** Each chain is drawn on its video's time line, one lane per
event, so the order and the gaps can be seen. Notes say what the best frame of
each event does on its own, and how much the chains of one video share.

**How it works.** Six steps, from shots and keyframes to the answer file, each
with a sentence, a link to its guide on the `main` branch, and examples. An
example is tagged **Recorded** (data of this page, made by the competition
system) or **Output of the main branch** (copied from its guides).

The page uses plain buttons and links with visible keyboard focus, follows the
system's light or dark setting, and works from a phone to a wide screen.

## Run it locally

```sh
python3 -m http.server 8000   # then open http://localhost:8000
```

Any static file server works; opening `index.html` from disk does not, because
browsers do not load modules from `file://`. The page is written for current
browsers (ES modules, CSS `color-mix`) and was checked in Firefox.

## Use it with your own system

The page is a front end for any retrieval backend. Implement the nine
endpoints in [docs/api.md](docs/api.md) and edit one line in `config.js`:

```js
export const config = { provider: 'http', baseUrl: 'https://your-host/api/' };
```

Or publish a static demo of your own system by writing the files described in
[docs/data-format.md](docs/data-format.md). How the parts fit together is in
[docs/architecture.md](docs/architecture.md); what each part of the page does,
and what to keep when changing it, is in [docs/interface.md](docs/interface.md).

`config.js` also takes `keywordExamples` (words offered under the word search),
`exampleVideos` (videos offered under "Look inside a video"), `how` (the examples
of the *How it works* page; leave it out and the page is not offered) and
`docsUrl` (where the documents of the system behind the page are, so the page can
link to them).

## Layout

```text
src/core/        plain data and functions: frames, stretches, chains, fusion, text folding
src/providers/   where data comes from: static files or your API
src/answers/     the answer list, its storage and the CSV export
src/views/       the page's parts; each owns one element
tests/           the tests, against a three-video example of the data format
data/ img/ sprites/   the recorded demo data
```

No build step and no dependencies: plain ES modules. Tests run with Node 20+:

```sh
node --test
```

## Data

Videos belong to their owners on YouTube and were provided for the challenge;
frames are shown here for demonstration only. Code: MIT, see [LICENSE](LICENSE).
