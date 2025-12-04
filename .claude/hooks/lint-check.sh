#!/usr/bin/env bash
set -e

# Lint check hook (Stop hook)
# Runs ruff on Python files that were edited during the session
# Does NOT block - just surfaces linting issues

# Read input from stdin
input=$(cat)
session_id=$(echo "$input" | jq -r '.session_id // empty')

# Skip if no session ID
if [[ -z "$session_id" ]]; then
    exit 0
fi

# Check cache directory
cache_dir="$CLAUDE_PROJECT_DIR/.claude/cache/${session_id}"
if [[ ! -d "$cache_dir" ]] || [[ ! -f "$cache_dir/edited-files.log" ]]; then
    exit 0
fi

# Extract Python files that were edited
python_files=$(awk -F':' '{print $2}' "$cache_dir/edited-files.log" | grep '\.py$' | sort -u)

# Skip if no Python files
if [[ -z "$python_files" ]]; then
    exit 0
fi

# Count files
file_count=$(echo "$python_files" | wc -l | tr -d ' ')

# Run ruff check with --fix
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔍 LINT CHECK"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Checking $file_count Python file(s)..."
echo ""

# Create temp file list
temp_file_list=$(mktemp)
echo "$python_files" > "$temp_file_list"

# Run ruff with fix
cd "$CLAUDE_PROJECT_DIR"
if ./venv/bin/python -m ruff check "$(cat "$temp_file_list")" --fix 2>&1; then
    echo ""
    echo "✅ All files passed linting checks"
else
    echo ""
    echo "⚠️  Some linting issues remain"
    echo "TIP: Review issues above and address before committing"
fi

rm -f "$temp_file_list"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Exit cleanly (doesn't block)
exit 0
