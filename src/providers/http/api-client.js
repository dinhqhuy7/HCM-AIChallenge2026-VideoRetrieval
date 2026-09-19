/** JSON over HTTP against one base URL. Errors name the request and the status. */
export class ApiClient {
  #base;
  #fetch;

  /** The default wraps `fetch`: browsers reject it when called as another object's method. */
  constructor(base, fetchFn = (url, init) => fetch(url, init)) {
    this.#base = base;
    this.#fetch = fetchFn;
  }

  get(path, { optional = false } = {}) {
    return this.#send(path, { method: 'GET' }, optional);
  }

  post(path, body) {
    const init = { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) };
    return this.#send(path, init, false);
  }

  /** An `optional` endpoint that answers 404 is not an error: the backend simply lacks it. */
  async #send(path, init, optional) {
    const url = new URL(path, this.#base);
    const response = await this.#fetch(url, init);
    if (optional && response.status === 404) return null;
    if (!response.ok) throw new Error(`${init.method} ${url.pathname}: HTTP ${response.status}`);
    return response.json();
  }
}
