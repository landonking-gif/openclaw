#!/bin/bash
# OpenClaw Army Test Runner - Shell version (one test at a time)
# Usage: ./run_batch.sh <start> <end>
# Results go to results.jsonl

set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
PROMPTS="$DIR/prompts.json"
RESULTS="$DIR/results.jsonl"
BASE="http://127.0.0.1:18830"

start=${1:-1}
end=${2:-5}

echo "========================================"
echo "  Running tests $start - $end"
echo "========================================"

# Extract prompts using python
python3 -c "
import json, sys
with open('$PROMPTS') as f:
    prompts = json.load(f)
for p in prompts:
    if $start <= p['id'] <= $end:
        print(json.dumps(p))
" | while IFS= read -r test_json; do
    test_id=$(echo "$test_json" | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")
    test_cat=$(echo "$test_json" | python3 -c "import json,sys; print(json.load(sys.stdin)['cat'])")
    test_prompt=$(echo "$test_json" | python3 -c "import json,sys; print(json.load(sys.stdin)['prompt'])")
    test_expect=$(echo "$test_json" | python3 -c "import json,sys; print(json.load(sys.stdin)['expect'])")

    echo ""
    echo "[$test_id/$end] $test_cat"
    echo "  Prompt: ${test_prompt:0:80}"
    
    # Send to orchestrator
    ts_before=$(date -u +%Y-%m-%dT%H:%M:%S)
    t_start=$(python3 -c "import time; print(time.time())")
    
    response=$(curl -s --max-time 180 -X POST "$BASE/chat" \
        -H "Content-Type: application/json" \
        -d "$(python3 -c "import json; print(json.dumps({'message': $(echo "$test_json" | python3 -c "import json,sys; print(json.dumps(json.load(sys.stdin)['prompt']))")}))")" \
        2>&1) || response='{"error":"curl_failed"}'
    
    t_end=$(python3 -c "import time; print(time.time())")
    elapsed=$(python3 -c "print(round($t_end - $t_start, 2))")
    
    # Get activity for this period
    sleep 1
    activity=$(curl -s --max-time 10 "$BASE/activity?limit=10" 2>/dev/null) || activity='[]'
    
    # Parse response
    resp_text=$(echo "$response" | python3 -c "import json,sys; r=json.load(sys.stdin); print(r.get('response','ERROR: '+str(r.get('error','')))[:200])" 2>/dev/null) || resp_text="PARSE_ERROR"
    n_delegations=$(echo "$response" | python3 -c "import json,sys; print(len(json.load(sys.stdin).get('delegations',[])))" 2>/dev/null) || n_delegations="?"
    
    if [ "$n_delegations" != "0" ] && [ "$n_delegations" != "?" ]; then
        status="DELEGATED($n_delegations)"
    elif echo "$response" | python3 -c "import json,sys; r=json.load(sys.stdin); sys.exit(0 if 'error' in r else 1)" 2>/dev/null; then
        status="ERROR"
    else
        status="DIRECT"
    fi
    
    echo "  [$status] ${elapsed}s"
    echo "  Response: ${resp_text:0:150}"
    
    # Write result
    python3 -c "
import json, sys
result = {
    'id': $test_id,
    'cat': '$test_cat',
    'prompt': $(echo "$test_json" | python3 -c "import json,sys; print(json.dumps(json.load(sys.stdin)['prompt']))"),
    'expect': '$test_expect',
    'response': json.loads('''$response''' if '''$response'''.strip() else '{\"error\":\"empty\"}'),
    'elapsed_sec': $elapsed,
    'status': '$status',
}
with open('$RESULTS', 'a') as f:
    f.write(json.dumps(result) + '\n')
" 2>/dev/null || echo "  [WARN] Failed to write result"
    
    # Rate limit pause
    sleep 3
done

echo ""
echo "========================================"
echo "  Done! Results in $RESULTS"
echo "========================================"
