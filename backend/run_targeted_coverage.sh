#!/bin/bash
# Script to run coverage for specific target files mentioned in Task 3.1

echo "Running coverage for target files: router.py, prd_compliant_workflow.py, qualifier_utils.py"
echo "=============================================================================="

# Run coverage for specific files
uv run pytest tests/test_router_coverage.py tests/test_prd_workflow_coverage.py tests/test_qualifier_utils.py \
    --cov=agents/router \
    --cov=agents/prd_compliant_workflow \
    --cov=tools/qualifier_utils \
    --cov-report=term-missing \
    --cov-report=html:htmlcov_targeted \
    --cov-fail-under=90 \
    -v

echo ""
echo "Coverage report generated in htmlcov_targeted/"