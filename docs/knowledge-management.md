# Knowledge Management & RAG System

## Overview

AgentLLM provides a built-in knowledge management system for Retrieval-Augmented Generation (RAG). Each agent can have its own knowledge base with automatic vector storage and hybrid search.

## Architecture

**Key Components**:
- `KnowledgeManager` - Manages vector DB, document loading, and retrieval
- `KnowledgeManagerFactory` - Creates and caches manager instances per agent type
- `LanceDB` - Vector database for embeddings (hybrid search: vector + keyword)
- `Gemini Embeddings` - Embedding model (`gemini-embedding-001`)

**Design Principles**:
- **Per-agent knowledge**: Each agent type has its own knowledge base
- **Explicit configuration**: Required paths must be provided by caller (no env var fallbacks)
- **Lazy loading**: Documents indexed on first request, cached thereafter
- **Automatic discovery**: No manual knowledge manager injection needed

## How It Works

### 1. Agent Defines Knowledge Config

In your agent's configurator, override `_get_knowledge_config()`:

```python
class MyAgentConfigurator(AgentConfigurator):
    def _get_knowledge_config(self) -> dict[str, Any] | None:
        return {
            "knowledge_path": "examples/my_knowledge",  # Path to docs (MD, PDF, CSV)
            "table_name": "my_agent_knowledge"          # LanceDB table name
        }
```

### 2. Base Class Loads Knowledge Automatically

During agent building (`build_agent()`):
1. Calls `KnowledgeManagerFactory.get_or_create(agent_name, config)`
2. Factory returns cached instance (one singleton per agent type)
3. Manager loads/indexes documents on first call (lazy loading)
4. Knowledge added to agent kwargs

### 3. Each Agent Gets Own Knowledge Base

```python
# Demo agent
demo_config = {
    "knowledge_path": "examples/knowledge",
    "table_name": "demo_knowledge"
}

# GitHub agent
github_config = {
    "knowledge_path": "examples/github_knowledge",
    "table_name": "github_knowledge"
}
```

No code changes needed - just different config per agent!

### 4. Lazy Loading with Persistence

**First Request (slow, 10-60s)**:
- Scans `knowledge_path` for documents (MD, PDF, CSV)
- Generates embeddings via Gemini
- Indexes into LanceDB table
- Table persists to `${AGENTLLM_DATA_DIR}/lancedb/`

**Subsequent Requests (fast, <1s)**:
- Checks if table exists
- Skips indexing if table has data
- Uses existing vectors for retrieval

## Configuration Requirements

### Required Parameters

`KnowledgeManager` requires explicit configuration:

```python
manager = KnowledgeManager(
    knowledge_path="examples/knowledge",  # Required: path to documents
    table_name="my_table",                # Required: LanceDB table name
    vector_db_path="/custom/lancedb",     # Optional: defaults to tmp/lancedb
)
```

**Validation**:
- `knowledge_path` cannot be empty or None
- `table_name` cannot be empty, None, or whitespace-only
- Raises `ValueError` if validation fails

### Default Paths

- **Vector DB**: `${AGENTLLM_DATA_DIR}/lancedb` (defaults to `tmp/lancedb`)
- **Knowledge path**: Must be provided by agent configurator
- **Table name**: Must be provided by agent configurator

**No environment variables** are used for knowledge configuration.

## File Organization

```
examples/
├── knowledge/              # Demo agent knowledge
│   ├── acmeviz_company.md
│   ├── quantumflux_api.md
│   └── zorbonian_recipes.md
└── my_agent_knowledge/     # Custom agent knowledge
    ├── docs.md
    ├── api_reference.pdf
    └── data.csv

tmp/lancedb/                # Vector database (persisted)
├── demo_knowledge.lance/   # Demo agent table
└── my_agent_knowledge.lance/  # Custom agent table
```

## Adding RAG to an Agent

### Step 1: Create Knowledge Directory

```bash
mkdir -p examples/my_agent_knowledge
echo "# My Knowledge" > examples/my_agent_knowledge/intro.md
```

### Step 2: Override _get_knowledge_config()

```python
class MyAgentConfigurator(AgentConfigurator):
    def _get_knowledge_config(self) -> dict[str, Any] | None:
        return {
            "knowledge_path": "examples/my_agent_knowledge",
            "table_name": "my_agent_knowledge"
        }
```

**That's it!** The base class handles everything else automatically.

### Step 3: Optional - Disable Knowledge

Return `None` to disable RAG for an agent:

```python
def _get_knowledge_config(self) -> dict[str, Any] | None:
    return None  # No knowledge base for this agent
```

## Testing

### Test Isolation

Clear the factory cache between tests:

```python
@pytest.fixture
def my_configurator(shared_db, token_storage):
    # Clear factory cache for test isolation
    from agentllm.knowledge import KnowledgeManagerFactory
    KnowledgeManagerFactory.clear_cache()

    return MyAgentConfigurator(
        user_id="test_user",
        shared_db=shared_db,
        token_storage=token_storage,
    )
```

### Test-Specific Vector DB

Use temporary directories for test vector DBs:

```python
@pytest.fixture
def knowledge_manager(tmp_path):
    return KnowledgeManager(
        knowledge_path=Path("examples/knowledge"),
        table_name="test_knowledge",
        vector_db_path=tmp_path / "lancedb",  # Isolated per test
    )
```

## Supported File Types

- **Markdown** (`.md`) - Primary format for documentation
- **PDF** (`.pdf`) - Scanned documents, manuals
- **CSV** (`.csv`) - Structured data, tables

**File Filtering**:
- Files < 50 bytes are ignored (empty files)
- Maximum file size enforced by LanceDB
- Non-existent paths create empty knowledge bases

## Search Capabilities

**Hybrid Search** (vector + keyword):
- Vector similarity via embeddings
- Keyword matching via BM25
- Combined scoring for best results

**Retrieval Process**:
1. User query embedded via Gemini
2. Vector similarity search in LanceDB
3. Keyword matching on original text
4. Hybrid ranking of results
5. Top-k results returned to agent

## Performance Characteristics

**Indexing Time**:
- Small docs (< 10 files): ~5-10 seconds
- Medium docs (10-50 files): ~20-40 seconds
- Large docs (50+ files): ~60+ seconds

**Query Time**:
- Embedding generation: ~200-500ms
- Vector search: ~10-50ms
- Total: ~300-600ms per query

**Optimization**:
- Table persistence avoids re-indexing
- Factory caching prevents duplicate managers
- Lazy loading defers cost until needed

## Troubleshooting

### Knowledge Not Loading

**Check paths exist**:
```bash
ls -la examples/knowledge/
ls -la tmp/lancedb/
```

**Verify documents found**:
```python
km = KnowledgeManager(knowledge_path="examples/knowledge", table_name="test")
md_files, pdf_files, csv_files = km._count_documents()
print(f"Found: {len(md_files)} MD, {len(pdf_files)} PDF, {len(csv_files)} CSV")
```

### Table Exists But Empty

Force reindexing:
```python
knowledge_manager.reindex(force=True)
```

### Embeddings Failing

**Check API key**:
```bash
echo $GEMINI_API_KEY
```

**Test embedding directly**:
```python
from agno.knowledge.embedder.google import GeminiEmbedder
embedder = GeminiEmbedder(id="gemini-embedding-001")
result = embedder.embed("test")
print(f"Embedding dimensions: {len(result)}")
```

### Permission Errors

**Check directory permissions**:
```bash
chmod -R 755 tmp/lancedb
chmod -R 755 examples/knowledge
```

## Advanced Topics

### Custom Vector DB Path

Override the default vector DB location:

```python
def _get_knowledge_config(self) -> dict[str, Any] | None:
    return {
        "knowledge_path": "examples/knowledge",
        "table_name": "my_table",
        "vector_db_path": "/mnt/persistent/lancedb"  # Custom location
    }
```

### Multiple Knowledge Sources

Combine multiple directories by symlinking or copying:

```bash
mkdir -p examples/combined_knowledge
ln -s ../dir1/*.md examples/combined_knowledge/
ln -s ../dir2/*.md examples/combined_knowledge/
```

### Monitoring Index Status

```python
km = KnowledgeManagerFactory.get_cached_instance("my-agent")
if km:
    table_exists = km.check_table_exists()
    print(f"Table exists: {table_exists}")
```

## References

- [Agno Knowledge Documentation](https://docs.agno.com/knowledge)
- [LanceDB Documentation](https://lancedb.github.io/lancedb/)
- [Gemini Embeddings](https://ai.google.dev/gemini-api/docs/embeddings)
