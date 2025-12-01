#!/bin/bash
set -e

# Post-tool-use hook that tracks edited files for AIDB project
# This runs after Edit, MultiEdit, or Write tools complete successfully

# Read tool information from stdin
tool_info=$(cat)

# Extract relevant data
tool_name=$(echo "$tool_info" | jq -r '.tool_name // empty')
file_path=$(echo "$tool_info" | jq -r '.tool_input.file_path // empty')
session_id=$(echo "$tool_info" | jq -r '.session_id // empty')

# Skip if not an edit tool or no file path
if [[ ! "$tool_name" =~ ^(Edit|MultiEdit|Write)$ ]] || [[ -z "$file_path" ]]; then
    exit 0
fi

# Skip markdown files
if [[ "$file_path" =~ \.(md|markdown)$ ]]; then
    exit 0
fi

# Create cache directory in project
cache_dir="$CLAUDE_PROJECT_DIR/.claude/cache/${session_id:-default}"
mkdir -p "$cache_dir"

# Function to detect AIDB domain from file path
detect_aidb_domain() {
    local file="$1"
    local project_root="$CLAUDE_PROJECT_DIR"

    # Remove project root from path
    local relative_path="${file#"$project_root"/}"

    # AIDB domain detection based on directory structure
    case "$relative_path" in
        # Adapter files
        src/aidb/adapters/*)
            echo "adapters"
            ;;
        # DAP protocol/client
        src/aidb/dap/*)
            echo "dap"
            ;;
        # MCP server and tools
        src/aidb_mcp/*)
            echo "mcp"
            ;;
        # Core session management
        src/aidb/session/*)
            echo "session"
            ;;
        # Core API
        src/aidb/api/*)
            echo "api"
            ;;
        # Testing
        src/tests/*)
            echo "tests"
            ;;
        # CLI
        src/aidb_cli/*)
            echo "cli"
            ;;
        # Common utilities
        src/aidb_common/*)
            echo "common"
            ;;
        # Logging
        src/aidb_logging/*)
            echo "logging"
            ;;
        *)
            echo "other"
            ;;
    esac
}

# Detect domain
domain=$(detect_aidb_domain "$file_path")

# Skip if not in a recognized AIDB domain
if [[ "$domain" == "other" ]]; then
    exit 0
fi

# Log edited file
echo "$(date +%s):$file_path:$domain" >> "$cache_dir/edited-files.log"

# Update affected domains list
if ! grep -q "^$domain$" "$cache_dir/affected-domains.txt" 2>/dev/null; then
    echo "$domain" >> "$cache_dir/affected-domains.txt"
fi

# Store relevant test commands based on domain
case "$domain" in
    adapters)
        echo "adapters:test:./dev-cli test run -m unit -p 'test_adapter' --local" >> "$cache_dir/test-commands.txt.tmp"
        echo "adapters:test:./dev-cli test run -m unit -p 'test_launch' --local" >> "$cache_dir/test-commands.txt.tmp"
        ;;
    dap)
        echo "dap:test:./dev-cli test run -m unit -p 'test_dap' --local" >> "$cache_dir/test-commands.txt.tmp"
        ;;
    mcp)
        echo "mcp:test:./dev-cli test run -m unit -p 'test_mcp' --local" >> "$cache_dir/test-commands.txt.tmp"
        echo "mcp:test:./dev-cli test run -m e2e -p 'test_mcp_e2e' --local" >> "$cache_dir/test-commands.txt.tmp"
        ;;
    session)
        echo "session:test:./dev-cli test run -m unit -p 'test_session' --local" >> "$cache_dir/test-commands.txt.tmp"
        ;;
    tests)
        # If editing test files, suggest running that specific test
        if [[ "$file_path" =~ test_([^/]+)\.py$ ]]; then
            test_name="${BASH_REMATCH[1]}"
            echo "tests:test:./dev-cli test run -p '$test_name' --local" >> "$cache_dir/test-commands.txt.tmp"
        fi
        ;;
esac

# Remove duplicates from test commands
if [[ -f "$cache_dir/test-commands.txt.tmp" ]]; then
    sort -u "$cache_dir/test-commands.txt.tmp" > "$cache_dir/test-commands.txt"
    rm -f "$cache_dir/test-commands.txt.tmp"
fi

# Exit cleanly
exit 0
