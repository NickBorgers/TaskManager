#!/bin/bash
# Containerized test runner script for daily_planned_date_review.py

set -e

echo "🐳 Containerized Test Runner for Daily Planned Date Review Script"
echo "================================================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    print_error "Docker is not running. Please start Docker and try again."
    exit 1
fi

# Create necessary directories
print_status "Creating test directories..."
mkdir -p tests htmlcov

# Build the test image
print_status "Building test Docker image..."
docker build --target test -t notion-home-task-manager:test .

if [ $? -eq 0 ]; then
    print_success "Test image built successfully!"
else
    print_error "Failed to build test image"
    exit 1
fi

echo ""
print_status "Running tests in container..."

# Run tests using docker-compose
docker-compose --profile test up test --build --abort-on-container-exit

# Check if tests passed
if [ $? -eq 0 ]; then
    print_success "All tests passed!"
else
    print_error "Some tests failed"
    exit 1
fi

echo ""
print_status "Test Summary:"
echo "📊 Coverage report generated in htmlcov/index.html"
echo "🐳 Tests ran in isolated container environment"
echo "🔒 No external dependencies required (NOTION_INTEGRATION_SECRET mocked)"

# Optional: Open coverage report in browser
if command -v xdg-open &> /dev/null; then
    print_status "Opening coverage report in browser..."
    xdg-open htmlcov/index.html
elif command -v open &> /dev/null; then
    print_status "Opening coverage report in browser..."
    open htmlcov/index.html
fi

echo ""
echo "🎯 Containerized Testing Benefits:"
echo "- Isolated environment with consistent dependencies"
echo "- No need to install Python or packages locally"
echo "- Tests run in the same environment as production"
echo "- Easy to run on CI/CD pipelines"
echo ""
echo "📝 Available commands:"
echo "  ./run_tests_container.sh                    # Run all tests"
echo "  docker-compose --profile test up test       # Run tests with docker-compose"
echo "  docker run --rm notion-home-task-manager:test pytest tests/ -k 'test_name'  # Run specific test"
echo "  docker run --rm notion-home-task-manager:test pytest tests/ -m unit         # Run unit tests only"

