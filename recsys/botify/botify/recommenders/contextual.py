from typing import Union

from flask_redis import Redis
from redis.client import StrictRedis

from .random import Random
from .recommender import Recommender
import random

from ..utils import from_bytes


class Contextual(Recommender):
    """
    Recommend tracks closest to the previous one.
    Fall back to the random recommender if no
    recommendations found for the track.
    """

    def __init__(self, tracks_redis: Union[Redis, StrictRedis]):
        self.tracks_redis = tracks_redis
        self.fallback = Random(tracks_redis)

    def recommend_next(self, user: int, prev_track: int, prev_track_time: float) -> int:
        previous_track_raw_data = self.tracks_redis.get(prev_track)
        if previous_track_raw_data is None:
            return self.fallback.recommend_next(user, prev_track, prev_track_time)

        previous_track = from_bytes(previous_track_raw_data)
        recommendations = previous_track.recommendations
        if not recommendations:
            return self.fallback.recommend_next(user, prev_track, prev_track_time)

        return random.choice(list(recommendations))
