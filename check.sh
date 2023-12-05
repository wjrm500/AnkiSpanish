#!/bin/bash

# Define path to your virtual environment's activate script
VENV_PATH="./venv-dev/bin/activate"

# Check if the virtual environment exists and activate it
if [ -f "$VENV_PATH" ]; then
    source "$VENV_PATH"
else
    echo "Virtual environment not found at $VENV_PATH"
    exit 1
fi

# Define ANSI color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
RESET='\033[0m'

# Function to run a command and print success or failure
run_check() {
    printf "%-20s" "Running $1..."
    if $2 &> /dev/null; then
        echo -e "${GREEN}SUCCESS${RESET}"
    else
        echo -e "${RED}FAILURE${RESET}"
    fi
}

# Run isort in check mode
run_check "isort" "isort . --check-only --skip ./venv --skip ./venv-dev"

# Run black in check mode
run_check "black" "black . --check"

# Run flake8 with exclusion for ./venv
run_check "flake8" "flake8 . --exclude=./venv,./venv-dev"

# Run mypy in strict mode
run_check "mypy" "mypy . --strict"

