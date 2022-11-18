import random
from typing import Union

from flask_redis import Redis
from redis.client import StrictRedis

from .random import Random
from .recommender import Recommender
from ..utils import from_bytes


class StickyArtist(Recommender):
    def __init__(self, tracks_redis: Union[Redis, StrictRedis], artists_redis: Union[Redis, StrictRedis]):
        self.fallback = Random(tracks_redis)
        self.tracks_redis = tracks_redis
        self.artists_redis = artists_redis

    def recommend_next(self, user: int, prev_track: int, prev_track_time: float) -> int:
        track_data = self.tracks_redis.get(prev_track)
        if track_data is not None:
            track = from_bytes(track_data)
        else:
            raise ValueError(f"Track not found: {prev_track}")

        artist_data = self.artists_redis.get(track.artist)
        if artist_data is not None:
            artist_tracks = from_bytes(artist_data)
        else:
            raise ValueError(f"Artist not found: {prev_track}")

        index = random.randint(0, len(artist_tracks) - 1)
        return artist_tracks[index]
