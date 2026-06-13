from enum import Enum
from pydantic import BaseModel, Field, model_validator

### Qdrant
class Distance(str, Enum):
    COSINE = "Cosine"
    DOT = "Dot"
    EUCLID = "Euclid"
    MANHATTAN = "Manhattan"


class SparseModifier(str, Enum):
    NONE = "none"
    IDF = "idf"  # BM25류 가중. BGE-M3 sparse엔 보통 idf


class DenseVectorConfig(BaseModel):
    size: int = Field(..., gt=0)
    distance: Distance = Distance.COSINE
    on_disk: bool = False


class SparseVectorConfig(BaseModel):
    modifier: SparseModifier = SparseModifier.IDF
    on_disk: bool = False


class EmbeddingModelInfo(BaseModel):
    name: str = Field(..., examples=["BAAI/bge-m3"])
    dimension: int = Field(..., gt=0)
    revision: str | None = None
    normalize: bool = True


class CreateQdrantCollectionRequest(BaseModel):
    collection_name: str = Field(..., min_length=1)
    dense_vectors: dict[str, DenseVectorConfig]
    sparse_vectors: dict[str, SparseVectorConfig] = Field(default_factory=dict)
    embedding_model: EmbeddingModelInfo
    on_disk_payload: bool = True

    @model_validator(mode="after")
    def check_dense_dim(self):
        dim = self.embedding_model.dimension
        for name, cfg in self.dense_vectors.items():
            if cfg.size != dim:
                raise ValueError(
                    f"dense '{name}' size({cfg.size}) != model dimension({dim})"
                )
        return self