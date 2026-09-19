# Backend API

To run this page on your own system, serve these endpoints and set
`config.js` to `{ provider: 'http', baseUrl: 'https://your-host/api/' }`.
Each endpoint backs one method of `src/providers/search-provider.js`.
Bodies are JSON; any status outside 2xx is shown to the user as an error.

A frame travels as:

```json
{ "video": "L21_V001", "frame": 1234, "time": 49.4, "image": "https://your-host/frames/L21_V001/1234.jpg" }
```

`frame` is the frame number in the source video, which is what a submission
names. Lists of frames are `{ "frames": [frame, …] }`, best first.

| Method | Endpoint | Returns |
|---|---|---|
| `capabilities()` | `GET capabilities` | `{ "freeText", "keyword", "similar", "events", "browse", "transcript" }`, each true or false |
| `catalog()` | `GET queries` | sample queries, as in [data-format.md](data-format.md); **404** if you have none |
| `search(query)` | `POST search` `{ "task", "text" }` | frames |
| `searchEvents(query)` | `POST events` `{ "text", "stages": ["…"] }` | `{ "stages": [[frame]], "chains": [[frame]] }` |
| `searchKeyword(text)` | `GET keyword?q=…` | frames holding those words on screen or in speech |
| `similar(frame)` | `GET frames/{video}/{frame}/similar` | frames |
| `video(id)` | `GET videos/{video}` | `{ "title", "youtube", "embed" }` |
| `videoFrames(id)` | `GET videos/{video}/frames` | frames of the video in time order |
| `transcript(id)` | `GET videos/{video}/transcript` | `{ "onScreen": [{ "time", "until", "text" }], "speech": [{ "time", "text" }] }` |

`task` is `kis`, `qa` or `trake`. For TRAKE, `stages` holds one description
per event, in order; each chain returns one frame per stage.

Report a feature as false in `capabilities` and the page hides it, so its
endpoint is never called. The page sends `freeText` searches only when that
flag is true: this is the one feature the static demo cannot offer.

Serve the API from the page's origin, or allow it with CORS.
