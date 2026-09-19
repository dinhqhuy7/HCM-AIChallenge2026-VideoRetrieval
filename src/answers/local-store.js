/**
 * One JSON value kept in browser storage. Storage may be blocked (private
 * windows, sandboxed previews); the page then keeps working and forgets on reload.
 */
export class LocalStore {
  #key;
  #storage;

  constructor(key, storage = LocalStore.browserStorage()) {
    this.#key = key;
    this.#storage = storage;
  }

  /** Even reading `localStorage` can throw where storage is blocked. */
  static browserStorage() {
    try {
      return globalThis.localStorage ?? null;
    } catch {
      return null;
    }
  }

  read(fallback) {
    try {
      const raw = this.#storage?.getItem(this.#key);
      return raw == null ? fallback : JSON.parse(raw);
    } catch {
      return fallback;
    }
  }

  write(value) {
    try {
      this.#storage?.setItem(this.#key, JSON.stringify(value));
    } catch {
      // Full or blocked storage: the answers still live in memory for this visit.
    }
  }
}
