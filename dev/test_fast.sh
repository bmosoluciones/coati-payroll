#!/bin/bash
# Fast test execution script for quick feedback during development
# Runs tests in parallel and excludes validation tests

unset DATABASE_URL
export LOG_LEVEL=trace
export DEVELOPMENT=True

set -e

# Color output for better visibility
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}Running fast tests (excluding validation)...${NC}"
echo -e "${BLUE}Using parallel execution for speed${NC}\n"

# Run tests with:
# - Parallel execution (-n auto)
# - Exclude validation tests (default from pytest.ini)
# - No coverage for speed
# - Fail fast on first error (-x) for quick feedback
# - Show only test names, not full output (-q)
pytest -n auto -x -q "$@"

EXIT_CODE=$?

if [[ $EXIT_CODE -eq 0 ]]; then
    echo -e "\n${GREEN}✓ Fast tests passed!${NC}"
else
    echo -e "\n${RED}✗ Fast tests failed${NC}"
fi

exit $EXIT_CODE
