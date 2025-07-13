#!/usr/bin/env python3
"""
Simple coverage report for Project Manager
"""

import json
import subprocess
from pathlib import Path


def main():
    """Generate simple coverage report"""
    print("=" * 60)
    print("PROJECT MANAGER - COVERAGE REPORT")
    print("=" * 60)

    # Read coverage data
    status_file = Path("htmlcov/status.json")
    if not status_file.exists():
        print("❌ Coverage data not found. Please run tests with coverage first:")
        print("   python3 -m pytest tests/ --cov=src --cov-report=html")
        return

    try:
        with open(status_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"❌ Error reading coverage data: {e}")
        return

    files = data.get("files", {})

    # Calculate statistics
    total_statements = 0
    total_missing = 0
    total_branches = 0
    total_branch_missing = 0

    file_reports = []

    for file_data in files.values():
        file_info = file_data.get("index", {})
        file_path = file_info.get("file", "")

        if not file_path.startswith("src/"):
            continue

        nums = file_info.get("nums", {})
        statements = nums.get("n_statements", 0)
        missing = nums.get("n_missing", 0)
        branches = nums.get("n_branches", 0)
        branch_missing = nums.get("n_missing_branches", 0)

        total_statements += statements
        total_missing += missing
        total_branches += branches
        total_branch_missing += branch_missing

        coverage_percent = (
            ((statements - missing) / statements * 100) if statements > 0 else 0
        )
        branch_coverage_percent = (
            ((branches - branch_missing) / branches * 100) if branches > 0 else 0
        )

        file_reports.append(
            {
                "file": file_path,
                "statements": statements,
                "missing": missing,
                "coverage": coverage_percent,
                "branches": branches,
                "branch_missing": branch_missing,
                "branch_coverage": branch_coverage_percent,
            }
        )

    # Sort by coverage
    file_reports.sort(key=lambda x: x["coverage"])

    # Overall statistics
    overall_coverage = (
        ((total_statements - total_missing) / total_statements * 100)
        if total_statements > 0
        else 0
    )
    overall_branch_coverage = (
        ((total_branches - total_branch_missing) / total_branches * 100)
        if total_branches > 0
        else 0
    )

    print("\n📊 OVERALL COVERAGE:")
    print(
        f"   Statements: {total_statements - total_missing} / {total_statements} ({overall_coverage:.1f}%)"
    )
    print(
        f"   Branches: {total_branches - total_branch_missing} / {total_branches} ({overall_branch_coverage:.1f}%)"
    )
    print(f"   Missing statements: {total_missing}")
    print(f"   Missing branches: {total_branch_missing}")

    # File breakdown
    print("\n📁 FILE BREAKDOWN:")
    print("-" * 100)
    print(
        f"{'File': <40} | {'Stmts': >6} | {'Miss': >4} | {'Cover': >6} | {'Branch': >6} | {'BrMiss': >6}"
    )
    print("-" * 100)

    for report in file_reports:
        status = (
            "🟢"
            if report["coverage"] >= 80
            else "🟡" if report["coverage"] >= 50 else "🔴"
        )
        print(
            f"{status} {report['file']:<37} | "
            f"{report['statements']:>6} | "
            f"{report['missing']:>4} | "
            f"{report['coverage']:>5.1f}% | "
            f"{report['branch_coverage']:>5.1f}% | "
            f"{report['branch_missing']:>6}"
        )

    # Files needing attention
    low_coverage = [f for f in file_reports if f["coverage"] < 80]
    if low_coverage:
        print("\n⚠️  FILES NEEDING ATTENTION (Coverage < 80%):")
        print("-" * 60)
        for report in low_coverage:
            print(f"   {report['file']} ({report['coverage']:.1f}% coverage)")

    # Recommendations
    print("\n💡 RECOMMENDATIONS:")
    print("-" * 30)

    if overall_coverage < 80:
        print(
            f"   ⚠️  Overall coverage is {overall_coverage:.1f}%, below the 80% target"
        )
        print("      Consider adding more tests for uncovered code")

    if total_missing > 0:
        print(f"   📝 {total_missing} statements are not covered by tests")
        print("      Focus on files with lowest coverage first")

    if total_branch_missing > 0:
        print(f"   🔄 {total_branch_missing} branches are not covered by tests")
        print("      Add tests to cover different code paths and edge cases")

    # Test status
    print("\n🧪 TEST STATUS:")
    print("-" * 20)

    try:
        result = subprocess.run(
            ["python3", "-m", "pytest", "tests/", "--tb=no", "-q"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            print("   ✅ All tests passing")
        else:
            print("   ❌ Some tests failing")
            print("      Check test output for details")
    except (OSError, subprocess.SubprocessError) as e:
        print(f"   ⚠️  Could not determine test status: {e}")

    print("\n📖 For detailed HTML report, open: htmlcov/index.html")


if __name__ == "__main__":
    main()
