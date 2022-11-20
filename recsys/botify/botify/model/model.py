from dataclasses import field, dataclass

import pytorch_lightning as pl
import torch
import torch.nn as nn
import torch.nn.functional as F


@dataclass
class ModelConfig:
    unique_users_count: int = 10000
    unique_tracks_count: int = 50000
    unique_artists_count: int = 12000
    user_embedding_dim: int = 10
    context_track_embedding_dim: int = 20
    track_embedding_dim: int = 20
    artist_embedding_dim: int = 10
    hidden_dims: list = field(default_factory=lambda: [512, 256, 128])
    dropout_prob: float = 0.2


class ContextualRanker(pl.LightningModule):
    def __init__(self, config: ModelConfig):
        super().__init__()
        self.user_embedding_dim = config.user_embedding_dim
        self.context_track_embedding_dim = config.context_track_embedding_dim
        self.track_embedding_dim = config.track_embedding_dim
        self.artist_embedding_dim = config.artist_embedding_dim
        self.hidden_dims = config.hidden_dims

        self.user_embedding = nn.Embedding(num_embeddings=config.unique_users_count,
                                           embedding_dim=self.user_embedding_dim)
        self.context_track_embedding = nn.Embedding(num_embeddings=config.unique_tracks_count,
                                                    embedding_dim=self.context_track_embedding_dim)
        self.track_embedding = nn.Embedding(num_embeddings=config.unique_tracks_count,
                                            embedding_dim=self.track_embedding_dim)
        self.artist_embedding = nn.Embedding(num_embeddings=config.unique_artists_count,
                                             embedding_dim=self.artist_embedding_dim)

        context_transformation_layers = [
            nn.Linear(self.user_embedding_dim + self.context_track_embedding_dim, self.hidden_dims[0]),
            nn.BatchNorm1d(self.hidden_dims[0]),
            nn.LeakyReLU(0.1),
            nn.Dropout(config.dropout_prob)
        ]
        for i in range(0, len(self.hidden_dims) - 1):
            context_transformation_layers.extend([
                nn.Linear(self.hidden_dims[i], self.hidden_dims[i + 1]),
                nn.BatchNorm1d(self.hidden_dims[i + 1]),
                nn.LeakyReLU(0.1),
                nn.Dropout(config.dropout_prob)
            ])
        self.context_transformation = nn.Sequential(
            *context_transformation_layers
        )

        track_transformation_layers = [
            nn.Linear(self.track_embedding_dim + self.artist_embedding_dim, self.hidden_dims[0]),
            nn.BatchNorm1d(self.hidden_dims[0]),
            nn.LeakyReLU(0.1),
            nn.Dropout(config.dropout_prob)
        ]
        for i in range(0, len(self.hidden_dims) - 1):
            track_transformation_layers.extend([
                nn.Linear(self.hidden_dims[i], self.hidden_dims[i + 1]),
                nn.BatchNorm1d(self.hidden_dims[i + 1]),
                nn.LeakyReLU(0.1),
                nn.Dropout(config.dropout_prob)
            ])
        self.track_transformation = nn.Sequential(
            *track_transformation_layers
        )

    def forward(self, x):
        context_data = self.context_transformation(
            torch.cat((self.user_embedding(x[:, 0]), self.context_track_embedding(x[:, 1])), dim=1))
        track_data = self.track_transformation(
            torch.cat((self.track_embedding(x[:, 2]), self.artist_embedding(x[:, 3])), dim=1))

        return torch.sum(context_data * track_data, dim=1)

    def step(self, batch, batch_idx, metric, prog_bar=False):
        x, y = batch
        predictions = self.forward(x)
        loss = F.mse_loss(predictions, y.float(), reduction='mean')
        self.log(metric, loss, prog_bar=prog_bar)
        return loss

    def test_step(self, batch, batch_idx, prog_bar=False):
        x, y = batch
        predictions = self.forward(x)
        targets = y[:, 0].float()
        avgs = y[:, 1].float()
        rdms = y[:, 2].float()

        loss = F.mse_loss(predictions, targets, reduction='mean')
        avg_loss = F.mse_loss(avgs, targets, reduction='mean')
        rdm_loss = F.mse_loss(rdms, targets, reduction='mean')

        self.log("test_loss", loss, prog_bar=prog_bar)
        self.log("avg_loss", avg_loss, prog_bar=prog_bar)
        self.log("rdm_loss", rdm_loss, prog_bar=prog_bar)

    def training_step(self, batch, batch_idx):
        return self.step(batch, batch_idx, "train_loss")

    def validation_step(self, batch, batch_idx):
        return self.step(batch, batch_idx, "val_loss", True)

    def predict_step(self, batch, batch_idx):
        x, = batch
        predictions = self.forward(x)

        return predictions

    def get_context_embedding(self, user_id: torch.Tensor, track_id: torch.Tensor) -> torch.Tensor:
        input = torch.cat((self.user_embedding(user_id), self.context_track_embedding(track_id)), dim=0)\
            .unsqueeze(0)
        context_embeddings = self.context_transformation(input)

        return context_embeddings[0]

    def get_track_embeddings(self, tracks: torch.Tensor, artists: torch.Tensor) -> torch.Tensor:
        track_embeddings = self.track_transformation(
            torch.cat((self.track_embedding(tracks), self.artist_embedding(artists)), dim=1))

        return track_embeddings

    def configure_optimizers(self):
        optimizer = torch.optim.Adam(self.parameters(), lr=1e-3, weight_decay=1e-5)
        lr_scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=3, verbose=True)
        scheduler = {
            'scheduler': lr_scheduler,
            'monitor': 'val_loss'
        }
        return [optimizer], [scheduler]
