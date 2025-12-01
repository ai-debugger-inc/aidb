#!/usr/bin/env bash
# Cleanup stale skill enforcement state files
# Run this periodically to prevent accumulation of orphaned state files

set -euo pipefail

# Get project directory
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$HOME/project}"
STATE_DIR="$PROJECT_DIR/.claude/hooks/state"

# Exit if state directory doesn't exist
if [ ! -d "$STATE_DIR" ]; then
    echo "No state directory found at: $STATE_DIR"
    exit 0
fi

# Delete files older than 7 days
echo "Cleaning up stale state files (>7 days old) in: $STATE_DIR"
find "$STATE_DIR" -name "*-skills-suggested.json" -type f -mtime +7 -delete

# Count remaining files
REMAINING=$(find "$STATE_DIR" -name "*-skills-suggested.json" -type f | wc -l | tr -d ' ')
echo "Cleanup complete. Remaining state files: $REMAINING"
