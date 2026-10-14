# Architecture

A video retrieval system has three parts. This repository is the third; the
first two are yours to build, and which models they use is your choice.

```mermaid
flowchart LR
  subgraph Offline[Offline, once per collection]
    V[Videos] --> S[Split into scenes] --> K[Pick key frames]
    K --> E[Extract evidence: picture, on-screen text, speech]
    E --> I[Index]
  end
  subgraph Online[Online, per query]
    Q[Query] --> R[Search each evidence] --> C[Combine into one ranking]
  end
  I --> R
  C --> P[This page]
```

| Stage | Takes | Produces |
|---|---|---|
| Split into scenes | a video | scene boundaries |
| Pick key frames | a scene | the frames worth indexing, with their times |
| Extract evidence | a frame, or the audio around it | a picture vector, the text on screen, the words spoken |
| Index | all evidence | something each kind of search can query quickly |
| Search each evidence | the query | one ranked list of frames per kind |
| Combine | several ranked lists | one list, best first |

TRAKE asks for several events in order: search each event, then keep chains
of frames from one video whose times follow the events' order.

## The page

The page only displays. Everything it shows comes through one abstract class,
`SearchProvider`; views receive it and never know which subclass they hold.

```mermaid
classDiagram
  SearchProvider <|-- StaticProvider
  SearchProvider <|-- HttpProvider
  StaticProvider *-- StaticDataset
  StaticProvider *-- KeywordIndex
  SearchProvider ..> QueryCatalog : catalog()
  HttpProvider *-- ApiClient
  View <|-- QueryPanel
  View <|-- ResultGrid
  View <|-- EventChainView
  View <|-- FrameViewer
  View <|-- VideoAnatomy
  View <|-- StartPanel
  View <|-- HowItWorks
  View <|-- VideoPlayer
  View <|-- AnswerPanel
  App --> SearchProvider
  App --> View
  AnswerPanel --> AnswerList
  AnswerList --> LocalStore
```

- `App` builds the provider named in `config.js`, creates the views and routes
  their events (`search`, `open-frame`, `add-answer`, …). No view knows another.
  Views that share the results panel (the grid, the event chains, a video taken
  apart) do not know each other either: `View.load` lets the newest request into
  an element win, so a slow answer never draws over a newer one.
- The page has two parts, the search and a guide on how it works (`HowItWorks`,
  offered when `config.how` names its examples). The address says which is shown
  (`#how-it-works` is the guide), the part left keeps its state, and what the
  guide lets you try (`look-inside`, `try-words`, `open-query`, `open-frame`, …) goes
  to the search as a new step of the history. Its examples are of two kinds and
  say so: data read through the provider, and the main branch's own output
  (`src/core/main-output.js`, copied from its guides).
- `capabilities()` tells views which features exist, so no view checks which
  provider it has.
- `core/` holds the plain data (`Frame`, `Video`, `Query`, `Answer`) and the
  Vietnamese text folding shared with the data build.
- Answers are stored per query in the browser and downloaded as the
  competition's CSV: `video,frame` for KIS, `video,frame,answer` for Q&A,
  `video,frame1,frame2,…` for TRAKE.

To plug in your system, implement [the API](api.md); to publish a static demo
of it instead, write [these files](data-format.md).
