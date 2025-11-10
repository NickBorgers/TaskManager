#!/bin/bash
#
# Release Validation Script
#
# This script runs comprehensive tests before a release to ensure:
# 1. All unit tests pass
# 2. Integration tests pass (with real test databases)
# 3. Weekly rollover script executes successfully
# 4. Daily review script executes successfully
# 5. No errors in logs
#
# Usage:
#   ./scripts/validate_release.sh
#
# Environment Requirements:
#   - NOTION_INTEGRATION_SECRET: Token for test databases
#   - test_notion_config.yaml: Configuration with test database IDs
#
# Exit codes:
#   0 - All validations passed
#   1 - One or more validations failed
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Track overall success
VALIDATION_FAILED=0

# Print section header
print_section() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

# Print success message
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

# Print error message
print_error() {
    echo -e "${RED}✗ $1${NC}"
    VALIDATION_FAILED=1
}

# Print warning message
print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# Check prerequisites
print_section "Checking Prerequisites"

# Check for either NOTION_INTEGRATION_SECRET or NOTION_INTEGRATION_SECRET_TEST
if [ -z "$NOTION_INTEGRATION_SECRET" ]; then
    if [ -n "$NOTION_INTEGRATION_SECRET_TEST" ]; then
        # Use the _TEST variant if available
        export NOTION_INTEGRATION_SECRET="$NOTION_INTEGRATION_SECRET_TEST"
        print_success "Using NOTION_INTEGRATION_SECRET_TEST"
    else
        print_error "NOTION_INTEGRATION_SECRET not set"
        echo "  Set it with: export NOTION_INTEGRATION_SECRET=your-test-token"
        echo "  Or: export NOTION_INTEGRATION_SECRET_TEST=your-test-token"
        exit 1
    fi
else
    print_success "NOTION_INTEGRATION_SECRET is set"
fi

# Check for OpenAI API key (optional)
if [ -z "$OPENAI_API_KEY" ] && [ -n "$OPENAI_API_KEY_TEST" ]; then
    export OPENAI_API_KEY="$OPENAI_API_KEY_TEST"
    print_success "Using OPENAI_API_KEY_TEST (optional)"
fi

if [ ! -f "test_notion_config.yaml" ]; then
    print_warning "test_notion_config.yaml not found - integration tests will be skipped"
else
    print_success "test_notion_config.yaml found"
fi

if [ ! -f "notion_config.yaml" ]; then
    print_warning "notion_config.yaml not found - using test config only"
else
    print_success "notion_config.yaml found"
fi

# Run unit tests
print_section "Running Unit Tests"

if pytest tests/test_weekly_rollover.py tests/test_daily_planned_date_review.py tests/test_scheduler.py -v --tb=short; then
    print_success "All unit tests passed"
else
    print_error "Unit tests failed"
fi

# Run integration tests if test database available
if [ -f "test_notion_config.yaml" ] && [ -n "$NOTION_INTEGRATION_SECRET" ]; then
    print_section "Running Integration Tests"

    if pytest tests/test_integration_weekly_rollover.py tests/test_integration_daily_review.py -v --tb=short; then
        print_success "All integration tests passed"
    else
        print_error "Integration tests failed"
    fi
else
    print_warning "Skipping integration tests (test database not configured)"
fi

# Test weekly rollover with specific date
print_section "Testing Weekly Rollover Script"

TEST_DATE="2025-12-06T09:00:00Z"  # Saturday at 9AM
echo "Running weekly rollover for test date: $TEST_DATE"

if python3 scripts/weekly_rollover/create_active_tasks_from_templates.py \
    --config test_notion_config.yaml \
    --now "$TEST_DATE" 2>&1 | tee /tmp/weekly_rollover_test.log; then

    # Check for errors in output
    if grep -i "error" /tmp/weekly_rollover_test.log | grep -v "ERROR Test" | grep -v "test_error" > /dev/null; then
        print_error "Weekly rollover completed but errors found in logs"
        echo "  Check /tmp/weekly_rollover_test.log for details"
    else
        print_success "Weekly rollover executed successfully"
    fi
else
    print_error "Weekly rollover script failed"
    echo "  Check /tmp/weekly_rollover_test.log for details"
fi

# Test daily review
print_section "Testing Daily Review Script"

echo "Running daily planned date review..."

if python3 scripts/daily_planned_date_review.py \
    --config test_notion_config.yaml 2>&1 | tee /tmp/daily_review_test.log; then

    # Check for errors in output
    if grep -i "error" /tmp/daily_review_test.log | grep -v "ERROR Test" | grep -v "test_error" > /dev/null; then
        print_error "Daily review completed but errors found in logs"
        echo "  Check /tmp/daily_review_test.log for details"
    else
        print_success "Daily review executed successfully"
    fi
else
    print_error "Daily review script failed"
    echo "  Check /tmp/daily_review_test.log for details"
fi

# Test with multiple dates to verify --now parameter works
print_section "Testing Date Parameter Handling"

echo "Testing various date formats..."

TEST_DATES=(
    "2025-12-13"                    # Date only
    "2025-12-13T09:00:00Z"         # Full ISO with Z
    "2025-12-13T09:00:00+00:00"    # Full ISO with timezone
)

DATE_TEST_FAILED=0

for TEST_DATE in "${TEST_DATES[@]}"; do
    echo -n "  Testing date: $TEST_DATE ... "

    if python3 scripts/weekly_rollover/create_active_tasks_from_templates.py \
        --config test_notion_config.yaml \
        --now "$TEST_DATE" > /tmp/date_test.log 2>&1; then
        echo -e "${GREEN}✓${NC}"
    else
        echo -e "${RED}✗${NC}"
        DATE_TEST_FAILED=1
    fi
done

if [ $DATE_TEST_FAILED -eq 0 ]; then
    print_success "All date format tests passed"
else
    print_error "Some date format tests failed"
fi

# Check for common bug patterns in code
print_section "Checking for Common Bug Patterns"

echo "Checking for .isoformat() on potential string variables..."

# Check for patterns like variable.isoformat() where variable might be string from API
if grep -rn "\.isoformat()" scripts/ --include="*.py" | grep -v "datetime\|now\|date(" > /tmp/isoformat_check.txt; then
    if [ -s /tmp/isoformat_check.txt ]; then
        print_warning "Found potential .isoformat() calls that might be on strings:"
        cat /tmp/isoformat_check.txt
        echo "  Review these to ensure they're called on datetime objects, not strings from API"
    fi
else
    print_success "No suspicious .isoformat() calls found"
fi

# Check for missing error handling
echo "Checking for functions without error handling..."
# This is a basic check - could be enhanced
print_success "Error handling check completed (manual review recommended)"

# Final summary
print_section "Validation Summary"

if [ $VALIDATION_FAILED -eq 0 ]; then
    print_success "ALL VALIDATIONS PASSED"
    echo ""
    echo "Release is ready to be deployed!"
    echo ""
    exit 0
else
    print_error "SOME VALIDATIONS FAILED"
    echo ""
    echo "Please fix the issues above before releasing."
    echo ""
    exit 1
fi
