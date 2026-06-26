from clients.embedding import (
    FastEmbedEmbeddingClient,
    OpenAIEmbeddingClient,
)
from core.config import config
from schemes.dto.embedding import RegisteredEmbeddingModel

fastembed_multilingual_e5_large = FastEmbedEmbeddingClient(
    model_name="intfloat/multilingual-e5-large", dimension=1024
)
openai_small = OpenAIEmbeddingClient(
    model_name="text-embedding-3-small",
    dimension=1536,
    api_key=config.OPENAI_API_KEY,
)
openai_large = OpenAIEmbeddingClient(
    model_name="text-embedding-3-large",
    dimension=3072,
    api_key=config.OPENAI_API_KEY,
)

embedding_model_catalog = {
    "BAAI/bge-m3": (
        RegisteredEmbeddingModel(
            name="intfloat/multilingual-e5-large", provider="fastembed", dimension=1024
        ),
        fastembed_multilingual_e5_large,
    ),
    "text-embedding-3-small": (
        RegisteredEmbeddingModel(
            name="text-embedding-3-small", provider="openai", dimension=1536
        ),
        openai_small,
    ),
    "text-embedding-3-large": (
        RegisteredEmbeddingModel(
            name="text-embedding-3-large", provider="openai", dimension=3072
        ),
        openai_large,
    ),
}
