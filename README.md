# Video Retrieval Demo

A search page for the news videos of the HCM AI Challenge 2026 qualifier:
find a moment in hundreds of videos, collect answers, and download them in the
competition's submission format.

**Try it:** https://dinhqhuy7.github.io/HCM-AIChallenge2026-VideoRetrieval/

## What you can do

- Pick one of 70 qualifier queries (KIS, Q&A, TRAKE, in the organisers'
  Vietnamese) and see the frames the system ranked, recorded in advance.
- Search the words shown on screen or spoken, in all 873 videos. Vietnamese
  accents are optional: `bao lu` finds the accented words too.
- Open a frame to see its neighbours and the words around it, play the video
  from that second, find similar frames, or browse the whole video.
- Keep an answer list per query and download it as CSV.

## Run it locally

```sh
python3 -m http.server 8000   # then open http://localhost:8000
```

Any static file server works; opening `index.html` from disk does not,
because browsers do not load modules from `file://`.

## Use it with your own system

The page is a front end for any retrieval backend. Implement the nine
endpoints in [docs/api.md](docs/api.md) and edit one line in `config.js`:

```js
export const config = { provider: 'http', baseUrl: 'https://your-host/api/' };
```

Or publish a static demo of your own system by writing the files described in
[docs/data-format.md](docs/data-format.md). How the parts fit together is in
[docs/architecture.md](docs/architecture.md).

## Layout

```text
src/core/        plain data and Vietnamese text folding
src/providers/   where data comes from: static files or your API
src/answers/     the answer list, its storage and the CSV export
src/views/       the page's parts; each owns one element
data/ img/ sprites/   the recorded demo data
```

No build step and no dependencies: plain ES modules. Tests run with Node 20+:

```sh
node --test
```

## Data

Videos belong to their owners on YouTube and were provided for the challenge;
frames are shown here for demonstration only. Code: MIT, see [LICENSE](LICENSE).
