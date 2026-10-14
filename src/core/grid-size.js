/** How large the pictures of a result list are drawn: small, medium (the default) or large. */
export const GRID_SIZES = { s: 'Small', m: 'Medium', l: 'Large' };
export const DEFAULT_GRID_SIZE = 'm';

/** A stored or typed value as a size, so a corrupt or old entry never breaks the page. */
export const gridSize = (value) => (Object.hasOwn(GRID_SIZES, value) ? value : DEFAULT_GRID_SIZE);
