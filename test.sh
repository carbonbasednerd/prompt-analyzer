#!/bin/bash
# Simple test script for Prompt Analyzer

set -e

BASE_URL=${1:-"http://localhost:8001"}
SESSION_ID="test_$(date +%s)"

echo "Testing Prompt Analyzer..."
echo "Session ID: $SESSION_ID"
echo ""

# Test 1: Health checks
echo "=== Test 1: Health Checks ==="
echo "Ledger health:"
curl -s http://localhost:8001/health | jq
echo ""

echo "Extractor health:"
curl -s http://localhost:8002/health | jq
echo ""

echo "Monitor health:"
curl -s http://localhost:8003/health | jq
echo ""

# Test 2: Add first event
echo "=== Test 2: Add Events ==="
echo "Adding event 1: Never modify production files"
curl -s -X POST http://localhost:8001/ledger/append \
  -H "Content-Type: application/json" \
  -d "{
    \"session_id\": \"$SESSION_ID\",
    \"source\": \"user\",
    \"scope\": \"global\",
    \"text\": \"Never modify production files\"
  }" | jq
echo ""

echo "Adding event 2: Update the production config"
curl -s -X POST http://localhost:8001/ledger/append \
  -H "Content-Type: application/json" \
  -d "{
    \"session_id\": \"$SESSION_ID\",
    \"source\": \"user\",
    \"scope\": \"task\",
    \"text\": \"Update the production config file with new settings\"
  }" | jq
echo ""

# Test 3: Retrieve events
echo "=== Test 3: Retrieve Events ==="
echo "Events for session $SESSION_ID:"
curl -s "http://localhost:8001/ledger/session/$SESSION_ID" | jq
echo ""

# Wait for processing
echo "=== Waiting 10 seconds for processing ==="
sleep 10

# Test 4: View claims
echo "=== Test 4: View Claims ==="
echo "Claims for session $SESSION_ID:"
curl -s "http://localhost:8003/monitor/claims/$SESSION_ID" | jq
echo ""

# Test 5: View conflicts
echo "=== Test 5: View Conflicts ==="
echo "Conflicts for session $SESSION_ID:"
curl -s "http://localhost:8003/monitor/conflicts/$SESSION_ID" | jq
echo ""

# Test 6: Monitor status
echo "=== Test 6: Monitor Status ==="
curl -s http://localhost:8003/monitor/status | jq
echo ""

echo "=== Tests Complete ==="
echo "Session ID: $SESSION_ID"
