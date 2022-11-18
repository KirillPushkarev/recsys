import random
from typing import List, Union

from flask_redis import Redis
from redis.client import StrictRedis

from .random import Random
from .recommender import Recommender


class TopPop(Recommender):
    def __init__(self, tracks_redis: Union[Redis, StrictRedis], top_tracks: List[int]):
        self.random = Random(tracks_redis)
        self.top_tracks = top_tracks

    def recommend_next(self, user: int, prev_track: int, prev_track_time: float) -> int:
        if self.top_tracks:
            return random.choice(list(self.top_tracks))
        else:
            return self.random.recommend_next(user, prev_track, prev_track_time)
