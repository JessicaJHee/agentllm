# Streaming Reasoning (Future Enhancement)

## Overview

Stream reasoning tokens incrementally to users in real-time as Gemini generates them, rather than waiting for complete reasoning block.

## Current Implementation (Option 2)

The current implementation uses a "complete block" approach:

- **Behavior**: Reasoning content is accumulated during generation
- **Duration**: Typically 350-500ms (based on production logs)
- **Output**: Complete `<details>` block sent with `done="true"` and final duration
- **User Experience**: Brief pause, then complete reasoning block appears, then response streams

**Advantages**:
- ✅ Matches Open WebUI's expected format exactly
- ✅ Clean, complete reasoning block with accurate duration
- ✅ Reliable across all scenarios
- ✅ Simple implementation
- ✅ Fast enough for good UX (<1 second typically)

**Implementation Details**:
```python
# In base_agent.py _arun_streaming() method:
reasoning_start_time = None
reasoning_content_parts = []
reasoning_block_sent = False

# Accumulate reasoning from RunContentEvent.reasoning_content
if hasattr(chunk, "reasoning_content") and chunk.reasoning_content:
    if reasoning_start_time is None:
        reasoning_start_time = time.time()
    reasoning_content_parts.append(chunk.reasoning_content)
    continue  # Don't yield yet

# When first regular content arrives, send complete reasoning block
if reasoning_content_parts and not reasoning_block_sent:
    duration = int(time.time() - reasoning_start_time)
    full_content = "".join(reasoning_content_parts)
    formatted = _format_reasoning_content(full_content)

    yield {
        "text": f'<details type="reasoning" done="true" duration="{duration}">\n'
                f'<summary>Thought for {duration} seconds</summary>\n\n'
                f'{formatted}\n\n</details>\n\n',
        ...
    }
    reasoning_block_sent = True
```

## Proposed Enhancement (Option 1): Streaming Reasoning

### User Experience

**Goal**: Show agent "thinking in real-time" as Gemini generates thinking tokens.

**Benefits**:
- More engaging and transparent
- User sees progress during thinking
- Better perceived performance for long reasoning sessions

**Example**:
```
[Expandable block appears]
💭 Thinking...
> Analyzing the problem...
> [text appears word-by-word]
> Breaking down into steps...
> [more text streams in]

[Block updates when complete]
💭 Thought for 3 seconds
```

### Technical Approach

#### 1. Progressive Disclosure Pattern

Send reasoning in stages as it arrives:

```python
# State machine for streaming reasoning
reasoning_state = "NOT_STARTED"  # → "STREAMING" → "COMPLETED"

# On first reasoning content:
if reasoning_state == "NOT_STARTED":
    yield {
        "text": '<details type="reasoning" done="false">\n'
                '<summary>💭 Thinking...</summary>\n',
        ...
    }
    reasoning_state = "STREAMING"

# On each reasoning chunk:
if reasoning_state == "STREAMING":
    formatted_chunk = _format_reasoning_content(chunk.reasoning_content)
    yield {
        "text": formatted_chunk + "\n",
        ...
    }

# On reasoning completion (first regular content):
if reasoning_state == "STREAMING":
    duration = int(time.time() - reasoning_start_time)
    yield {
        "text": f'</details>\n\n',  # Close the block
        ...
    }
    # Or update summary (if Open WebUI supports it):
    # yield {
    #     "text": f'<summary>Thought for {duration} seconds</summary>',
    #     ...
    # }
    reasoning_state = "COMPLETED"
```

#### 2. Challenges to Investigate

##### Open WebUI Compatibility

**Unknown factors:**
- Does Open WebUI support `done="false"` → `done="true"` state transitions?
- Can we update `<summary>` text from "Thinking..." to "Thought for X seconds"?
- How does Open WebUI handle incremental updates to `<details>` blocks?

**Required testing:**
1. Send partial `<details>` block with `done="false"`
2. Stream content into the block incrementally
3. Close block or update attributes when complete
4. Verify rendering in Open WebUI

##### Gemini Streaming Behavior

**Questions:**
- Does Gemini stream thinking tokens incrementally?
- Or does it send them in a burst after thinking completes?
- What is the typical chunk size for reasoning content?

**Investigation needed:**
```python
# Add detailed logging to track chunk timing
async for chunk in stream:
    if hasattr(chunk, "reasoning_content") and chunk.reasoning_content:
        timestamp = time.time()
        chunk_size = len(chunk.reasoning_content)
        logger.info(f"Reasoning chunk at {timestamp}: {chunk_size} chars")
```

**Hypothesis**: If Gemini sends reasoning in a single burst (based on 350-500ms completion times in logs), streaming may not provide meaningful UX improvement.

#### 3. Alternative Approaches

##### Approach A: Dual-Phase Display

Show thinking status first, then complete block:

```html
<!-- Phase 1: Show status while thinking -->
<div class="reasoning-status">
💭 Thinking (3s elapsed)...
</div>

<!-- Phase 2: Replace with complete block when done -->
<details type="reasoning" done="true" duration="3">
<summary>Thought for 3 seconds</summary>
> **Complete reasoning content here**
</details>
```

**Pros**:
- Compatible with current Open WebUI format
- Shows progress without HTML complexity
- Easy to implement

**Cons**:
- Doesn't show actual thinking content in real-time
- Just a status indicator

##### Approach B: Progressive Content with Final Summary

Stream reasoning content as plain text, then wrap in `<details>` when complete:

```html
<!-- While streaming -->
💭 Analyzing the problem...
[content appears line by line]
Breaking down into steps...
[more content]

<!-- When complete, wrap in details block -->
<details type="reasoning" done="true" duration="3">
<summary>Thought for 3 seconds</summary>
> Analyzing the problem...
> Breaking down into steps...
[same content, now collapsed]
</details>
```

**Pros**:
- Content visible immediately
- Final format matches Open WebUI expectations
- No need for HTML state updates

**Cons**:
- Content appears twice (streaming + collapsed)
- May be visually cluttered

##### Approach C: Server-Sent Events for Status

Use a separate status channel:

```python
# Send thinking status updates separately
yield {
    "text": "",
    "metadata": {"thinking_status": "in_progress", "elapsed": 2},
    ...
}

# Then send complete reasoning block when done
yield {
    "text": '<details type="reasoning"...>',
    ...
}
```

**Pros**:
- Clean separation of status and content
- No HTML complexity

**Cons**:
- Requires Open WebUI support for metadata
- May not be supported

### Implementation Roadmap

#### Phase 1: Investigation (1-2 hours)

1. **Test Gemini streaming behavior**:
   ```bash
   # Enable detailed logging
   LOG_LEVEL=DEBUG nox -s proxy
   # Send reasoning prompts and analyze chunk timing
   ```

2. **Test Open WebUI rendering**:
   - Send partial `<details>` blocks manually
   - Test different HTML update patterns
   - Document what renders correctly

3. **Measure user impact**:
   - Current pause duration: 350-500ms (acceptable?)
   - Would streaming provide meaningful improvement?
   - Survey user feedback if available

#### Phase 2: Prototype (2-3 hours)

If investigation shows:
- ✅ Gemini streams thinking incrementally
- ✅ Open WebUI handles progressive HTML updates
- ✅ User feedback indicates desire for real-time thinking

Then implement:
1. Modify `base_agent.py` to use streaming state machine
2. Add configuration flag: `ENABLE_STREAMING_REASONING` (default: False)
3. Test with demo agent
4. Gather user feedback

#### Phase 3: Production (1 hour)

If prototype is successful:
1. Remove configuration flag (make it default)
2. Update documentation
3. Monitor for issues

### Decision Criteria

**Implement streaming reasoning (Option 1) when:**

| Criterion | Status | Required |
|-----------|--------|----------|
| Gemini streams thinking incrementally | ❓ Unknown | ✅ Yes |
| Open WebUI handles progressive HTML | ❓ Unknown | ✅ Yes |
| Current pause is noticeable/frustrating | ❓ Unknown | ⚠️ Recommended |
| Streaming provides measurable UX improvement | ❓ Unknown | ⚠️ Recommended |

**Current recommendation**: Investigate first, then decide.

### Compatibility Notes

**Current format works with Open WebUI**:
```json
{
  "model": "gemini-2.5-pro",
  "messages": [...],
  "chat_id": "...",
  "id": "...",
  "role": "assistant",
  "content": "<details type=\"reasoning\" done=\"true\" duration=\"22\">..."
}
```

This format is proven to work (based on user-provided example). Any changes risk breaking compatibility.

**Risk assessment**:
- **Low risk**: Adding status indicators (Approach A)
- **Medium risk**: Streaming content with state updates (Approach B)
- **High risk**: Changing HTML structure or attributes (original Approach)

### Testing Plan

#### Test 1: Gemini Streaming Behavior

```python
# In demo_agent.py or test file
import asyncio
import time
from agno.agent import Agent
from agno.models.google import Gemini

async def test_gemini_streaming():
    agent = Agent(
        model=Gemini(
            id="gemini-2.5-pro",
            thinking_budget=200,
            include_thoughts=True,
        ),
        reasoning=True,
    )

    start = time.time()
    async for chunk in agent.arun(
        "Think hard about: 2341234/2134234×23+4",
        stream=True,
        stream_events=True,
    ):
        if hasattr(chunk, "reasoning_content") and chunk.reasoning_content:
            elapsed = time.time() - start
            print(f"[{elapsed:.3f}s] Reasoning chunk: {len(chunk.reasoning_content)} chars")
            print(f"  Content: {chunk.reasoning_content[:100]}...")

asyncio.run(test_gemini_streaming())
```

**Expected outputs**:
- **Incremental**: Multiple chunks over 350-500ms period
- **Burst**: Single chunk near end of 350-500ms period

#### Test 2: Open WebUI HTML Rendering

```bash
# Start local proxy
nox -s proxy

# Send test request with progressive HTML
curl -X POST http://localhost:8890/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-agno-test-key-12345" \
  -d '{
    "model": "agno/demo-agent",
    "messages": [
      {"role": "user", "content": "test progressive reasoning"}
    ],
    "stream": true
  }'
```

Manually modify `base_agent.py` to send progressive updates and observe rendering in Open WebUI.

### References

- **Current implementation**: `src/agentllm/agents/base_agent.py` lines 768-849
- **Gemini thinking docs**: Agno library `.venv/lib/python3.11/site-packages/agno/reasoning/gemini.py`
- **RunContentEvent structure**: `.venv/lib/python3.11/site-packages/agno/run/agent.py`
- **Open WebUI format example**: Provided by user showing `done="true"` and `duration` attributes

### Timeline Estimate

- **Investigation**: 1-2 hours
- **Prototype** (if proceeding): 2-3 hours
- **Production** (if successful): 1 hour
- **Total**: 4-6 hours

### Conclusion

The current Option 2 implementation provides:
- ✅ Reliable, proven compatibility with Open WebUI
- ✅ Good UX (sub-second pause)
- ✅ Simple, maintainable code
- ✅ Complete reasoning visibility

Option 1 (streaming) is worth investigating if:
- User feedback indicates the pause is problematic
- Gemini actually streams thinking incrementally
- We confirm Open WebUI can handle progressive updates

**Recommended next steps**:
1. Gather user feedback on current experience
2. If feedback is positive, keep Option 2
3. If feedback indicates issues, proceed with investigation phase for Option 1
