import { HttpProvider } from './http/http-provider.js';
import { StaticProvider } from './static/static-provider.js';

/** Builds the provider that config.js names. A new data source is one more entry in `KINDS`. */
export class ProviderFactory {
  static KINDS = { static: StaticProvider, http: HttpProvider };

  static create({ provider, baseUrl }) {
    const Kind = ProviderFactory.KINDS[provider];
    if (!Kind) {
      throw new Error(`unknown provider "${provider}": use ${Object.keys(ProviderFactory.KINDS).join(' or ')}`);
    }
    return new Kind(baseUrl);
  }
}
