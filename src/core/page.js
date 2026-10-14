/** The page a location hash asks for: `#how-it-works` is the guide, anything else is the search. */
export const pageOf = (hash) => (hash === '#how-it-works' ? 'how' : 'search');
