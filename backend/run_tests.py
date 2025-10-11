#!/usr/bin/env python3
"""
Comprehensive Test Runner for IG Real Estate Lead Management System

Runs all tests with detailed reporting and coverage analysis.
"""

import sys
import subprocess
import os
from pathlib import Path

def run_tests():
    """Run all tests with comprehensive reporting."""
    
    # Ensure we're in the backend directory
    backend_dir = Path(__file__).parent
    os.chdir(backend_dir)
    
    print("🚀 Starting Comprehensive Test Suite for IG Real Estate System")
    print("=" * 70)
    
    # Test discovery and execution
    test_commands = [
        # Run all tests with verbose output
        ["python", "-m", "pytest", "tests/", "-v", "--tb=short"],
        
        # Run tests with coverage if pytest-cov is available
        ["python", "-m", "pytest", "tests/", "--cov=.", "--cov-report=term-missing", "--cov-report=html"],
        
        # Run specific test categories
        ["python", "-m", "pytest", "tests/test_integration.py", "-v", "-k", "integration"],
        ["python", "-m", "pytest", "tests/test_agents.py", "-v", "-k", "agent"],
        ["python", "-m", "pytest", "tests/test_tools.py", "-v", "-k", "tool"]
    ]
    
    results = []
    
    for i, cmd in enumerate(test_commands):
        print(f"\n📋 Running Test Command {i+1}/{len(test_commands)}")
        print(f"Command: {' '.join(cmd)}")
        print("-" * 50)
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            results.append({
                "command": " ".join(cmd),
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr
            })
            
            if result.returncode == 0:
                print("✅ PASSED")
                if result.stdout:
                    print(result.stdout)
            else:
                print("❌ FAILED")
                if result.stderr:
                    print("STDERR:", result.stderr)
                if result.stdout:
                    print("STDOUT:", result.stdout)
                    
        except subprocess.TimeoutExpired:
            print("⏰ TIMEOUT - Test took longer than 5 minutes")
            results.append({
                "command": " ".join(cmd),
                "returncode": -1,
                "stdout": "",
                "stderr": "Test timeout after 5 minutes"
            })
        except FileNotFoundError:
            print("⚠️  SKIPPED - pytest not available or command not found")
            results.append({
                "command": " ".join(cmd),
                "returncode": -2,
                "stdout": "",
                "stderr": "Command not found"
            })
    
    # Summary Report
    print("\n" + "=" * 70)
    print("📊 TEST EXECUTION SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for r in results if r["returncode"] == 0)
    failed = sum(1 for r in results if r["returncode"] > 0)
    skipped = sum(1 for r in results if r["returncode"] < 0)
    
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"⚠️  Skipped: {skipped}")
    print(f"📈 Total: {len(results)}")
    
    if failed > 0:
        print("\n🔍 FAILED TEST DETAILS:")
        for result in results:
            if result["returncode"] > 0:
                print(f"\n❌ {result['command']}")
                if result["stderr"]:
                    print(f"Error: {result['stderr'][:500]}...")
    
    # Test Coverage Report
    coverage_html_path = backend_dir / "htmlcov" / "index.html"
    if coverage_html_path.exists():
        print(f"\n📋 Coverage report generated: {coverage_html_path}")
    
    return failed == 0

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)