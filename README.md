# Prompt Analyzer

[![GitHub](https://img.shields.io/badge/github-carbonbasednerd%2Fprompt--analyzer-blue?logo=github)](https://github.com/carbonbasednerd/prompt-analyzer)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

A proof-of-concept system for recording AI agent instructions and detecting contradictions using locally running models.

**Repository:** https://github.com/carbonbasednerd/prompt-analyzer

## Overview

Prompt Analyzer is an observability and analysis sidecar that:
- Records all instructions given to AI agents in an append-only ledger
- Extracts semantic claims from instructions using local LLMs
- Detects contradictions between instructions
- Provides offline analysis and reporting

**This is NOT:**
- An autonomous agent
- A chatbot
- Integrated with Claude Code (yet)

**This IS:**
- An observability and analysis sidecar
- A logging + semantic analysis pipeline
- An offline analysis tool

## Architecture

```
Instruction Events → Ledger → Claim Extraction → Conflict Detection → Report
```

### Components

1. **Ledger Service** (Port 8001)
   - Append-only JSONL storage
   - Session-based event tracking
   - REST API + SSE streaming

2. **Extractor Service** (Port 8002)
   - Semantic claim extraction
   - Local LLM via Ollama (llama3.1:8b)
   - Pydantic validation

3. **Monitor Service** (Port 8003)
   - Pipeline orchestration
   - Conflict detection (rule-based)
   - Processing state tracking

4. **Ollama** (Port 11434)
   - Local LLM inference
   - Automatic model pulling

## Quick Start

### Prerequisites

- Docker and Docker Compose
- 8GB+ RAM (for llama3.1:8b)
- 10GB+ free disk space

### Setup

1. Clone or navigate to the project directory:
```bash
cd prompt-analyzer
```

2. Start all services:
```bash
docker-compose up -d
```

This will:
- Pull and start Ollama
- Download llama3.1:8b model (~4GB)
- Build and start all services
- Create data directories

3. Wait for services to be healthy (check logs):
```bash
docker-compose logs -f
```

4. Check service health:
```bash
curl http://localhost:8001/health  # Ledger
curl http://localhost:8002/health  # Extractor
curl http://localhost:8003/health  # Monitor
```

### Basic Usage

#### 1. Append an Instruction Event

```bash
curl -X POST http://localhost:8001/ledger/append \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test_session",
    "source": "user",
    "scope": "global",
    "text": "Never modify production files"
  }'
```

#### 2. View Events for a Session

```bash
curl http://localhost:8001/ledger/session/test_session
```

#### 3. View Extracted Claims

```bash
curl http://localhost:8003/monitor/claims/test_session
```

#### 4. View Detected Conflicts

```bash
curl http://localhost:8003/monitor/conflicts/test_session
```

### Example: Detecting a Contradiction

1. Add first instruction:
```bash
curl -X POST http://localhost:8001/ledger/append \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "demo",
    "source": "user",
    "scope": "global",
    "text": "Never modify production files"
  }'
```

2. Add contradictory instruction:
```bash
curl -X POST http://localhost:8001/ledger/append \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "demo",
    "source": "user",
    "scope": "task",
    "text": "Update the production config file with new settings"
  }'
```

3. Wait a few seconds for processing, then check conflicts:
```bash
curl http://localhost:8003/monitor/conflicts/demo | jq
```

Expected output:
```json
[
  {
    "schema_version": "1.0",
    "conflict_id": "cfl_...",
    "session_id": "demo",
    "claims": ["clm_...", "clm_..."],
    "severity": "hard",
    "explanation": "Contradictory instructions: must_not file_write vs must file_write on 'production files'",
    "confidence": 0.925
  }
]
```

## API Documentation

### Ledger Service (Port 8001)

- `POST /ledger/append` - Append new event
- `GET /ledger/session/{id}` - Get all events for session
- `GET /ledger/events?start=&end=` - Query events by timestamp
- `GET /ledger/sessions` - List all session IDs
- `GET /ledger/stream?session_id=` - SSE stream of new events
- `GET /health` - Health check

### Extractor Service (Port 8002)

- `POST /extract` - Extract claims from single event
- `POST /extract/batch` - Extract from multiple events
- `GET /health` - Health check

### Monitor Service (Port 8003)

- `GET /monitor/status` - Pipeline status
- `GET /monitor/claims/{session_id}` - Get claims for session
- `GET /monitor/conflicts/{session_id}` - Get conflicts for session
- `GET /health` - Health check

Auto-generated OpenAPI docs available at:
- http://localhost:8001/docs (Ledger)
- http://localhost:8002/docs (Extractor)
- http://localhost:8003/docs (Monitor)

## Data Storage

All data is stored in the `data/` directory:

```
data/
├── ledger/           # Event JSONL files (session-{id}.jsonl)
├── claims/           # Claim JSONL files (session-{id}.jsonl)
├── conflicts/        # Conflict JSONL files (session-{id}.jsonl)
└── monitor/          # Processing state logs
```

### Event Schema

```json
{
  "schema_version": "1.0",
  "event_id": "evt_...",
  "session_id": "session_...",
  "ts": "2026-02-02T10:00:00Z",
  "source": "user|system|developer|memory|claude_md|skill|tool_output|agent_internal",
  "scope": "global|conversation|task|step|file",
  "text": "instruction text",
  "metadata": {}
}
```

### Claim Schema

```json
{
  "schema_version": "1.0",
  "claim_id": "clm_...",
  "session_id": "session_...",
  "event_id": "evt_...",
  "modality": "must|must_not|should|prefer|avoid|allowed",
  "action": "file_write|internet_access|...",
  "target": "specific target",
  "conditions": ["condition1", "condition2"],
  "exceptions": ["exception1"],
  "confidence": 0.95,
  "evidence": ["verbatim quote from text"]
}
```

### Conflict Schema

```json
{
  "schema_version": "1.0",
  "conflict_id": "cfl_...",
  "session_id": "session_...",
  "claims": ["clm_1", "clm_2"],
  "severity": "hard|soft|scope|style",
  "explanation": "human-readable explanation",
  "confidence": 0.92
}
```

## Development

### Viewing Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f monitor
docker-compose logs -f extractor
docker-compose logs -f ledger

# Last 100 lines
docker-compose logs --tail=100 monitor
```

### Rebuilding Services

```bash
# Rebuild all
docker-compose build

# Rebuild specific service
docker-compose build ledger

# Rebuild and restart
docker-compose up -d --build
```

### Stopping Services

```bash
# Stop all
docker-compose down

# Stop and remove volumes (WARNING: deletes all data)
docker-compose down -v
```

### Testing

Load example data:
```bash
# Copy examples to data directory
cp examples/sample_events.jsonl data/ledger/session_demo.jsonl

# Restart monitor to process
docker-compose restart monitor

# Check results
curl http://localhost:8003/monitor/claims/session_demo | jq
curl http://localhost:8003/monitor/conflicts/session_demo | jq
```

## Configuration

Environment variables (set in docker-compose.yml):

### Ledger
- `DATA_DIR` - Data directory path (default: /data/ledger)
- `LOG_LEVEL` - Logging level (default: INFO)

### Extractor
- `OLLAMA_HOST` - Ollama service URL (default: http://ollama:11434)
- `MODEL` - LLM model to use (default: llama3.1:8b)
- `LOG_LEVEL` - Logging level (default: INFO)

### Monitor
- `LEDGER_URL` - Ledger service URL (default: http://ledger:8000)
- `EXTRACTOR_URL` - Extractor service URL (default: http://extractor:8000)
- `DATA_DIR` - Data directory path (default: /data)
- `POLL_INTERVAL` - Polling interval in seconds (default: 5)
- `LOG_LEVEL` - Logging level (default: INFO)

## Troubleshooting

### Service won't start
- Check logs: `docker-compose logs [service]`
- Verify ports are not in use: `lsof -i :8001,8002,8003,11434`
- Check disk space: `df -h`

### Ollama model download fails
- Check internet connection
- Increase Docker resources (8GB+ RAM recommended)
- Manually pull: `docker-compose exec ollama ollama pull llama3.1:8b`

### Claims not being extracted
- Check extractor logs: `docker-compose logs extractor`
- Verify Ollama is healthy: `curl http://localhost:11434/api/tags`
- Check monitor logs for errors: `docker-compose logs monitor`

### No conflicts detected
- Verify claims were extracted: `curl http://localhost:8003/monitor/claims/{session_id}`
- Check that instructions actually contradict (same action/target, opposite modality)
- Review monitor logs for detection errors

## Future Enhancements

- [ ] Web UI for viewing conflicts
- [ ] Semantic conflict detection (LLM-based)
- [ ] SQLite index for fast queries
- [ ] Claim clustering and analysis
- [ ] Integration with Claude Code / jay-i
- [ ] Export/import functionality
- [ ] Real-time notifications
- [ ] Multi-session conflict detection
- [ ] Confidence scoring improvements
- [ ] Action vocabulary normalization

## Design Principles

- **Append-only audit trail** - Never modify historical data
- **Deterministic where possible** - LLM used as structured extractor, not authority
- **Simple schemas** - Extensible vocabulary, clear provenance
- **Generic/standalone** - Works with any AI agent system
- **Observability first** - Structured logging, health checks, error recovery

## License

MIT

## Contributing

This is a proof-of-concept. For production use, consider:
- Adding authentication/authorization
- Implementing rate limiting
- Adding comprehensive tests
- Improving error recovery
- Optimizing performance
- Adding monitoring/alerting

## Contact

For questions or feedback, please open an issue.
