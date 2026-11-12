import os
import asyncio
from getpass import getpass
from datetime import datetime, timezone

from dotenv import load_dotenv

from graphiti_core import Graphiti
from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient
from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient


load_dotenv()


async def main():

    api_key = os.getenv("OPENROUTER_API_KEY")
    base_url = "https://openrouter.ai/api/v1"

    # LLM
    llm_config = LLMConfig(
        api_key=api_key,
        model="google/gemini-2.5-flash",
        base_url=base_url,
        temperature=0
    )

    llm_client = OpenAIGenericClient(
        config=llm_config
    )

    # Embeddings
    embedder_config = OpenAIEmbedderConfig(
        api_key=api_key,
        embedding_model="openai/text-embedding-3-small",
        base_url=base_url,
        embedding_dim=1536
    )

    embedder = OpenAIEmbedder(
        config=embedder_config
    )

    # Reranker
    cross_encoder = OpenAIRerankerClient(
        config=llm_config
    )

    # Neo4j
    neo4j_password = getpass("Neo4j password: ")

    graphiti = Graphiti(
        uri="bolt://localhost:7687",
        user="neo4j",
        password=neo4j_password,
        llm_client=llm_client,
        embedder=embedder,
        cross_encoder=cross_encoder
    )

    await graphiti.build_indices_and_constraints()

    # Knowledge that we want Graphiti to remember
    episode_body = """
    The Queryable Chatbot project uses MongoDB for structured business data.
    LangChain is used for the queryable agent.
    Graphiti is used for knowledge graph and relationship-based context.
    Neo4j is used as the graph database for Graphiti.
    OpenUI is used as the frontend presentation layer.
    Jev is used as a backend routing and verification component.
    """

    print()
    print("Adding project knowledge to Graphiti...")

    await graphiti.add_episode(
        name="queryable_chatbot_project",
        episode_body=episode_body,
        source_description="Project architecture information",
        reference_time=datetime.now(timezone.utc)
    )

    print()
    print("=" * 60)
    print("KNOWLEDGE ADDED SUCCESSFULLY")
    print("=" * 60)

    await graphiti.close()


if __name__ == "__main__":
    asyncio.run(main())