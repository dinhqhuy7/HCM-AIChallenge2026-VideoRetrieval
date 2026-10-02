"""One query, typed into up to four boxes, to the rows that get submitted."""
from __future__ import annotations

from src.config import MissingSetting
from src.fusion.rank_fusion import ReciprocalRankFusion
from src.fusion.shaping import ResultShaper
from src.retrieval.hits import Frame
from src.retrieval.lanes import Lane


class SearchEngine:
    def __init__(self, lanes: dict[str, Lane], fusion: ReciprocalRankFusion | None,
                 shaper: ResultShaper, depth: int) -> None:
        self.lanes = lanes
        self.fusion = fusion
        self.shaper = shaper
        self.depth = depth

    def search(self, queries: dict[str, str]) -> list[Frame]:
        """``queries`` maps a lane name to the text typed into its box; empty boxes are skipped.
        One box answers on its own; two or more are combined with RRF."""
        asked = {lane: text for lane, text in queries.items() if text and text.strip()}
        if not asked:
            raise ValueError("type something into at least one box")
        missing = sorted(set(asked) - set(self.lanes))
        if missing:
            raise ValueError(f"no lane for {missing}; this index has {sorted(self.lanes)}")
        if len(asked) > 1 and self.fusion is None:
            raise MissingSetting("set `fusion.rrf_k` to combine lanes (the RRF paper uses 60)")
        rankings = [self.lanes[lane].search(text, self.depth) for lane, text in asked.items()]
        return self.shaper.shape(rankings[0] if len(rankings) == 1 else self.fusion.fuse(rankings))
