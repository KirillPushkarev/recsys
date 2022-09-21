import random
from typing import List
from .random import Random
from .recommender import Recommender


class TopPop(Recommender):
    def __init__(self, tracks_redis, top_tracks: List[int]):
        self.random = Random(tracks_redis)
        self.top_tracks = top_tracks

    # TODO Seminar 3 step 3: Implement TopPop recommender.
    #  Well, so far we uploaded top tracks to our catalog, now we need to recommend these tracks.
    #  This step is quite simple as you just need to return random track from the list.
    #  Make sure you don't try to take elements from the empty list!
    #  In case there are no top tracks, it is important to implement fallback recommender.

    def recommend_next(self, user: int, prev_track: int, prev_track_time: float) -> int:

        # your code here

        return self.random.recommend_next(user, prev_track, prev_track_time)
