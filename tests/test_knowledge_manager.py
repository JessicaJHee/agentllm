"""Unit tests for KnowledgeManager."""

import tempfile
from pathlib import Path

import pytest

from agentllm.knowledge import KnowledgeManager


class TestKnowledgeManager:
    """Tests for KnowledgeManager class."""

    def test_initialization_with_required_params(self):
        """Test KnowledgeManager initializes with required parameters."""
        custom_knowledge = "/tmp/custom_knowledge"
        custom_table = "custom_table"

        km = KnowledgeManager(
            knowledge_path=custom_knowledge,
            table_name=custom_table,
        )

        assert km.knowledge_path == Path(custom_knowledge)
        assert "lancedb" in str(km.vector_db_path)  # Default vector_db_path
        assert km.table_name == custom_table

    def test_initialization_with_all_params(self):
        """Test KnowledgeManager initializes with all parameters."""
        custom_knowledge = "/tmp/custom_knowledge"
        custom_vector_db = "/tmp/custom_lancedb"
        custom_table = "custom_table"

        km = KnowledgeManager(
            knowledge_path=custom_knowledge,
            table_name=custom_table,
            vector_db_path=custom_vector_db,
        )

        assert km.knowledge_path == Path(custom_knowledge)
        assert km.vector_db_path == Path(custom_vector_db)
        assert km.table_name == custom_table

    def test_initialization_fails_without_required_params(self):
        """Test KnowledgeManager raises ValueError when required params missing."""
        with pytest.raises(ValueError, match="knowledge_path is required"):
            KnowledgeManager(knowledge_path="", table_name="test")

        with pytest.raises(ValueError, match="table_name is required"):
            KnowledgeManager(knowledge_path="/tmp/knowledge", table_name="")

        with pytest.raises(ValueError, match="table_name is required"):
            KnowledgeManager(knowledge_path="/tmp/knowledge", table_name="   ")

    def test_load_knowledge_with_missing_path(self):
        """Test load_knowledge with non-existent knowledge path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            km = KnowledgeManager(
                knowledge_path=Path(tmpdir) / "nonexistent",
                table_name="test_table",
                vector_db_path=Path(tmpdir) / "lancedb",
            )

            # Should create empty knowledge base
            knowledge = km.load_knowledge()
            assert knowledge is not None

    def test_load_knowledge_with_empty_directory(self):
        """Test load_knowledge with empty knowledge directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            knowledge_dir = Path(tmpdir) / "knowledge"
            knowledge_dir.mkdir()

            km = KnowledgeManager(
                knowledge_path=knowledge_dir,
                table_name="test_table",
                vector_db_path=Path(tmpdir) / "lancedb",
            )

            knowledge = km.load_knowledge()
            assert knowledge is not None

    def test_count_documents(self):
        """Test _count_documents method."""
        with tempfile.TemporaryDirectory() as tmpdir:
            knowledge_dir = Path(tmpdir) / "knowledge"
            knowledge_dir.mkdir()

            # Create test files
            (knowledge_dir / "test1.md").write_text("Test markdown content " * 10)
            (knowledge_dir / "test2.md").write_text("Another markdown file " * 10)
            (knowledge_dir / "empty.md").write_text("")  # Should be filtered out

            km = KnowledgeManager(
                knowledge_path=knowledge_dir,
                table_name="test_table",
                vector_db_path=Path(tmpdir) / "lancedb",
            )

            md_files, pdf_files, csv_files = km._count_documents()

            # Should find 2 markdown files (empty one filtered out)
            assert len(md_files) == 2
            assert len(pdf_files) == 0
            assert len(csv_files) == 0

    def test_check_table_exists_empty(self):
        """Test check_table_exists returns False when table doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            km = KnowledgeManager(
                knowledge_path=Path(tmpdir) / "knowledge",
                table_name="test_table",
                vector_db_path=Path(tmpdir) / "lancedb",
            )

            # Table doesn't exist yet
            exists = km.check_table_exists()
            assert exists is False

    def test_knowledge_caching(self):
        """Test that load_knowledge caches the knowledge instance."""
        with tempfile.TemporaryDirectory() as tmpdir:
            knowledge_dir = Path(tmpdir) / "knowledge"
            knowledge_dir.mkdir()

            km = KnowledgeManager(
                knowledge_path=knowledge_dir,
                table_name="test_table",
                vector_db_path=Path(tmpdir) / "lancedb",
            )

            # First load
            knowledge1 = km.load_knowledge()
            # Second load should return cached instance
            knowledge2 = km.load_knowledge()

            assert knowledge1 is knowledge2


class TestKnowledgeManagerIntegration:
    """Integration tests for KnowledgeManager (may be slow)."""

    @pytest.mark.integration
    def test_load_actual_knowledge_files(self):
        """Test loading the actual example knowledge files (if they exist)."""
        # Skip if knowledge directory doesn't exist
        knowledge_path = Path("examples/knowledge")
        if not knowledge_path.exists():
            pytest.skip("Knowledge directory not found")

        with tempfile.TemporaryDirectory() as tmpdir:
            km = KnowledgeManager(
                knowledge_path=knowledge_path,
                table_name="test_integration",
                vector_db_path=Path(tmpdir) / "lancedb",
            )

            # This will actually load and index the markdown files
            knowledge = km.load_knowledge()
            assert knowledge is not None

    @pytest.mark.integration
    def test_reindex_knowledge_base(self):
        """Test reindexing the knowledge base."""
        with tempfile.TemporaryDirectory() as tmpdir:
            knowledge_dir = Path(tmpdir) / "knowledge"
            knowledge_dir.mkdir()

            # Create a test file
            (knowledge_dir / "test.md").write_text("Test content " * 20)

            km = KnowledgeManager(
                knowledge_path=knowledge_dir,
                table_name="test_reindex",
                vector_db_path=Path(tmpdir) / "lancedb",
            )

            # Initial load
            km.load_knowledge()

            # Reindex
            km.reindex(force=True)

            # Should have new knowledge instance
            assert km._knowledge is not None
