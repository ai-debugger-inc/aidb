#!/usr/bin/env bash

# Deactivate any active virtual environment
if [[ -n "${VIRTUAL_ENV:-}" ]]; then
    echo "Deactivating currently active virtual environment: ${VIRTUAL_ENV}"
    if declare -f deactivate >/dev/null 2>&1; then
        deactivate || true
    else
        echo "(Skipping deactivate — not defined in this shell)"
    fi
    unset VIRTUAL_ENV
fi

set -eu

if command -v realpath >/dev/null 2>&1; then
    SCRIPT_PATH="$(realpath "${0}")"
else
    SCRIPT_PATH="$(python -c "import os; print(os.path.realpath('${0}'))")"
fi

REPO_ROOT=$(dirname "$(dirname "$(dirname "$(dirname "${SCRIPT_PATH}")")")")

VERBOSE=0
FORCE=0

show_help() {
    echo "Usage: ./install/src/install.sh [options]"
    echo ""
    echo "Options:"
    echo "  -v            Enable verbose output"
    echo "  -h, --help    Show this help message"
    exit 0
}

for arg in "${@}"; do
    case "${arg}" in
        --force)
            FORCE=1
            ;;
        -h|--help)
            show_help
            ;;
        -v)
            VERBOSE=1
            ;;
    esac
done

find_python() {
    # Dynamically find all python3.1* binaries in PATH (deduped)
    mapfile -t dynamic_candidates < <(command -v -a python3.1* 2>/dev/null | awk '!seen[$0]++')

    # Find all python3.1* in common Homebrew and local bin dirs, even if not in PATH
    mapfile -t homebrew_candidates < <(ls /opt/homebrew/bin/python3.1* 2>/dev/null || true)
    mapfile -t usr_local_candidates < <(ls /usr/local/bin/python3.1* 2>/dev/null || true)

    # Add generic candidates for robustness
    static_candidates=(
        python3
        python
    )

    candidates=(
        "${dynamic_candidates[@]}"
        "${homebrew_candidates[@]}"
        "${usr_local_candidates[@]}"
        "${static_candidates[@]}"
    )

    best_py=""
    best_major=0
    best_minor=0
    for py in "${candidates[@]}"; do
        echo "Checking candidate: ${py}"
        if ! [[ -x "${py}" ]] && ! command -v "${py}" >/dev/null 2>&1; then
            continue
        fi
        version="$(
            "${py}" -c \
            'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")' \
            2>/dev/null || echo "0.0"
        )"
        echo "Detected Python version: ${version} (${py})"
        major="$(echo "${version}" | cut -d. -f1)"
        minor="$(echo "${version}" | cut -d. -f2)"
        if ! [[ "${major}" =~ ^[0-9]+$ ]] || ! [[ "${minor}" =~ ^[0-9]+$ ]]; then
            continue
        fi
        if [[ "${major}" -lt 3 ]] || { [[ "${major}" -eq 3 ]] && [[ "${minor}" -lt 10 ]]; }; then
            continue
        fi
        if [[ "${major}" -gt "${best_major}" ]] || \
           { [[ "${major}" -eq "${best_major}" ]] && \
             [[ "${minor}" -gt "${best_minor}" ]]; }; then
            best_py="${py}"
            best_major="${major}"
            best_minor="${minor}"
        fi
    done
    if [[ -n "${best_py}" ]]; then
        PYTHON="${best_py}"
        echo "Using Python interpreter: ${PYTHON} (${best_major}.${best_minor})"
        return
    fi
    echo "Error: Python 3.10+ is required but not found." >&2
    exit 1
}

check_wsl() {
    if [[ "$(uname -s)" = "Linux" ]] && grep -qEi "(Microsoft|WSL)" /proc/version 2>/dev/null; then
        echo "WSL detected."
    fi
}

check_pip() {
    if ! "${PYTHON}" -m pip --version >/dev/null 2>&1; then
        echo "Error: Pip is not available for ${PYTHON}. Please install pip."
        exit 1
    fi
}

check_docker() {
    # Required for docs build/testing
    if ! command -v docker >/dev/null 2>&1; then
        echo "Error: Docker is required but not installed or not in your PATH."
        exit 1
    fi
}

handle_venv() {
    local venv_dir="${REPO_ROOT}/venv"
    if [[ ! -d "${venv_dir}" ]]; then
        echo "Creating virtual environment in ${REPO_ROOT}/venv..."
        "${PYTHON}" -m venv "${venv_dir}"
    else
        echo "Using existing virtual environment in ${REPO_ROOT}/venv"
    fi

    # shellcheck source=/dev/null
    . "${venv_dir}/bin/activate"
    echo "Switching to venv python..."
    PYTHON="$(command -v python)"
}

pip_install() {
    echo "Installing editable ai-debugger-inc with [dev,docs,test] extras from source..."
    if [[ "${FORCE}" -eq 1 ]]; then
        echo "Forcing reinstall of ai-debugger-inc..."
        "${PYTHON}" -m pip uninstall -y ai-debugger-inc || true
    fi
    "${PYTHON}" -m pip install --disable-pip-version-check --upgrade pip setuptools wheel || {
        echo "Error: Failed to upgrade pip, setuptools, or wheel"
        exit 1
    }
    "${PYTHON}" -m pip install -e "${REPO_ROOT}/.[dev,docs,test]" --use-pep517 || {
        echo "Error: Failed to install AI Debugger main module with [dev,docs,test] extras"
        exit 1
    }
}

setup_dev_cli() {
    local dev_cli="${REPO_ROOT}/dev-cli"
    local venv_bin="${REPO_ROOT}/venv/bin"

    if [[ -f "${dev_cli}" ]] && [[ -d "${venv_bin}" ]]; then
        echo "Setting up dev-cli symlink..."
        ln -sf "${dev_cli}" "${venv_bin}/dev-cli"
        echo "✓ dev-cli is now available from anywhere when venv is active"
    else
        echo "Warning: dev-cli script not found at ${dev_cli}"
    fi
}

perform_install() {
    if [[ "${VERBOSE}" -eq 1 ]]; then
        set -x
    fi
    find_python
    check_wsl
    check_pip
    check_docker
    handle_venv
    pip_install
    setup_dev_cli
}

perform_install "${@}"

set +x
echo -e "\nInstallation complete!"
echo "Virtual environment activated. You can now use:"
echo "  • dev-cli (from anywhere when venv is active)"
echo "  • Python: import aidb"
echo ""
echo "Example Python usage:"
echo -e "\033[1;35m"
echo 'import asyncio
from aidb.api.api import DebugAPI
from aidb.models.entities.breakpoint import BreakpointSpec

async def debug_example():
    api = DebugAPI()
    session = await api.create_session(
        language="python",
        target="./main.py",
        breakpoints=[
            BreakpointSpec(file="foo.py", line=42, condition="x > 5")
        ]
    )
    await session.start()
    # Use api.orchestration and api.introspection for debugging
    await session.stop()

# Run the debug session
asyncio.run(debug_example())'
echo -e "\033[0m"
