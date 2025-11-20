# Demo Agent Accuracy Evaluation Tests

Consolidated accuracy evaluation tests for the Demo Agent using Agno's evaluation framework.

## Test Structure

All tests are in `test_demo_agent.py` (8 focused tests):

### Basic Functionality (3 tests)
- ✅ Basic greeting and capability listing
- ✅ Configuration prompt when not configured
- ✅ Color palette tool usage

### RAG Knowledge Retrieval (3 tests)
- ✅ **AcmeViz**: CEO query (company information)
- ✅ **Zorbonian**: Recipe ingredients (fictional recipes)
- ✅ **QuantumFlux**: API base URL (API documentation)

### Edge Cases & Integration (2 tests)
- ✅ Unknown topic handling (no hallucination)
- ✅ Mixed capabilities (tools + knowledge)

## Fixtures (conftest.py)

Shared pytest fixtures:
- `shared_db`: File-based SQLite database (in temp directory)
- `token_storage`: Token storage instance
- `demo_configurator`: DemoAgentConfigurator instance (knowledge loaded automatically)
- `configured_demo_configurator`: Pre-configured configurator (favorite color set)

Note: Knowledge loading is automatic via `_get_knowledge_config()` in the configurator.

## Running Tests

### Run All Evaluation Tests
```bash
# Run all eval tests
pytest tests/demo_agent/ -v -m eval

# Run all eval tests with output
pytest tests/demo_agent/ -v -s -m eval
```

### Run Specific Tests
```bash
# Run single test
pytest tests/demo_agent/test_demo_agent.py::test_rag_acmeviz -v -s

# Run all RAG tests
pytest tests/demo_agent/ -v -s -k "rag"

# Run only basic functionality tests
pytest tests/demo_agent/ -v -s -k "basic or configuration or color"
```

### Run Without Integration Tests
```bash
# Skip integration tests (faster, no knowledge loading)
pytest tests/demo_agent/ -v -m "eval and not integration"
```

### Run Without Eval Tests
```bash
# Exclude eval tests from normal test runs
pytest -m "not eval"
```

## Test Markers

Tests use the following pytest markers:

- `@pytest.mark.eval` - Accuracy evaluation test (may be slow)
- `@pytest.mark.integration` - Requires knowledge base loading (RAG tests)
- `@pytest.mark.asyncio` - Async test (not currently used)

## Evaluation Scores

Each test asserts a minimum accuracy score:

- **Basic functionality tests**: Score ≥ 6.5 - 7.0
- **RAG retrieval tests**: Score ≥ 7.0 - 8.5
- **Edge case tests**: Score ≥ 7.0

Scores are based on Gemini 2.0 Flash Exp evaluation.

## Knowledge Base Requirements

RAG tests require the example knowledge files in `examples/knowledge/`:
- `acmeviz_company.md` - Fictional company information
- `zorbonian_recipes.md` - Fictional recipes
- `quantumflux_api.md` - Fictional API documentation

The knowledge base is loaded automatically via `KnowledgeManagerFactory` when the agent is built.
Each test run clears the factory cache to ensure test isolation.

## What the Tests Verify

### Basic Functionality
- Agent responds appropriately to greetings
- Agent prompts for required configuration when missing
- Agent uses tools correctly (color palette generation)

### RAG Knowledge Retrieval
- **Correctness**: Agent retrieves accurate information from knowledge base
- **Coverage**: Agent can handle different document types (company info, recipes, API docs)
- **No hallucination**: Agent indicates when information is not available

### Integration
- Agent can combine tool usage with knowledge retrieval
- Responses are coherent and address all parts of questions

## Troubleshooting

### Tests Fail with Low Scores

If tests consistently fail with low accuracy scores:

1. **Check knowledge loading**: Ensure `examples/knowledge/` exists and contains the markdown files
2. **Verify agent configuration**: Check that favorite color is configured for `configured_demo_configurator` tests
3. **Review evaluation output**: Use `-s` flag to see detailed evaluation results
4. **Adjust score thresholds**: If needed, lower the assertion thresholds in individual tests

### Knowledge Base Not Loading

If RAG tests fail to retrieve knowledge:

1. Check that `GEMINI_API_KEY` is set in environment
2. Verify LanceDB is installed: `pip show lancedb`
3. Check tmp directory permissions
4. Run with verbose logging: `pytest -v -s --log-cli-level=DEBUG`

## CI/CD Integration

For CI/CD pipelines:

```bash
# Run eval tests with JUnit XML output
pytest tests/demo_agent/ -m eval --junitxml=eval-results.xml

# Run with coverage
pytest tests/demo_agent/ -m eval --cov=agentllm --cov-report=html

# Run with timeout
pytest tests/demo_agent/ -m eval --timeout=300
```

## Development Tips

### Adding New Evaluation Tests

1. Add test to `test_demo_agent.py` in appropriate section
2. Use `configured_demo_configurator` fixture for most tests
3. Set appropriate `num_iterations` (1-2 typical)
4. Write clear `expected_output` and `additional_guidelines`
5. Assert reasonable score threshold based on test difficulty

### Debugging Evaluation Results

Use `print_results=True` in `evaluation.run()` to see:
- Individual iteration scores
- Average score
- Evaluator's reasoning
- Agent's actual output vs expected output

Example:
```python
result = evaluation.run(print_results=True)
print(f"Scores: {result.scores}")
print(f"Average: {result.avg_score}")
```
