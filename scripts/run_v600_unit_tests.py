"""Run the normal provider-free v6 unit-test suite with stdlib unittest."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = PROJECT_ROOT / "tests"
PATTERN = "test_*.py"


def main() -> int:
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    if not TEST_ROOT.is_dir():
        raise SystemExit("tests directory is missing")

    suite = unittest.defaultTestLoader.discover(
        start_dir=str(TEST_ROOT),
        pattern=PATTERN,
        top_level_dir=str(PROJECT_ROOT),
    )
    test_count = suite.countTestCases()
    if test_count < 1:
        raise SystemExit("unit test discovery returned zero tests")

    print("v600_unit_test_runner: unittest")
    print(f"v600_unit_test_discovery_root: {TEST_ROOT.relative_to(PROJECT_ROOT)}")
    print(f"v600_unit_test_pattern: {PATTERN}")
    print(f"v600_unit_test_count: {test_count}")

    result = unittest.TextTestRunner(
        stream=sys.stdout,
        verbosity=2,
    ).run(suite)

    if not result.wasSuccessful():
        print("v600_unit_test_result: FAIL")
        return 1

    print("v600_unit_test_result: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
