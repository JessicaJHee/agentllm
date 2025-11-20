"""Knowledge management module for RAG with LanceDB."""

from .factory import KnowledgeManagerFactory
from .manager import KnowledgeManager

__all__ = ["KnowledgeManager", "KnowledgeManagerFactory"]
