import importlib.util
import itertools
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

HAVE_NUMPY = importlib.util.find_spec("numpy") is not None


def frames(times, video="V"):
    return [Frame(video, number, f"{video}_{number:06d}", number, time) for number, time in enumerate(times)]


if HAVE_NUMPY:
    import numpy as np

    from src.retrieval.hits import Frame
    from src.retrieval.trake import ChainAligner, ChainRules, TrakeSearch


def brute_force(frames, scores, rules):
    """Every chain the rules allow, scored; the best total (or None when there is none)."""
    events, count = scores.shape
    best = None
    for path in itertools.product(range(count), repeat=events):
        times = [frames[p].time_ms for p in path]
        ok = all((later > earlier if rules.order == "strict" and not rules.min_gap_ms else later >= earlier)
                 and (rules.min_gap_ms is None or later - earlier >= rules.min_gap_ms)
                 and (rules.max_gap_ms is None or later - earlier <= rules.max_gap_ms)
                 for earlier, later in zip(times, times[1:]))
        if ok:
            total = sum(float(scores[event, position]) for event, position in enumerate(path))
            best = total if best is None else max(best, total)
    return best


@unittest.skipUnless(HAVE_NUMPY, "needs numpy")
class ChainRulesTest(unittest.TestCase):
    def windows(self, times, **rules):
        return [list(part) for part in ChainRules(**rules).windows(np.array(times, dtype=np.int64))]

    def test_strict_moves_past_frames_shown_at_the_same_time(self):
        starts, ends = self.windows([0, 0, 100, 200])
        self.assertEqual(starts, [2, 2, 3, 4])
        self.assertEqual(ends, [4, 4, 4, 4])

    def test_loose_lets_one_frame_serve_two_events(self):
        starts, _ = self.windows([0, 0, 100, 200], order="loose")
        self.assertEqual(starts, [0, 0, 2, 3])

    def test_the_gaps_cut_the_window_on_both_sides(self):
        starts, _ = self.windows([0, 100, 500], min_gap_ms=200)
        self.assertEqual(starts, [2, 2, 3])
        _, ends = self.windows([0, 100, 500], max_gap_ms=150)
        self.assertEqual(ends, [2, 2, 3])

    def test_the_order_and_the_gaps_are_checked(self):
        with self.assertRaisesRegex(ValueError, "order must be"):
            ChainRules(order="any")
        with self.assertRaisesRegex(ValueError, "min_gap_ms must not be larger"):
            ChainRules(min_gap_ms=900, max_gap_ms=100)


@unittest.skipUnless(HAVE_NUMPY, "needs numpy")
class ChainAlignerTest(unittest.TestCase):
    def test_the_best_chain_is_not_the_best_frame_of_each_event(self):
        scores = np.array([[0.9, 0.5, 0.1], [0.95, 0.2, 0.3]])
        (best, *rest) = ChainAligner(ChainRules()).chains(frames([0, 100, 200]), scores)
        self.assertEqual([frame.frame_index for frame in best.frames], [0, 2])
        self.assertAlmostEqual(best.score, 1.2)
        self.assertEqual([round(frame.score, 2) for frame in best.frames], [0.9, 0.3])
        self.assertEqual(len(rest), 1)  # a chain may also start at frame 1
        self.assertAlmostEqual(rest[0].score, 0.8)

    def test_loose_lets_one_frame_answer_both_events(self):
        scores = np.array([[0.9, 0.5, 0.1], [0.95, 0.2, 0.3]])
        (best, *_) = ChainAligner(ChainRules(order="loose")).chains(frames([0, 100, 200]), scores)
        self.assertEqual([frame.frame_index for frame in best.frames], [0, 0])
        self.assertAlmostEqual(best.score, 1.85)

    def test_a_video_too_short_for_the_events_has_no_chain(self):
        aligner = ChainAligner(ChainRules())
        self.assertEqual(aligner.chains(frames([0]), np.array([[0.9], [0.9]])), [])
        far_apart = ChainAligner(ChainRules(max_gap_ms=50))
        self.assertEqual(far_apart.chains(frames([0, 5000]), np.array([[0.9, 0.1], [0.1, 0.9]])), [])

    def test_the_scores_must_match_the_frames(self):
        with self.assertRaisesRegex(ValueError, "3 columns of scores for 2 frames"):
            ChainAligner(ChainRules()).chains(frames([0, 100]), np.zeros((2, 3)))

    def test_it_agrees_with_trying_every_chain(self):
        rng = random.Random(4)
        for case in range(200):
            times = sorted(rng.randrange(0, 1000) for _ in range(rng.randrange(2, 7)))
            events = rng.randrange(2, 4)
            scores = np.array([[round(rng.random(), 3) for _ in times] for _ in range(events)])
            rules = ChainRules(order=rng.choice(["strict", "loose"]),
                               min_gap_ms=rng.choice([None, 0, 100]), max_gap_ms=rng.choice([None, 300, 900]))
            chains = ChainAligner(rules).chains(frames(times), scores)
            want = brute_force(frames(times), scores, rules)
            if want is None:
                self.assertEqual(chains, [], (times, rules))
            else:
                self.assertAlmostEqual(chains[0].score, want, places=6, msg=(times, rules))


class FakeLane:
    """Embeds each event as a one-hot vector and serves two short videos."""

    def __init__(self):
        self.videos = {"A": ([0, 100, 200], [[0.9, 0.1], [0.2, 0.8], [0.4, 0.7]]),
                       "B": ([0, 100], [[0.5, 0.2], [0.3, 0.6]])}
        self.index = self

    def embed(self, text):
        return np.array([1.0, 0.0]) if text == "first" else np.array([0.0, 1.0])

    def search(self, vector, limit, video_id=None):
        found = []
        for video, (times, rows) in self.videos.items():
            for number, (time, row) in enumerate(zip(times, rows)):
                found.append(Frame(video, number, f"{video}_{number:06d}", number, time, float(np.dot(vector, row))))
        return sorted(found, key=lambda frame: -frame.score)[:limit]

    def frames_of(self, video_id):
        times, rows = self.videos[video_id]
        return frames(times, video_id), np.array(rows, dtype=np.float32)


@unittest.skipUnless(HAVE_NUMPY, "needs numpy")
class TrakeSearchTest(unittest.TestCase):
    def search(self, rows=10, spread=False, rules=None):
        return TrakeSearch(FakeLane(), rules or ChainRules(), depth=10, rows=rows, spread=spread)

    def test_two_events_at_least(self):
        with self.assertRaisesRegex(ValueError, "at least two events"):
            self.search().search(["first"])

    def test_videos_are_ranked_by_their_best_frame_for_each_event(self):
        trake = self.search()
        self.assertEqual(trake.videos(np.array([[1.0, 0.0], [0.0, 1.0]])), ["A", "B"])  # 0.9 + 0.8 vs 0.5 + 0.6

    def test_every_candidate_video_gives_its_chains_best_first(self):
        chains = self.search().search(["first", "second"])
        self.assertEqual([(chain.video_id, [f.frame_index for f in chain.frames]) for chain in chains[:3]],
                         [("A", [0, 1]), ("B", [0, 1]), ("A", [1, 2])])  # 1.7, then 1.1, then 0.9
        self.assertAlmostEqual(chains[0].score, 1.7)
        self.assertEqual({chain.video_id for chain in chains}, {"A", "B"})

    def test_the_rows_are_cut_and_the_spread_takes_one_video_in_turn(self):
        self.assertEqual(len(self.search(rows=2).search(["first", "second"])), 2)
        spread = self.search(spread=True).search(["first", "second"])
        self.assertEqual([chain.video_id for chain in spread[:2]], ["A", "B"])


if __name__ == "__main__":
    unittest.main()
