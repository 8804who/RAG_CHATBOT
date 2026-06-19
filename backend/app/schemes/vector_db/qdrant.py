from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class QdrantCollectionInfo:
    collection_name: Optional[str] = None
    on_disk_payload: Optional[str] = None
    vectors_count: Optional[int] = None
    points_count: Optional[int] = None
