import random
from typing import Union

import numpy as np
import torch
from flask_redis import Redis
from redis.client import StrictRedis

from .random import Random
from .recommender import Recommender
from ..model.model import ContextualRanker
from ..utils import from_bytes, to_bytes


class ContextualV2(Recommender):
    """
    Recommend tracks closest to the previous one and to the current user.
    Fall back to the random recommender if no
    recommendations found for the track.
    """

    def __init__(self, session_redis: Union[Redis, StrictRedis], model: ContextualRanker,
                 track_embeddings: torch.Tensor, top_tracks_per_user=40):
        self.session_redis = session_redis
        self.model = model
        self.track_embeddings = track_embeddings
        self.top_tracks_per_user = top_tracks_per_user

        self.fallback = Random(session_redis)

    def recommend_next(self, user_id: int, prev_track_id: int, prev_track_time: float) -> int:
        if self.session_redis.exists(user_id):
            recommendations = from_bytes(self.session_redis.get(user_id))
        else:
            recommendations = self.calculate_recommendations(user_id, prev_track_id)
            self.session_redis.set(user_id, to_bytes(recommendations))

        return random.choice(list(recommendations))

    def calculate_recommendations(self, user: int, prev_track: int) -> list:
        with torch.no_grad():
            context_embedding = self.model.get_context_embedding(
                torch.tensor(user),
                torch.tensor(prev_track)
            )
            context_embedding = context_embedding.cpu().numpy()

            neighbours = np.argpartition(-np.dot(self.track_embeddings, context_embedding), self.top_tracks_per_user)[:self.top_tracks_per_user]
            recommendations = neighbours.tolist()

            return recommendations
