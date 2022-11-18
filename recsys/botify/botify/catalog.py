import itertools
import json
from typing import Union

from flask_redis import Redis
from redis.client import StrictRedis

from botify.track import Track
from botify.utils import to_bytes


class Catalog:
    """
    A helper class used to load track data upon server startup
    and store the data to redis.
    """

    def __init__(self, app):
        self.app = app

        self.tracks_with_recs = []
        self.tracks_with_diverse_recs = []
        self.top_track_ids = []

    def load_data_from_filesystem(self, tracks_with_recs_path: str, top_tracks_path: str, tracks_with_diverse_recs_path: str):
        self.app.logger.info(f"Loading tracks from {tracks_with_recs_path}")
        self.tracks_with_recs = self.load_track_data_from_file(tracks_with_recs_path)
        self.app.logger.info(f"Loaded {len(self.tracks_with_recs)} tracks")

        self.app.logger.info(f"Loading tracks with diverse recommendations from {tracks_with_diverse_recs_path}")
        self.tracks_with_diverse_recs = self.load_track_data_from_file(tracks_with_diverse_recs_path)
        self.app.logger.info(f"Loaded {len(self.tracks_with_diverse_recs)} tracks with diverse recs")

        self.app.logger.info(f"Loading top tracks from {top_tracks_path}")
        with open(top_tracks_path) as top_tracks_file:
            self.top_track_ids = json.load(top_tracks_file)
        self.app.logger.info(f"Loaded {len(self.top_track_ids)} top tracks")

        return self

    @staticmethod
    def load_track_data_from_file(path: str) -> list:
        tracks = []
        with open(path) as file_handle:
            for j, line in enumerate(file_handle):
                data = json.loads(line)
                tracks.append(Track(data["track"], data["artist"], data["title"], data["recommendations"], ))

        return tracks

    def upload_tracks_to_cache(self, redis_tracks_with_recs: Union[Redis, StrictRedis], redis_tracks_with_diverse_recs: Union[Redis, StrictRedis]):
        self.app.logger.info(f"Uploading tracks to redis")

        for track in self.tracks_with_recs:
            redis_tracks_with_recs.set(track.track, to_bytes(track))

        for track in self.tracks_with_diverse_recs:
            redis_tracks_with_diverse_recs.set(track.track, to_bytes(track))

        self.app.logger.info(
            f"Uploaded {len(self.tracks_with_recs)} tracks with recs, {len(self.tracks_with_diverse_recs)} tracks with diverse recs"
        )

    def upload_artists_to_cache(self, redis: Union[Redis, StrictRedis]):
        self.app.logger.info(f"Uploading artists to redis")

        sorted_tracks = sorted(self.tracks_with_recs, key=lambda t: t.artist)
        for j, (artist, artist_catalog) in enumerate(
                itertools.groupby(sorted_tracks, key=lambda t: t.artist)
        ):
            artist_tracks = [t.track for t in artist_catalog]
            redis.set(artist, to_bytes(artist_tracks))

        self.app.logger.info(f"Uploaded {j + 1} artists")

    def upload_recommendations_to_cache(self, redis: Union[Redis, StrictRedis], recommendations_path: str):
        self.app.logger.info(f"Uploading recommendations to redis")

        recommendations_file_path = self.app.config[recommendations_path]
        with open(recommendations_file_path) as recommendations_file:
            for j, line in enumerate(recommendations_file):
                recommendations = json.loads(line)
                redis.set(
                    recommendations["user"], to_bytes(recommendations["tracks"])
                )

        self.app.logger.info(f"Uploaded recommendations for {j + 1} users")
