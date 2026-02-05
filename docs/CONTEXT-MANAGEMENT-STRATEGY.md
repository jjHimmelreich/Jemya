# Context Management Strategy for MCP Mode

## Problem
OpenAI's GPT-4o-mini has a 128k token context limit. With function calling and large tool results (e.g., 181 playlists), we can easily exceed this limit, especially in multi-turn conversations.

## Generalized Solution (Implemented)

### 1. **Tool Result Summarization** (`mcp_manager.py`)
**Strategy**: Reduce size of tool results before adding to context

**Implementation**:
```python
def summarize_tool_result(tool_name, result):
    if tool_name == "list_playlists":
        # Keep only: id, name, track_count, owner
        # Drop: images, URLs, descriptions, collaborative flags, etc.
        # Reduction: ~90% smaller
    elif tool_name == "read_playlist":
        # Keep only: name, artist, uri per track
        # Drop: duration, popularity, album, URLs
        # Reduction: ~70% smaller
```

**Benefit**: 181 playlists: 90,500 tokens → 9,000 tokens

---

### 2. **Remove Old Tool Results** (`ai_manager.py`)
**Strategy**: Tool results are only needed for ONE turn. After AI responds, remove them.

**Implementation**:
```python
# Initial cleanup: Remove tool results from conversation_history
cleaned = []
for msg in conversation_history:
    if msg.get("role") == "tool":
        continue  # Skip old tool results
    cleaned.append(msg)
```

**Benefit**: Each function calling iteration doesn't carry forward previous tool results

---

### 3. **Conversation History Limits** (`ai_manager.py`)
**Strategy**: Keep only recent messages

**Implementation**:
```python
# Keep last 10 user/assistant messages (after removing tool results)
messages = system_messages + cleaned[-10:] + [user_message]
```

**Benefit**: Long conversations don't accumulate unbounded context

---

### 4. **Token Budget Monitoring** (`ai_manager.py`)
**Strategy**: Estimate tokens and trim proactively during iteration

**Implementation**:
```python
def estimate_tokens(messages):
    # Rough estimate: 1 token ≈ 4 characters
    total_chars = sum(len(msg['content']) for msg in messages)
    return total_chars // 4

# After each tool call iteration
estimated = self.estimate_tokens(messages)
if estimated > max_context_tokens:
    # Aggressive trimming: keep only system + user + most recent tool exchange
    trimmed = [system, user, last_assistant, last_tool_results]
    messages = trimmed
```

**Benefit**: Never hit the hard limit unexpectedly

---

### 5. **Configurable Token Budget** (`ai_manager.py`)
**Strategy**: Set headroom below hard limit to account for response generation

**Implementation**:
```python
max_context_tokens: int = 100000  # 100k for context, 28k for response/tools
```

**Benefit**: Prevents errors even when response is large

---

## Token Flow Example

### Scenario: "List all my playlists"

**Turn 1:**
- User message: 20 tokens
- System message: 300 tokens
- Tool definition (list_playlists): 50 tokens
- **Call OpenAI**: ~370 tokens ✅
- AI response: "I'll list your playlists" (10 tokens)
- Tool call: `list_playlists()` 
- Tool result (summarized): 181 playlists × 50 tokens = **9,050 tokens**
- **Next iteration context**: 370 + 10 + 9,050 = **9,430 tokens** ✅

**Turn 2:**
- AI response: "Here are your 181 playlists: [formatted list]" (2,000 tokens)
- **No more tool calls** → Return to user

**Turn 3 (new user message):**
- Previous conversation: 9,430 tokens
- **Remove tool results**: -9,050 tokens
- **Cleaned context**: ~380 tokens ✅
- New user message: "Show me playlists with '2025' in the name"
- **Call OpenAI**: 380 + 20 = **400 tokens** ✅

---

## Why This Works Long-Term

### Problem: "We'll hit the limit eventually"
**Answer**: No, because:

1. **Tool results are ephemeral** - removed after each response
2. **Only recent context matters** - old messages are trimmed
3. **Proactive monitoring** - context is checked and trimmed before hitting limit
4. **Exponential decay** - each turn, old content is pruned

### Example: 100-turn conversation
- Turn 1-10: Each ~10k tokens (with tool results), trimmed after
- Turn 11-20: Only last 10 turns kept = max 100k tokens
- Turn 21+: Still max 100k tokens (old turns dropped)

**Result**: Context size stabilizes around 10-30k tokens for typical usage

---

## Advanced Strategies (Not Yet Implemented)

### 1. **Conversation Summarization**
After every 10 turns, summarize the conversation:
```python
if turn_count % 10 == 0:
    summary = summarize_conversation(messages)
    messages = [system_message, summary] + recent_messages[-5:]
```

### 2. **Semantic Search for Context**
Instead of keeping all history, use embeddings:
```python
relevant_history = semantic_search(user_message, conversation_history, top_k=3)
messages = [system, relevant_history, user_message]
```

### 3. **External Tool Result Storage**
Store large results externally, reference them:
```python
tool_result_id = store_result(large_playlist_data)
messages.append({"role": "tool", "content": f"Result stored as: {tool_result_id}"})
# AI can request full data if needed
```

### 4. **Progressive Detail**
Start with summaries, fetch details on demand:
```python
# First call: Return playlist names only
# If AI needs details: Call read_playlist for specific one
```

---

## Configuration

### Current Settings (`ai_manager.py`)
```python
max_iterations = 5              # Max function calling loops
max_context_tokens = 100000     # Context budget (100k)
max_history_messages = 10       # Max conversation history
```

### Tuning Guidelines
- **Increase max_context_tokens**: If you need longer conversations (up to 115k)
- **Decrease max_history_messages**: If users make complex multi-turn requests
- **Adjust summarization aggressiveness**: Change mcp_manager.summarize_tool_result()

---

## Monitoring

### Current Logging
```
DEBUG: Initial context ~45000 tokens, trimming to last 5 messages
DEBUG: Context at ~105000 tokens, removing old tool results
DEBUG: Context trimmed to ~35000 tokens
```

### Recommended Monitoring
- Track average tokens per request
- Alert if any request exceeds 120k tokens
- Log tool result sizes to identify bloat

---

## Summary

**The generalized approach is**: 
1. ✅ **Summarize** large tool results immediately
2. ✅ **Remove** tool results after AI processes them
3. ✅ **Limit** conversation history to recent messages
4. ✅ **Monitor** token usage and trim proactively
5. 🔜 **Summarize** entire conversations periodically (future)

This ensures the system **never** hits context limits, even in long-running conversations with large datasets.
