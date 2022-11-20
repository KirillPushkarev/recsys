import json
import logging
import time
from dataclasses import asdict
from datetime import datetime
from typing import Union

import torch
from flask import Flask
from flask_redis import Redis
from flask_restful import Resource, Api, abort, reqparse
from flask_restful.reqparse import RequestParser
from redis.client import StrictRedis

from botify.catalog import Catalog
from botify.data import DataLogger, Datum
from botify.experiment import Experiments, Treatment
from botify.model.model import ContextualRanker, ModelConfig
from botify.recommenders.contextual import Contextual
from botify.recommenders.contextual_v2 import ContextualV2
from botify.utils import from_bytes


class Hello(Resource):
    def get(self):
        return {
            "status": "alive",
            "message": "welcome to botify, the best toy music recommender",
        }


class Track(Resource):
    def __init__(self, tracks_with_recs_redis: Union[Redis, StrictRedis]):
        self.tracks_with_recs_redis = tracks_with_recs_redis

    def get(self, track: int):
        data = self.tracks_with_recs_redis.connection.get(track)
        if data is not None:
            return asdict(from_bytes(data))
        else:
            abort(404, description="Track not found")


class NextTrack(Resource):
    def __init__(
            self,
            parser: RequestParser,
            tracks_with_recs_redis: Union[Redis, StrictRedis],
            tracks_with_recs_contextual_v2_redis: Union[Redis, StrictRedis],
            session_redis: Union[Redis, StrictRedis],
            model: ContextualRanker,
            track_embeddings: torch.Tensor,
            data_logger: DataLogger
    ):
        self.parser = parser
        self.tracks_with_recs_redis = tracks_with_recs_redis
        self.tracks_with_recs_contextual_v2_redis = tracks_with_recs_contextual_v2_redis
        self.session_redis = session_redis
        self.model = model
        self.track_embeddings = track_embeddings

        self.data_logger = data_logger

    def post(self, user: int):
        start = time.time()

        args = self.parser.parse_args()

        treatment = Experiments.CONTEXTUAL_V2.assign(user)
        if treatment == Treatment.T1:
            recommender = ContextualV2(self.session_redis.connection, self.model, self.track_embeddings)
        else:
            recommender = Contextual(self.tracks_with_recs_redis.connection)

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
    def __init__(self, parser: RequestParser, session_redis: Union[Redis, StrictRedis], data_logger: DataLogger):
        self.parser = parser
        self.session_redis = session_redis
        self.data_logger = data_logger

    def post(self, user: int):
        start = time.time()
        args = self.parser.parse_args()

        self.session_redis.delete(user)

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


def load_model(checkpoint_path: str):
    model_config = ModelConfig(
        unique_users_count=10000,
        unique_tracks_count=50000,
        unique_artists_count=12000,
        user_embedding_dim=30,
        context_track_embedding_dim=100,
        track_embedding_dim=100,
        artist_embedding_dim=30,
        hidden_dims=[512, 256, 128],
        dropout_prob=0.0
    )

    model = ContextualRanker.load_from_checkpoint(checkpoint_path, config=model_config)
    model.eval()
    return model


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
    tracks_with_recs_contextual_v2_redis = Redis(app, config_prefix="REDIS_TRACKS_WITH_RECS_CONTEXTUAL_V2")
    tracks_with_diverse_recs_redis = Redis(app, config_prefix="REDIS_TRACKS_WITH_DIVERSE_RECS")
    artists_redis = Redis(app, config_prefix="REDIS_ARTIST")
    recommendations_redis = Redis(app, config_prefix="REDIS_RECOMMENDATIONS")
    recommendations_svd_redis = Redis(app, config_prefix="REDIS_RECOMMENDATIONS_SVD")
    session_redis = Redis(app, config_prefix="REDIS_SESSION")

    catalog = Catalog(app)
    catalog.load_data_from_filesystem(
        app.config["TRACKS_CATALOG"],
        app.config["TOP_TRACKS_CATALOG"],
        app.config["TRACKS_WITH_DIVERSE_RECS_CATALOG"],
        app.config["RECOMMENDATIONS_CONTEXTUAL_V2_FILE_PATH"],
    )
    catalog.upload_tracks_to_cache(tracks_with_recs_redis.connection, tracks_with_diverse_recs_redis.connection, tracks_with_recs_contextual_v2_redis.connection)
    catalog.upload_artists_to_cache(artists_redis.connection)
    catalog.upload_recommendations_to_cache(recommendations_redis.connection, "RECOMMENDATIONS_FILE_PATH")
    catalog.upload_recommendations_to_cache(recommendations_svd_redis.connection, "RECOMMENDATIONS_SVD_FILE_PATH")

    model = load_model(app.config["CHECKPOINT_PATH"])
    track_embeddings = torch.load(app.config["TRACK_EMBEDDINGS_PATH"])

    api = Api(app)
    api.add_resource(Hello, "/")
    api.add_resource(Track, "/track/<int:track>", resource_class_args=(tracks_with_recs_redis,))
    api.add_resource(NextTrack, "/next/<int:user>", resource_class_args=(parser, tracks_with_recs_redis, tracks_with_recs_contextual_v2_redis, session_redis, model, track_embeddings, data_logger))
    api.add_resource(LastTrack, "/last/<int:user>", resource_class_args=(parser, session_redis.connection, data_logger))

    app.run(host="0.0.0.0", port=7777)
