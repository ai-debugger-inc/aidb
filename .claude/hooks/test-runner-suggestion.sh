#!/usr/bin/env bash
set -e

# Test runner suggestion hook (Stop hook)
# Suggests running relevant tests based on edited files
# Does NOT block - just provides helpful suggestions

# Read input from stdin
input=$(cat)
session_id=$(echo "$input" | jq -r '.session_id // empty')

# Skip if no session ID
if [[ -z "$session_id" ]]; then
    exit 0
fi

# Check cache directory
cache_dir="$CLAUDE_PROJECT_DIR/.claude/cache/${session_id}"
if [[ ! -d "$cache_dir" ]]; then
    exit 0
fi

# Check if any domains were affected
if [[ ! -f "$cache_dir/affected-domains.txt" ]]; then
    exit 0
fi

# Check if test commands were generated
if [[ ! -f "$cache_dir/test-commands.txt" ]]; then
    exit 0
fi

# Read affected domains
affected_domains=$(sort -u < "$cache_dir/affected-domains.txt")
domain_count=$(echo "$affected_domains" | wc -l | tr -d ' ')

# Read test commands
test_commands=$(cut -d':' -f3- < "$cache_dir/test-commands.txt" | sort -u)
command_count=$(echo "$test_commands" | wc -l | tr -d ' ')

# Skip if no test commands
if [[ $command_count -eq 0 ]]; then
    exit 0
fi

# Generate output
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🧪 TEST RUNNER SUGGESTION"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📝 Edited $domain_count AIDB domain(s):"
while IFS= read -r domain; do
    echo "   • $domain"
done <<< "$affected_domains"
echo ""
echo "💡 Suggested test commands:"
while IFS= read -r cmd; do
    echo "   → $cmd"
done <<< "$test_commands"
echo ""
echo "TIP: Run tests to validate changes"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Exit cleanly (doesn't block)
exit 0
