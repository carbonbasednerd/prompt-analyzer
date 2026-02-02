# Prompt Analyzer - Architecture Documentation

## System Overview

Prompt Analyzer is a proof-of-concept system for detecting contradictions in AI agent instructions. It follows a pipeline architecture with clear separation of concerns.

## Core Pipeline

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Instruction│────▶│   Ledger    │────▶│  Extractor  │────▶│   Monitor   │
│   Events    │     │   Service   │     │   Service   │     │   Service   │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                           │                    │                    │
                           ▼                    ▼                    ▼
                    ┌──────────┐        ┌──────────┐        ┌──────────┐
                    │  Events  │        │  Claims  │        │Conflicts │
                    │  JSONL   │        │  JSONL   │        │  JSONL   │
                    └──────────┘        └──────────┘        └──────────┘
```

## Component Details

### 1. Ledger Service

**Responsibility:** Append-only storage of instruction events

**Technology:**
- FastAPI for REST API
- JSONL files for storage (session-based)
- SSE (Server-Sent Events) for real-time streaming

**Key Features:**
- Atomic append operations
- Session-based file partitioning
- Timestamp-based queries
- Real-time event streaming

**Storage Pattern:**
- Primary: `data/ledger/{session_id}.jsonl`
- Each line = one event (JSON)
- Never modified after write

**API Endpoints:**
- `POST /ledger/append` - Add new event
- `GET /ledger/session/{id}` - Get all events
- `GET /ledger/events` - Query by timestamp
- `GET /ledger/stream` - SSE stream
- `GET /health` - Health check

### 2. Extractor Service

**Responsibility:** Extract semantic claims from instruction text

**Technology:**
- FastAPI for REST API
- Ollama for local LLM inference
- Pydantic for validation

**Key Features:**
- Deterministic extraction (temperature=0.0)
- JSON mode output
- Strict Pydantic validation
- Error recovery

**Extraction Process:**
1. Receive instruction text
2. Build prompt with examples
3. Call Ollama LLM (llama3.1:8b)
4. Parse JSON output
5. Validate with Pydantic
6. Return validated claims

**Claim Structure:**
```python
{
  "modality": "must|must_not|should|prefer|avoid|allowed",
  "action": "file_write|internet_access|...",
  "target": "specific target",
  "conditions": [...],
  "exceptions": [...],
  "confidence": 0.0-1.0,
  "evidence": ["verbatim quotes"]
}
```

**API Endpoints:**
- `POST /extract` - Extract from single event
- `POST /extract/batch` - Extract from multiple events
- `GET /health` - Health check

### 3. Monitor Service

**Responsibility:** Orchestrate pipeline and detect conflicts

**Technology:**
- FastAPI for REST API
- httpx for async HTTP client
- Rule-based conflict detection

**Key Features:**
- Polling-based event watching
- Automatic claim extraction
- Rule-based contradiction detection
- Processing state tracking (for recovery)

**Processing Flow:**
1. Poll ledger for new events
2. Check if event already processed
3. Call extractor for each new event
4. Save claims to JSONL
5. Load all claims for session
6. Run conflict detection
7. Save conflicts to JSONL
8. Log processing state

**Conflict Detection Algorithm:**
```python
For each (action, target) pair:
  For each pair of claims:
    If modalities contradict (e.g., must vs must_not):
      If scopes overlap:
        Assess severity based on conditions
        Create conflict record
```

**Severity Assessment:**
- **hard**: No conditions, always applies
- **soft**: Conditional or exceptional cases
- **scope**: Different scopes but overlapping
- **style**: Preference conflicts (prefer vs avoid)

**API Endpoints:**
- `GET /monitor/status` - Pipeline status
- `GET /monitor/claims/{id}` - Get claims
- `GET /monitor/conflicts/{id}` - Get conflicts
- `GET /health` - Health check

### 4. Ollama Service

**Responsibility:** Local LLM inference

**Technology:**
- Official Ollama Docker image
- llama3.1:8b model

**Key Features:**
- Automatic model pulling on startup
- JSON mode output
- Temperature control

**Model Choice Rationale:**
- llama3.1:8b - Good instruction following
- Fits on consumer hardware (8GB RAM)
- Fast enough for real-time extraction
- Can upgrade to larger models if needed

## Data Schemas

### Event Schema v1.0

```json
{
  "schema_version": "1.0",
  "event_id": "evt_{uuid}",
  "session_id": "session_{id}",
  "ts": "ISO8601 timestamp",
  "source": "user|system|developer|memory|claude_md|skill|tool_output|agent_internal",
  "scope": "global|conversation|task|step|file",
  "text": "Raw instruction text",
  "metadata": {}
}
```

**Source Types:**
- `user` - Direct user input
- `system` - System-generated instructions
- `developer` - Developer configuration
- `memory` - Retrieved from memory system
- `claude_md` - From CLAUDE.md files
- `skill` - Skill/command invocation
- `tool_output` - Tool feedback/constraints
- `agent_internal` - Agent reasoning/decisions

**Scope Hierarchy:**
```
global           (0) - Affects everything
  └─ conversation (1) - Affects conversation
      └─ task      (2) - Affects task
          └─ step   (3) - Affects step
              └─ file (4) - Affects specific file
```

### Claim Schema v1.0

```json
{
  "schema_version": "1.0",
  "claim_id": "clm_{uuid}",
  "session_id": "session_{id}",
  "event_id": "evt_{uuid}",
  "modality": "must|must_not|should|prefer|avoid|allowed",
  "action": "string (extensible vocabulary)",
  "target": "string",
  "conditions": ["string", ...],
  "exceptions": ["string", ...],
  "confidence": 0.0-1.0,
  "evidence": ["verbatim quotes"]
}
```

**Modality Meanings:**
- `must` - Required action
- `must_not` - Forbidden action
- `should` - Recommended action
- `prefer` - Preferred option
- `avoid` - Not recommended
- `allowed` - Explicitly permitted

**Action Vocabulary (Initial):**
- `file_write`, `file_read`, `file_delete`
- `internet_access`, `api_call`
- `tool_use`, `command_execute`
- `modify_prod`, `deploy`
- `output_format`, `set_verbosity`
- `secrets_pii`, `data_access`

**Extensibility:** LLM can create new action names as needed.

### Conflict Schema v1.0

```json
{
  "schema_version": "1.0",
  "conflict_id": "cfl_{uuid}",
  "session_id": "session_{id}",
  "claims": ["clm_id1", "clm_id2"],
  "severity": "hard|soft|scope|style",
  "explanation": "Human-readable explanation",
  "confidence": 0.0-1.0
}
```

## Design Decisions

### 1. Append-Only Storage (JSONL)

**Decision:** Use JSONL files as primary storage

**Rationale:**
- Simple, human-readable
- Append-only audit trail
- Easy backup/recovery
- No database dependencies
- Proven pattern (from jay-i memory system)

**Trade-offs:**
- Linear scan for queries (acceptable for PoC)
- No indexing (can add SQLite later)
- File handle management

### 2. Session-Based Partitioning

**Decision:** One JSONL file per session

**Rationale:**
- Natural isolation boundary
- Prevents file size growth
- Enables parallel processing
- Simplifies cleanup

**Trade-offs:**
- Cross-session queries more complex
- File proliferation (manageable)

### 3. Deterministic LLM Extraction

**Decision:** Use temperature=0.0 and JSON mode

**Rationale:**
- Reproducible results
- Easier to debug
- Reduces hallucinations
- Matches PoC goal (LLM as tool, not authority)

**Trade-offs:**
- May miss creative interpretations
- Less robust to prompt variations

### 4. Rule-Based Conflict Detection

**Decision:** Start with rule-based, not LLM-based

**Rationale:**
- Fast and deterministic
- Easy to test and explain
- No LLM cost per comparison
- Sufficient for PoC validation

**Trade-offs:**
- Misses semantic conflicts
- Requires exact action/target match
- No fuzzy matching

**Future Enhancement:** Add LLM-based semantic layer.

### 5. Polling vs Streaming

**Decision:** Use polling in monitor, offer SSE in ledger

**Rationale:**
- Polling is simpler to implement
- SSE available for future optimization
- Acceptable latency for PoC (5s default)

**Trade-offs:**
- 5-10s processing delay
- Network overhead (minimal)

### 6. Extensible Vocabulary

**Decision:** Allow LLM to create action names dynamically

**Rationale:**
- Handles new domains without retraining
- More flexible than fixed vocabulary
- Can normalize post-processing

**Trade-offs:**
- Synonym problem (e.g., "modify_file" vs "file_write")
- Harder to query
- Requires normalization layer (future)

## Error Recovery Strategy

### Processing State Log

Monitor service maintains `data/monitor/processing_log.jsonl`:

```json
{
  "event_id": "evt_...",
  "session_id": "session_...",
  "state": "pending|processing|completed|failed",
  "attempts": 1,
  "last_error": "error message",
  "timestamp": "ISO8601",
  "claims_extracted": 0
}
```

### Recovery Logic

On startup:
1. Load processing log
2. Identify `PENDING` or `FAILED` events (attempts < 3)
3. Retry extraction
4. Update state

### Failure Handling

- LLM timeout: Retry up to 3 times
- JSON parse error: Log warning, skip event
- Validation error: Log warning, skip claim
- Service unavailable: Log error, retry on next poll

## Performance Considerations

### Current (PoC)

- **Throughput:** ~10-20 events/minute (LLM bound)
- **Latency:** 5-10s per event (extraction time)
- **Storage:** ~1KB per event, ~500B per claim
- **Memory:** ~500MB per service + 4GB for Ollama

### Optimization Opportunities

1. **Batch Processing:** Extract multiple events in parallel
2. **Caching:** Deduplicate identical instruction texts
3. **SQLite Index:** Add fast queries without changing storage
4. **Faster Model:** Use smaller/quantized models
5. **Streaming:** Replace polling with SSE push

## Security Considerations

### Current Limitations (PoC)

- No authentication/authorization
- No rate limiting
- No input sanitization (JSON only)
- No secrets management
- Local network only

### Production Requirements

- Add API key authentication
- Implement rate limiting
- Sanitize/validate all inputs
- Encrypt sensitive data
- Add audit logging
- Network isolation
- HTTPS/TLS

## Testing Strategy

### Unit Tests (Future)

- Event validation
- Claim extraction parsing
- Contradiction detection logic
- Scope overlap calculation

### Integration Tests (Future)

- End-to-end: event → claim → conflict
- Service health checks
- Error recovery scenarios

### Example Scenarios (Included)

1. Simple contradiction (hard conflict)
2. Scope-based conflict (soft/none)
3. Conditional conflict (soft)

## Future Enhancements

### Phase 2: Robustness

- [ ] SQLite indexing
- [ ] Advanced scope hierarchy logic
- [ ] Condition comparison improvements
- [ ] Semantic conflict detection (LLM)
- [ ] Schema versioning/migration

### Phase 3: Features

- [ ] Web UI (React/Vue dashboard)
- [ ] Real-time notifications
- [ ] Multi-session analysis
- [ ] Claim clustering
- [ ] Export/import functionality
- [ ] Vocabulary normalization

### Phase 4: Integration

- [ ] Claude Code integration
- [ ] jay-i memory system integration
- [ ] File watching (CLAUDE.md)
- [ ] Feedback loop (auto-update CLAUDE.md)

## References

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Ollama Documentation](https://ollama.ai/docs)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [JSONL Format](http://jsonlines.org/)
- [jay-i Memory System](../.claude/memory/) - Inspiration for append-only pattern
