"""Factory for creating and managing KnowledgeManager instances.

Each agent type gets its own KnowledgeManager singleton instance, allowing
different agents to have different knowledge bases and vector databases.
"""

import logging
import threading
from typing import Any

from .manager import KnowledgeManager

logger = logging.getLogger(__name__)


class KnowledgeManagerFactory:
    """Factory for creating and caching KnowledgeManager instances per agent type.

    Each agent type (identified by agent_name) gets its own KnowledgeManager instance,
    allowing different agents to have different knowledge bases and vector databases.

    Example:
        # Demo agent gets its own manager
        demo_manager = KnowledgeManagerFactory.get_or_create(
            agent_name="demo-agent",
            config={"knowledge_path": "examples/knowledge", "table_name": "demo_knowledge"}
        )

        # GitHub agent gets a different manager
        github_manager = KnowledgeManagerFactory.get_or_create(
            agent_name="github-agent",
            config={"knowledge_path": "examples/github_knowledge", "table_name": "github_knowledge"}
        )
    """

    _instances: dict[str, KnowledgeManager] = {}
    _lock = threading.Lock()

    @classmethod
    def get_or_create(cls, agent_name: str, config: dict[str, Any]) -> KnowledgeManager:
        """Get or create a KnowledgeManager instance for the specified agent.

        Args:
            agent_name: Unique identifier for the agent type (e.g., "demo-agent")
            config: Configuration dictionary with keys:
                - knowledge_path: Path to knowledge base files (str or Path)
                - table_name: Name of the LanceDB table (str)
                - vector_db_path: (optional) Path to vector database directory

        Returns:
            KnowledgeManager instance for this agent type (cached singleton)
        """
        # Use agent_name as cache key (one manager per agent type)
        cache_key = agent_name

        # Check if instance already exists (fast path, no lock)
        if cache_key in cls._instances:
            logger.info(f"✓ Using CACHED KnowledgeManager for agent '{agent_name}' (no indexing needed)")
            return cls._instances[cache_key]

        # Thread-safe creation (slow path, with lock)
        with cls._lock:
            # Double-check pattern: another thread might have created it
            if cache_key in cls._instances:
                logger.info(f"✓ Using CACHED KnowledgeManager for agent '{agent_name}' (after lock, no indexing needed)")
                return cls._instances[cache_key]

            # Create new instance
            logger.info(f"✗ Cache MISS - Creating NEW KnowledgeManager for agent '{agent_name}' with config: {config}")

            # Extract config parameters
            knowledge_path = config.get("knowledge_path")
            table_name = config.get("table_name")
            vector_db_path = config.get("vector_db_path")

            if not knowledge_path or not table_name:
                raise ValueError(f"Knowledge config for agent '{agent_name}' must include 'knowledge_path' and 'table_name'. Got: {config}")

            # Create KnowledgeManager instance
            # Note: knowledge_path and table_name are required, vector_db_path is optional
            manager = KnowledgeManager(
                knowledge_path=knowledge_path,
                table_name=table_name,
                vector_db_path=vector_db_path,  # Can be None (will use default)
            )

            # Cache and return
            cls._instances[cache_key] = manager
            logger.info(
                f"Created KnowledgeManager for agent '{agent_name}': "
                f"knowledge_path={manager.knowledge_path}, "
                f"vector_db={manager.vector_db_path}, "
                f"table={manager.table_name}"
            )
            return manager

    @classmethod
    def clear_cache(cls) -> None:
        """Clear all cached instances (useful for testing)."""
        with cls._lock:
            cls._instances.clear()
            logger.info("Cleared KnowledgeManagerFactory cache")

    @classmethod
    def get_cached_instance(cls, agent_name: str) -> KnowledgeManager | None:
        """Get cached instance without creating (useful for testing).

        Args:
            agent_name: Agent identifier

        Returns:
            Cached KnowledgeManager instance or None if not found
        """
        return cls._instances.get(agent_name)
