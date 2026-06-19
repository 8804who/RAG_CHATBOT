from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LoginResponse(BaseModel):
    # Opaque session token; the client sends it as `Authorization: Bearer <token>`.
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: str | None
    picture: str | None


### Qdrant
class DenseVectorDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    size: int
    distance: str
    on_disk: bool


class SparseVectorDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    modifier: str | None
    on_disk: bool


class CollectionDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    status: str
    points_count: int
    dense_vectors: dict[str, DenseVectorDetail]
    sparse_vectors: dict[str, SparseVectorDetail]
    indexing_threshold: int | None
    default_segment_number: int | None


class CollectionSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str


class CollectionsResponse(BaseModel):
    collections: list[CollectionSummaryResponse]
