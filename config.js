/**
 * The page's data source. For your own backend: { provider: 'http', baseUrl: 'https://your-host/api/' }.
 * `keywordExamples` are words offered under the word search; leave them out when yours has other data.
 * `exampleVideos` are videos offered under "Look inside a video", each with the reason to open it.
 * `how` names the examples of the "How it works" page: `video` (whose frames, text and speech the steps
 * follow), `titleFrame` (the number of one of its frames, a title card), `words` (a word search to try),
 * `ranked` (a sample query whose recorded ranking is shown) and `chain` (a TRAKE query whose chain is shown).
 * Leave it out and the page is not offered.
 * `docsUrl` is where the documents of the system behind the page are, with a trailing slash; the page
 * links to them where it explains what it shows. Leave it out and those links are not drawn.
 */
export const config = {
  provider: 'static',
  baseUrl: './',
  keywordExamples: ['bao lu', 'london zoo', 'xuat khau', 'phong van'],
  exampleVideos: [
    { id: 'L30_V040', note: 'The video the guides on the main branch use as their example: a news report.' },
    { id: 'L24_V040', note: 'A short clip with one line of speech and almost no text.' },
  ],
  how: { video: 'L30_V040', titleFrame: 158, words: 'xuat khau', ranked: 'r1-p1-4', chain: 'r2-p2-21' },
  docsUrl: 'https://github.com/dinhqhuy7/HCM-AIChallenge2026-VideoRetrieval/blob/main/docs/',
};
