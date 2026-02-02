# Prompt Analyzer - Quick Start Guide

## 5-Minute Setup

### 1. Start Services (2-5 minutes first time)
```bash
cd /home/jay/git/jay-i/prompt-analyzer
docker-compose up -d
```

Wait for Ollama to download llama3.1:8b (~4GB, first time only):
```bash
docker-compose logs -f ollama
# Wait until you see: "pulled llama3.1:8b"
# Press Ctrl+C to exit logs
```

### 2. Check Health (10 seconds)
```bash
curl http://localhost:8001/health  # Ledger (should return "healthy")
curl http://localhost:8002/health  # Extractor (should return "healthy")
curl http://localhost:8003/health  # Monitor (should return "healthy")
```

### 3. Run Test (30 seconds)
```bash
./test.sh
```

## Common Commands

### Add Instruction Event
```bash
curl -X POST http://localhost:8001/ledger/append \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "my_session",
    "source": "user",
    "scope": "global",
    "text": "Your instruction text here"
  }'
```

### View Events
```bash
curl http://localhost:8001/ledger/session/my_session | jq
```

### View Claims (wait 10s after adding events)
```bash
curl http://localhost:8003/monitor/claims/my_session | jq
```

### View Conflicts
```bash
curl http://localhost:8003/monitor/conflicts/my_session | jq
```

### View Logs
```bash
docker-compose logs -f          # All services
docker-compose logs -f monitor  # Just monitor
docker-compose logs --tail=100 extractor  # Last 100 lines
```

### Stop/Restart
```bash
docker-compose down             # Stop all services
docker-compose up -d            # Start all services
docker-compose restart monitor  # Restart one service
```

## API Documentation

Interactive docs available at:
- Ledger: http://localhost:8001/docs
- Extractor: http://localhost:8002/docs
- Monitor: http://localhost:8003/docs

## Ports

- 8001 - Ledger Service
- 8002 - Extractor Service
- 8003 - Monitor Service
- 11434 - Ollama (LLM)

## Example: Find Contradictions

```bash
SESSION="test_$(date +%s)"

# Add first instruction
curl -X POST http://localhost:8001/ledger/append \
  -H "Content-Type: application/json" \
  -d "{
    \"session_id\": \"$SESSION\",
    \"source\": \"user\",
    \"scope\": \"global\",
    \"text\": \"Never modify production files\"
  }"

# Add contradictory instruction
curl -X POST http://localhost:8001/ledger/append \
  -H "Content-Type: application/json" \
  -d "{
    \"session_id\": \"$SESSION\",
    \"source\": \"user\",
    \"scope\": \"task\",
    \"text\": \"Update the production config file\"
  }"

# Wait for processing
sleep 10

# Check conflicts
curl "http://localhost:8003/monitor/conflicts/$SESSION" | jq
```

Expected output:
```json
[
  {
    "conflict_id": "cfl_...",
    "session_id": "test_...",
    "claims": ["clm_...", "clm_..."],
    "severity": "hard",
    "explanation": "Contradictory instructions: must_not file_write vs must file_write on 'production files'",
    "confidence": 0.92
  }
]
```

## Troubleshooting

**Services won't start:**
```bash
docker-compose logs [service_name]  # Check logs
docker-compose down && docker-compose up -d  # Restart
```

**Ollama download stuck:**
```bash
docker-compose restart ollama
docker-compose exec ollama ollama pull llama3.1:8b  # Manual pull
```

**No conflicts detected:**
- Wait 10-15 seconds after adding events
- Check claims exist: `curl http://localhost:8003/monitor/claims/[session_id]`
- Check logs: `docker-compose logs monitor`

**Port already in use:**
```bash
# Change ports in docker-compose.yml
# e.g., "8001:8000" -> "9001:8000"
```

## Next Steps

1. Read full documentation: `README.md`
2. Review architecture: `ARCHITECTURE.md`
3. Check implementation details: `IMPLEMENTATION.md`
4. Explore API docs at http://localhost:8001/docs

## One-Liner Demo

```bash
cd /home/jay/git/jay-i/prompt-analyzer && docker-compose up -d && sleep 60 && ./test.sh
```

This will:
1. Start all services
2. Wait 60 seconds for model download
3. Run full integration test
