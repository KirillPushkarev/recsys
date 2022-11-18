import json
import logging
import time
from dataclasses import asdict
from datetime import datetime
from typing import Union

from flask import Flask
from flask_redis import Redis
from flask_restful import Resource, Api, abort, reqparse
from flask_restful.reqparse import RequestParser
from redis.client import StrictRedis

from botify.catalog import Catalog
from botify.data import DataLogger, Datum
from botify.recommenders.contextual import Contextual
from botify.utils import from_bytes


class Hello(Resource):
    def get(self):
        return {
            "status": "alive",
            "message": "welcome to botify, the best toy music recommender",
        }


class Track(Resource):
    def __init__(self, tracks_with_recs_redis: Union[Redis, StrictRedis]):
        self.tracks_redis = tracks_with_recs_redis

    def get(self, track: int):
        data = self.tracks_redis.connection.get(track)
        if data is not None:
            return asdict(from_bytes(data))
        else:
            abort(404, description="Track not found")


class NextTrack(Resource):
    def __init__(self, parser: RequestParser, tracks_with_recs_redis: Union[Redis, StrictRedis], data_logger: DataLogger):
        self.parser = parser
        self.tracks_redis = tracks_with_recs_redis
        self.data_logger = data_logger

    def post(self, user: int):
        start = time.time()

        args = self.parser.parse_args()
        recommender = Contextual(self.tracks_redis.connection)

        recommendation = recommender.recommend_next(user, args.track, args.time)

        self.data_logger.log(
            "next",
            Datum(
                int(datetime.now().timestamp() * 1000),
                user,
                args.track,
                args.time,
                time.time() - start,
                recommendation,
            ),
        )
        return {"user": user, "track": recommendation}


class LastTrack(Resource):
    def __init__(self, parser: RequestParser, data_logger: DataLogger):
        self.parser = parser
        self.data_logger = data_logger

    def post(self, user: int):
        start = time.time()
        args = self.parser.parse_args()
        self.data_logger.log(
            "last",
            Datum(
                int(datetime.now().timestamp() * 1000),
                user,
                args.track,
                args.time,
                time.time() - start,
            ),
        )
        return {"user": user}


if __name__ == "__main__":
    root = logging.getLogger()
    root.setLevel("INFO")

    app = Flask(__name__)
    app.config.from_file("config.json", load=json.load)

    data_logger = DataLogger(app)

    parser = reqparse.RequestParser()
    parser.add_argument("track", type=int, location="json", required=True)
    parser.add_argument("time", type=float, location="json", required=True)

    tracks_with_recs_redis = Redis(app, config_prefix="REDIS_TRACKS_WITH_RECS")
    tracks_with_diverse_recs_redis = Redis(app, config_prefix="REDIS_TRACKS_WITH_DIVERSE_RECS")
    artists_redis = Redis(app, config_prefix="REDIS_ARTIST")
    recommendations_redis = Redis(app, config_prefix="REDIS_RECOMMENDATIONS")
    recommendations_svd_redis = Redis(app, config_prefix="REDIS_RECOMMENDATIONS_SVD")

    catalog = Catalog(app)
    catalog.load_data_from_filesystem(
        app.config["TRACKS_CATALOG"],
        app.config["TOP_TRACKS_CATALOG"],
        app.config["TRACKS_WITH_DIVERSE_RECS_CATALOG"]
    )
    catalog.upload_tracks_to_cache(tracks_with_recs_redis.connection, tracks_with_diverse_recs_redis.connection)
    catalog.upload_artists_to_cache(artists_redis.connection)
    catalog.upload_recommendations_to_cache(recommendations_redis.connection, "RECOMMENDATIONS_FILE_PATH")
    catalog.upload_recommendations_to_cache(recommendations_svd_redis.connection, "RECOMMENDATIONS_SVD_FILE_PATH")

    api = Api(app)
    api.add_resource(Hello, "/")
    api.add_resource(Track, "/track/<int:track>", resource_class_args=(tracks_with_recs_redis,))
    api.add_resource(NextTrack, "/next/<int:user>", resource_class_args=(parser, tracks_with_recs_redis, data_logger))
    api.add_resource(LastTrack, "/last/<int:user>", resource_class_args=(parser, data_logger))

    app.run(host="0.0.0.0", port=7777)
