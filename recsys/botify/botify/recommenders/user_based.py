from .random import Random
from .recommender import Recommender


# TODO Seminar 3 step 2: Implement UserBased recommender
class UserBased(Recommender):
    def __init__(self, recommendations_redis, track_redis):
        self.recommendations_redis = recommendations_redis
        self.random = Random(track_redis)

    def recommend_next(self, user: int, prev_track: int, prev_track_time: float) -> int:
        return self.random.recommend_next(user, prev_track, prev_track_time)
