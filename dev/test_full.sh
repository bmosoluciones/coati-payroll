#!/bin/bash
# Full test execution script for comprehensive testing
# Runs all tests including validation tests with coverage

unset DATABASE_URL
export LOG_LEVEL=trace
export DEVELOPMENT=True

set -e

# Color output for better visibility
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}Running full test suite...${NC}"
echo -e "${BLUE}This includes regular tests, validation tests, and coverage${NC}\n"

# Run regular tests with coverage
echo -e "${YELLOW}Step 1/2: Running regular tests with coverage...${NC}"
pytest -n auto \
    --cov=coati_payroll \
    --cov-report=xml \
    --cov-report=term-missing \
    -v \
    "$@"

REGULAR_EXIT_CODE=$?

# Run validation tests with coverage append
echo -e "\n${YELLOW}Step 2/2: Running validation tests...${NC}"
pytest -n auto \
    -m validation \
    --cov=coati_payroll \
    --cov-append \
    --cov-report=xml \
    --cov-report=term-missing \
    -v \
    "$@"

VALIDATION_EXIT_CODE=$?

# Report results
echo ""
if [[ $REGULAR_EXIT_CODE -eq 0 && $VALIDATION_EXIT_CODE -eq 0 ]]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
    echo -e "${GREEN}Coverage report generated: coverage.xml${NC}"
    EXIT_CODE=0
else
    if [[ $REGULAR_EXIT_CODE -ne 0 ]]; then
        echo -e "${RED}✗ Regular tests failed${NC}"
    fi
    if [[ $VALIDATION_EXIT_CODE -ne 0 ]]; then
        echo -e "${RED}✗ Validation tests failed${NC}"
    fi
    EXIT_CODE=1
fi

exit $EXIT_CODE
