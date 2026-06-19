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


# Qdrant은 기존 vector의 size/distance는 변경할 수 없으므로, 수정 가능한 항목만 노출한다.
class DenseVectorUpdateConfig(BaseModel):
    on_disk: bool | None = None


class SparseVectorUpdateConfig(BaseModel):
    on_disk: bool | None = None


class OptimizersConfigUpdate(BaseModel):
    indexing_threshold: int | None = Field(default=None, ge=0)
    default_segment_number: int | None = Field(default=None, ge=0)


class UpdateQdrantCollectionRequest(BaseModel):
    # 지정된 vector 이름의 수정 가능한 설정만 갱신한다. None인 항목은 변경하지 않는다.
    dense_vectors: dict[str, DenseVectorUpdateConfig] | None = None
    sparse_vectors: dict[str, SparseVectorUpdateConfig] | None = None
    optimizers_config: OptimizersConfigUpdate | None = None

    @model_validator(mode="after")
    def check_any_field(self):
        if not any([self.dense_vectors, self.sparse_vectors, self.optimizers_config]):
            raise ValueError("수정할 항목을 최소 하나 이상 지정해야 합니다")
        return self
