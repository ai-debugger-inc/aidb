#!/bin/bash

# Test AI-powered intent analysis

set -e

cd "$(dirname "$0")"

# Set CLAUDE_PROJECT_DIR to the repo root
CLAUDE_PROJECT_DIR="$(cd ../.. && pwd)"
export CLAUDE_PROJECT_DIR

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Testing AI-powered intent analysis"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check API key
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "⚠️  ANTHROPIC_API_KEY not set"
    echo "    Loading from .env file if it exists..."
    if [ -f .env ]; then
        export "$(grep -v '^#' < .env | xargs)"
    fi

    if [ -z "$ANTHROPIC_API_KEY" ]; then
        echo "❌ ERROR: ANTHROPIC_API_KEY still not set"
        echo "   Please create .env file with your API key"
        exit 1
    fi
    echo "✅ API key loaded from .env"
fi
echo ""

# Test 1: Meta-work on skills (should NOT trigger adapter-development)
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Test 1: Fix skill file references"
echo "Expected: Only skill-developer (meta-skill)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo '{"session_id":"test1","transcript_path":"","cwd":"","permission_mode":"","prompt":"Fix skill file references"}' | \
    npx tsx skill-activation-prompt.ts
echo ""

# Test 2: Adapter work (should trigger adapter-development)
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Test 2: Fix Java adapter cleanup"
echo "Expected: adapter-development (high confidence)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo '{"session_id":"test2","transcript_path":"","cwd":"","permission_mode":"","prompt":"Fix the Java adapter cleanup issue"}' | \
    npx tsx skill-activation-prompt.ts
echo ""

# Test 3: Testing work (should trigger testing-strategy)
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Test 3: Add E2E tests"
echo "Expected: testing-strategy (high confidence)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo '{"session_id":"test3","transcript_path":"","cwd":"","permission_mode":"","prompt":"Add E2E tests for Express framework"}' | \
    npx tsx skill-activation-prompt.ts
echo ""

# Test 4: Generic question (should not trigger domain skills)
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Test 4: Project status"
echo "Expected: Only skill-developer (meta-skill)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo '{"session_id":"test4","transcript_path":"","cwd":"","permission_mode":"","prompt":"What is the status of the project?"}' | \
    npx tsx skill-activation-prompt.ts
echo ""

# Test 5: Precommit issues in skills (the original false positive case)
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Test 5: Fix precommit issues in skills system"
echo "Expected: Only skill-developer (no false positives)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo '{"session_id":"test5","transcript_path":"","cwd":"","permission_mode":"","prompt":"Fix precommit issues in skills system"}' | \
    npx tsx skill-activation-prompt.ts
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ All tests completed!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Check the output above to verify:"
echo "  • Test 1: Only skill-developer"
echo "  • Test 2: adapter-development in CRITICAL"
echo "  • Test 3: testing-strategy in CRITICAL"
echo "  • Test 4: Only skill-developer"
echo "  • Test 5: Only skill-developer (no adapter/dap/ci-cd false positives)"
