from dataclasses import dataclass, field
from typing import List


@dataclass
class Track:
    track: int
    artist: str
    title: str
    recommendations: List[int] = field(default=lambda: [])
