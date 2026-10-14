/**
 * Reciprocal Rank Fusion (Cormack, Clarke and Büttcher, SIGIR 2009): the score of a shot is the sum,
 * over the lanes, of 1 / (k + its rank in that lane), ranks counting from 1. A lane that did not
 * return the shot (`null`) adds nothing. Only ranks are used, so scores of different kinds never
 * have to be put on one scale.
 */
export const rrf = (k, ranks) => ranks.reduce((sum, rank) => sum + (rank == null ? 0 : 1 / (k + rank)), 0);
