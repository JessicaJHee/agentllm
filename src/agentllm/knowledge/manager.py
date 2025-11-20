"""
Knowledge base management for AgentLLM using LanceDB and Agno.

This module provides centralized knowledge management that can be shared
across multiple agents. It uses LanceDB for vector storage with Gemini
embeddings, supporting markdown, PDF, and CSV documents.
"""

import asyncio
import os
from pathlib import Path

from agno.knowledge.embedder.google import GeminiEmbedder
from agno.knowledge.knowledge import Knowledge
from agno.vectordb.lancedb import LanceDb, SearchType
from loguru import logger


class KnowledgeManager:
    """Manages shared knowledge base with vector storage for markdown, PDF, and CSV files.

    This class provides centralized knowledge management that can be shared across
    multiple agents. All configuration must be provided explicitly by the caller.
    """

    def __init__(
        self,
        knowledge_path: Path | str,
        table_name: str,
        vector_db_path: Path | str | None = None,
    ):
        """
        Initialize knowledge manager with explicit configuration.

        Args:
            knowledge_path: Path to knowledge documents directory (required)
            table_name: Name of the LanceDB table (required)
            vector_db_path: Path for vector database storage (optional, defaults to tmp/lancedb)

        Raises:
            ValueError: If knowledge_path or table_name is empty or None
        """
        # Validate required parameters
        if not knowledge_path:
            raise ValueError("knowledge_path is required and cannot be empty")
        if not table_name or not table_name.strip():
            raise ValueError("table_name is required and cannot be empty")

        # Convert to Path and validate knowledge_path is not empty string
        self.knowledge_path = Path(knowledge_path)
        if str(self.knowledge_path).strip() == "" or str(self.knowledge_path) == ".":
            raise ValueError(f"Invalid knowledge_path: '{knowledge_path}' resolves to empty or current directory")

        # Default vector_db_path to tmp/lancedb if not provided
        if vector_db_path is None:
            # Use AGENTLLM_DATA_DIR env var if set, otherwise tmp
            base_dir = os.getenv("AGENTLLM_DATA_DIR", "tmp")
            vector_db_path = Path(base_dir) / "lancedb"

        self.vector_db_path = Path(vector_db_path)
        self.table_name = table_name.strip()
        self._knowledge: Knowledge | None = None
        self._vector_db: LanceDb | None = None

        logger.debug(
            f"KnowledgeManager initialized: knowledge_path={self.knowledge_path}, "
            f"vector_db_path={self.vector_db_path}, table_name={self.table_name}"
        )

    def get_vector_db(self) -> LanceDb:
        """Get or create the LanceDB vector database instance.

        Returns:
            LanceDb instance configured for hybrid search with Gemini embeddings
        """
        if self._vector_db is None:
            logger.debug("Creating LanceDB vector database")
            self._vector_db = LanceDb(
                uri=str(self.vector_db_path),
                table_name=self.table_name,
                search_type=SearchType.hybrid,  # Vector + keyword search
                embedder=GeminiEmbedder(id="gemini-embedding-001"),
            )
            logger.debug(f"LanceDB created: {self.vector_db_path}/{self.table_name}")
        return self._vector_db

    def check_table_exists(self) -> bool:
        """
        Check if the LanceDB table exists and has data.

        Returns:
            True if table exists and has data, False otherwise
        """
        try:
            vector_db = self.get_vector_db()
            # Try to access the table row count
            if hasattr(vector_db, "table") and vector_db.table is not None:
                row_count = vector_db.table.count_rows()
                logger.debug(f"Table {self.table_name} exists with {row_count} rows")
                return bool(row_count > 0)
            return False
        except Exception as e:
            logger.debug(f"Table check failed: {e}")
            return False

    def _count_documents(self, min_size_bytes: int = 50) -> tuple[list[Path], list[Path], list[Path]]:
        """Count and return markdown, PDF, and CSV files, excluding small/empty files.

        Args:
            min_size_bytes: Minimum file size in bytes to include

        Returns:
            Tuple of (markdown_files, pdf_files, csv_files)
        """

        def filter_by_size(files: list[Path]) -> list[Path]:
            """Filter files by minimum size to exclude empty or very small files."""
            filtered = []
            for file_path in files:
                try:
                    if file_path.stat().st_size >= min_size_bytes:
                        filtered.append(file_path)
                    else:
                        logger.debug(f"Skipping small file ({file_path.stat().st_size} bytes): {file_path}")
                except (OSError, FileNotFoundError) as e:
                    logger.debug(f"Error checking file size for {file_path}: {e}")
            return filtered

        md_files = filter_by_size(list(self.knowledge_path.rglob("*.md")))
        pdf_files = filter_by_size(list(self.knowledge_path.rglob("*.pdf")))
        csv_files = filter_by_size(list(self.knowledge_path.rglob("*.csv")))
        return md_files, pdf_files, csv_files

    def _create_knowledge_base(self, vector_db: LanceDb, md_files: list[Path], pdf_files: list[Path], csv_files: list[Path]) -> Knowledge:
        """Create knowledge base instance with all file types.

        Args:
            vector_db: LanceDb instance
            md_files: List of markdown files
            pdf_files: List of PDF files
            csv_files: List of CSV files

        Returns:
            Knowledge instance
        """
        logger.debug(f"Creating Knowledge with {len(md_files)} markdown, {len(pdf_files)} PDF, {len(csv_files)} CSV files")

        # Create a unified Knowledge instance
        knowledge = Knowledge(
            name=self.table_name,
            description="AgentLLM shared knowledge base",
            vector_db=vector_db,
            max_results=5,
        )

        return knowledge

    def _add_documents_sync(self, md_files: list[Path], pdf_files: list[Path], csv_files: list[Path]) -> None:
        """Add documents to knowledge base with proper event loop handling.

        This method ensures async operations (embedding extraction) run in a
        proper event loop context to avoid "Event loop is closed" errors.

        Args:
            md_files: List of markdown file paths
            pdf_files: List of PDF file paths
            csv_files: List of CSV file paths
        """
        try:
            # Try to get the current event loop
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                # Create a new event loop if the current one is closed
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            # No event loop exists, create one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        try:
            # Add all markdown files
            for md_file in md_files:
                logger.debug(f"Adding markdown file: {md_file}")
                self._knowledge.add_content(path=str(md_file))

            # Add all PDF files
            for pdf_file in pdf_files:
                logger.debug(f"Adding PDF file: {pdf_file}")
                self._knowledge.add_content(path=str(pdf_file))

            # Add all CSV files
            for csv_file in csv_files:
                logger.debug(f"Adding CSV file: {csv_file}")
                self._knowledge.add_content(path=str(csv_file))
        finally:
            # Don't close the loop as it might be needed by other operations
            pass

    def load_knowledge(self, recreate: bool = False, force_reload: bool = False) -> Knowledge:
        """
        Load or create the knowledge base.

        Args:
            recreate: If True, recreate the knowledge base even if it exists
            force_reload: If True, reload documents even if table exists

        Returns:
            Knowledge instance with loaded documents

        Raises:
            FileNotFoundError: If knowledge path doesn't exist
            RuntimeError: If knowledge loading fails
        """
        if self._knowledge is not None and not recreate:
            logger.debug("Returning existing knowledge base")
            return self._knowledge

        if not self.knowledge_path.exists():
            logger.warning(f"Knowledge path not found: {self.knowledge_path}")
            logger.info("Creating empty knowledge base (no documents to load)")

            # Create empty knowledge base
            vector_db = self.get_vector_db()
            self._vector_db = vector_db
            self._knowledge = Knowledge(
                name=self.table_name,
                description="AgentLLM shared knowledge base (empty)",
                vector_db=vector_db,
                max_results=5,
            )
            return self._knowledge

        try:
            # Get the shared vector database instance
            vector_db = self.get_vector_db()
            self._vector_db = vector_db

            # Count documents for reference
            md_files, pdf_files, csv_files = self._count_documents()

            if not md_files and not pdf_files and not csv_files:
                logger.warning(f"No supported documents found in {self.knowledge_path}")
                logger.info("Creating empty knowledge base")
                self._knowledge = self._create_knowledge_base(vector_db, [], [], [])
                return self._knowledge

            # Check if table exists and has data
            table_exists = self.check_table_exists()

            if table_exists and not recreate and not force_reload:
                logger.info(f"LanceDB table '{self.table_name}' already exists with data. Skipping document loading for faster startup.")

                # Create knowledge base object without loading documents
                self._knowledge = self._create_knowledge_base(vector_db, md_files, pdf_files, csv_files)

                logger.info(
                    f"Knowledge base ready (using existing data). "
                    f"Available: {len(md_files)} markdown, {len(pdf_files)} PDF, and {len(csv_files)} CSV files"
                )

                return self._knowledge

            # Table doesn't exist or force_reload requested - load documents
            logger.info(f"Loading knowledge base from {self.knowledge_path}")
            logger.debug(f"Found {len(md_files)} markdown, {len(pdf_files)} PDF, and {len(csv_files)} CSV files")

            # Create knowledge base
            self._knowledge = self._create_knowledge_base(vector_db, md_files, pdf_files, csv_files)

            logger.info("Loading documents into Knowledge base")

            # Add all documents to the knowledge base
            # Use proper async context to avoid event loop errors
            self._add_documents_sync(md_files, pdf_files, csv_files)

            logger.info(
                f"Knowledge base loaded successfully with {len(md_files)} markdown, "
                f"{len(pdf_files)} PDF, and {len(csv_files)} CSV files available"
            )

            return self._knowledge

        except Exception as e:
            logger.error(f"Failed to load knowledge base: {e}")
            raise RuntimeError(f"Knowledge loading failed: {e}") from e

    def reindex(self, force: bool = True) -> None:
        """
        Reindex the knowledge base by recreating the vector database.

        Args:
            force: If True, force recreation even if table exists
        """
        logger.info("Starting knowledge base reindexing...")

        try:
            # Force reload the knowledge base
            self.load_knowledge(recreate=True, force_reload=force)
            logger.info("Knowledge base reindexing completed successfully")
        except Exception as e:
            logger.error(f"Failed to reindex knowledge base: {e}")
            raise RuntimeError(f"Reindexing failed: {e}") from e
