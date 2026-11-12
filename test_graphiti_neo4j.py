import os
import asyncio
from getpass import getpass

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

    llm_config = LLMConfig(
        api_key=api_key,
        model="google/gemini-2.5-flash",
        base_url=base_url,
        temperature=0
    )

    llm_client = OpenAIGenericClient(
        config=llm_config
    )

    embedder_config = OpenAIEmbedderConfig(
        api_key=api_key,
        embedding_model="openai/text-embedding-3-small",
        base_url=base_url,
        embedding_dim=1536
    )

    embedder = OpenAIEmbedder(
        config=embedder_config
    )

    cross_encoder = OpenAIRerankerClient(
        config=llm_config
    )

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

    print()
    print("=" * 60)
    print("GRAPHITI -> NEO4J CONNECTION: OK")
    print("=" * 60)
    print("Graphiti successfully connected to Neo4j.")
    print("Graphiti indexes and constraints are ready.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())