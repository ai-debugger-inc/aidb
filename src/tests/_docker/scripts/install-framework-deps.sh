#!/usr/bin/env bash
set -e

FRAMEWORK_ROOT="${FRAMEWORK_ROOT:-/workspace/src/tests/_assets/framework_apps}"
LANGUAGE_FILTER="${1:-all}"
CACHE_DIR="${FRAMEWORK_ROOT}/.cache"

# Skip check entirely if requested
if [[ "${SKIP_FRAMEWORK_DEPS_CHECK:-false}" == "true" ]]; then
    echo "→ Skipping framework dependency check (SKIP_FRAMEWORK_DEPS_CHECK=true)"
    exit 0
fi

echo ""
echo "=== Framework Dependencies Check (Hash-Based) ==="
echo "Filter: ${LANGUAGE_FILTER}"
echo "Root: ${FRAMEWORK_ROOT}"
echo ""

# Ensure cache directory exists
mkdir -p "${CACHE_DIR}"

# Check if app dependencies need installation using Python checksum service
# Args: language, app_name
# Returns: 0 if needs install, 1 if up-to-date
check_needs_install() {
    local language="${1}"
    local app_name="${2}"

    # Call Python service to check hash
    python3 <<EOF
import sys
from pathlib import Path
sys.path.insert(0, "/workspace/src")

from aidb_cli.services.docker.framework_deps_checksum_service import FrameworkDepsChecksumService

service = FrameworkDepsChecksumService(Path("${FRAMEWORK_ROOT}"))
needs_install, reason = service.needs_install("${language}", "${app_name}")
sys.exit(0 if needs_install else 1)
EOF
}

# Mark app dependencies as installed using Python checksum service
# Args: language, app_name
mark_installed() {
    local language="${1}"
    local app_name="${2}"

    python3 <<EOF
import sys
from pathlib import Path
sys.path.insert(0, "/workspace/src")

from aidb_cli.services.docker.framework_deps_checksum_service import FrameworkDepsChecksumService

service = FrameworkDepsChecksumService(Path("${FRAMEWORK_ROOT}"))
service.mark_installed("${language}", "${app_name}")
EOF
}

# Run install command and report success/failure
# Args: app_name, install_command, installed_count_ref
run_install() {
    local app_name="${1}"
    local install_cmd="${2}"

    echo "  → Installing ${app_name}..."
    if eval "${install_cmd}" 2>/dev/null; then
        echo "    ✓ Installed successfully"
        return 0
    else
        echo "    ✗ Installation failed"
        return 1
    fi
}

# Install dependencies for a specific language
# Args: language, install_function
install_language_deps() {
    local language="${1}"
    local language_dir="${FRAMEWORK_ROOT}/${language}"

    echo "--- ${language} ---"

    if [ ! -d "${language_dir}" ]; then
        echo "  ⊘ No ${language} framework directory found"
    else
        local app_count=0
        local installed_count=0
        local cached_count=0

        # Call language-specific installation logic
        "${2}" "${language_dir}" app_count installed_count cached_count

        if [ "${app_count}" -eq 0 ]; then
            echo "  ⊘ No ${language} framework apps found"
        else
            echo "  Summary: ${app_count} app(s) checked, ${installed_count} installed, ${cached_count} cached"
        fi
    fi
    echo ""
}

# JavaScript/Node.js installation logic
install_javascript_deps() {
    local language_dir="${1}"
    local -n app_count_ref="${2}"
    local -n installed_count_ref="${3}"
    local -n cached_count_ref="${4}"

    for dir in "${language_dir}/"*/; do
        [ ! -f "${dir}/package.json" ] && continue

        app_count_ref=$((app_count_ref + 1))
        local app_name
        app_name="$(basename "${dir}")"

        # Check hash to determine if installation is needed
            if check_needs_install "javascript" "${app_name}"; then
            if run_install "${app_name}" "npm install --prefix '${dir}' --no-save --silent"; then
                installed_count_ref=$((installed_count_ref + 1))
                mark_installed "javascript" "${app_name}"
            fi
        else
            echo "  ✓ ${app_name} (up-to-date)"
            cached_count_ref=$((cached_count_ref + 1))
        fi
    done
}

# JavaScript/Node.js frameworks
if [[ "${LANGUAGE_FILTER}" == "all" || "${LANGUAGE_FILTER}" == "javascript" ]]; then
    install_language_deps "javascript" install_javascript_deps
fi

# Python installation logic
install_python_deps() {
    local language_dir="${1}"
    local -n app_count_ref="${2}"
    local -n installed_count_ref="${3}"
    local -n cached_count_ref="${4}"

    for dir in "${language_dir}/"*/; do
        [ ! -f "${dir}/requirements.txt" ] && continue

        app_count_ref=$((app_count_ref + 1))
        local app_name
        app_name="$(basename "${dir}")"

        # Check hash to determine if installation is needed
            if check_needs_install "python" "${app_name}"; then
            if run_install "${app_name}" "pip install --root-user-action=ignore -q -r '${dir}/requirements.txt'"; then
                installed_count_ref=$((installed_count_ref + 1))
                mark_installed "python" "${app_name}"
            fi
        else
            echo "  ✓ ${app_name} (up-to-date)"
            cached_count_ref=$((cached_count_ref + 1))
        fi
    done
}

# Python frameworks
if [[ "${LANGUAGE_FILTER}" == "all" || "${LANGUAGE_FILTER}" == "python" ]]; then
    install_language_deps "python" install_python_deps
fi

# Java installation logic
install_java_deps() {
    local language_dir="${1}"
    local -n app_count_ref="${2}"
    local -n installed_count_ref="${3}"
    local -n cached_count_ref="${4}"

    for dir in "${language_dir}/"*/; do
        local app_name
        app_name="$(basename "${dir}")"

        # Maven
        if [ -f "${dir}/pom.xml" ]; then
            app_count_ref=$((app_count_ref + 1))

            # Check hash to determine if installation is needed
            if check_needs_install "java" "${app_name}"; then
                # Download dependencies AND compile source for JDT LS
                if run_install "${app_name} (Maven)" "cd '${dir}' && mvn dependency:resolve -q && mvn compile -q"; then
                    installed_count_ref=$((installed_count_ref + 1))
                    mark_installed "java" "${app_name}"
                fi
            else
                echo "  ✓ ${app_name} (Maven, up-to-date)"
                cached_count_ref=$((cached_count_ref + 1))
            fi
        fi

        # Gradle
        if [ -f "${dir}/build.gradle" ] || [ -f "${dir}/build.gradle.kts" ]; then
            app_count_ref=$((app_count_ref + 1))

            # Check hash to determine if installation is needed
            if check_needs_install "java" "${app_name}"; then
                # Download dependencies AND compile source for JDT LS
                if run_install "${app_name} (Gradle)" "cd '${dir}' && gradle dependencies --quiet && gradle compileJava --quiet"; then
                    installed_count_ref=$((installed_count_ref + 1))
                    mark_installed "java" "${app_name}"
                fi
            else
                echo "  ✓ ${app_name} (Gradle, up-to-date)"
                cached_count_ref=$((cached_count_ref + 1))
            fi
        fi
    done
}

# Java frameworks
if [[ "${LANGUAGE_FILTER}" == "all" || "${LANGUAGE_FILTER}" == "java" ]]; then
    install_language_deps "java" install_java_deps
fi

echo "=== Framework dependencies ready ==="
echo ""
