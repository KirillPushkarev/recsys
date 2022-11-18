import random

from .random import Random
from .recommender import Recommender
from ..utils import from_bytes


class Collaborative(Recommender):
    def __init__(self, recommendations_redis, track_redis):
        self.recommendations_redis = recommendations_redis
        self.fallback = Random(track_redis)

    def recommend_next(self, user: int, prev_track: int, prev_track_time: float) -> int:
        recommendations = self.recommendations_redis.get(user)
        if recommendations is not None:
            return random.choice(list(from_bytes(recommendations)))
        else:
            return self.fallback.recommend_next(user, prev_track, prev_track_time)
