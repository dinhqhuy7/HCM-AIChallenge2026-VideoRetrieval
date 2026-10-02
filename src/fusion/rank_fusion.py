"""Reciprocal Rank Fusion of shot rankings.

    score(shot) = sum over the rankings r that hold it of  1 / (k + rank_r(shot))

Cormack, Clarke and Buettcher, "Reciprocal Rank Fusion outperforms Condorcet and individual
Rank Learning Methods", SIGIR 2009. Only the ranks are used, so lanes whose scores live on
different scales (cosine similarity, BM25) are combined without calibrating them. The paper
fixed k = 60 in a pilot run, where it "was near-optimal, but ... the choice was not critical".
"""
from __future__ import annotations

from src.retrieval.hits import ShotHit


class ReciprocalRankFusion:
    def __init__(self, k: float) -> None:
        """``k`` sets how much the top of each list outweighs the rest; there is no default
        here because it is a choice. The paper uses 60."""
        if k is None or k < 0:
            raise ValueError("fusion.rrf_k must be 0 or more (the paper uses 60)")
        self.k = float(k)

    def fuse(self, rankings: list[list[ShotHit]]) -> list[ShotHit]:
        """One ranking of shots, best first. A shot keeps the frame, and the other frames, of
        the ranking that placed it highest; ties are settled by that rank, then by the shot."""
        shares: dict[tuple[str, int], list[float]] = {}
        best: dict[tuple[str, int], tuple[int, ShotHit]] = {}
        for ranking in rankings:
            for rank, hit in enumerate(ranking, start=1):
                shares.setdefault(hit.shot, []).append(1.0 / (self.k + rank))
                if hit.shot not in best or rank < best[hit.shot][0]:
                    best[hit.shot] = (rank, hit)
        # Add each shot's shares in the same order: two shots found at the same ranks then score
        # exactly alike, and the tie is settled below instead of by the rounding.
        scores = {shot: sum(sorted(found)) for shot, found in shares.items()}
        order = sorted(scores, key=lambda shot: (-scores[shot], best[shot][0], shot))
        return [ShotHit(best[shot][1].frame, scores[shot], best[shot][1].others) for shot in order]
