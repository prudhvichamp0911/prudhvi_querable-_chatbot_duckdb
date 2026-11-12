import asyncio
from datetime import datetime, timezone
from getpass import getpass

from graphiti_service import GraphitiService


async def test():

    # Ask for Neo4j password securely
    password = getpass("Neo4j password: ")

    # Create Graphiti service
    service = GraphitiService(password)

    # Initialize Graphiti
    await service.initialize()

    print()
    print("=" * 60)
    print("Adding knowledge to Graphiti...")
    print("=" * 60)

    # Add project knowledge to Graphiti
    result = await service.graphiti.add_episode(
        name="Queryable Chatbot Project",
        episode_body=(
            "The Queryable Chatbot project uses MongoDB for structured "
            "business data. LangChain is used for the queryable agent. "
            "Graphiti is used for knowledge graph and relationship-based "
            "context. Neo4j is used as the graph database for Graphiti."
        ),
        source_description="Queryable Chatbot project architecture",
        reference_time=datetime.now(timezone.utc),
    )

    print()
    print("=" * 60)
    print("KNOWLEDGE ADDED SUCCESSFULLY")
    print("=" * 60)

    print("Episode:", result.episode.name)
    print("Entities created:", len(result.nodes))
    print("Relationships created:", len(result.edges))

    print("=" * 60)

    print()
    print("Graphiti test completed.")
    print("The Neo4j connection will be released when the test process exits.")


if __name__ == "__main__":
    asyncio.run(test())