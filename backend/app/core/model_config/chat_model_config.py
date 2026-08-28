from clients.llm import OpenAILLMClient
from core.config import config
from schemes.dto.chat import RegisteredChatModel

openai_gpt4o_mini = OpenAILLMClient(
    model_name="gpt-4o-mini", api_key=config.OPENAI_API_KEY
)
openai_gpt4o = OpenAILLMClient(model_name="gpt-4o", api_key=config.OPENAI_API_KEY)

chat_model_catalog = {
    "gpt-4o-mini": (
        RegisteredChatModel(name="gpt-4o-mini", provider="openai"),
        openai_gpt4o_mini,
    ),
    "gpt-4o": (
        RegisteredChatModel(name="gpt-4o", provider="openai"),
        openai_gpt4o,
    ),
}
