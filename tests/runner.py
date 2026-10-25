# ai-generated: 90% - test runner emitting ITSMLAB-TESTS marker
import sys
import pytest

class MarkerPlugin:
    def __init__(self):
        self.passed = 0
        self.failed = 0

    def pytest_runtest_logreport(self, report):
        if report.when == "call":
            if report.passed:
                self.passed += 1
            elif report.failed:
                self.failed += 1

if __name__ == "__main__":
    plugin = MarkerPlugin()
    exit_code = pytest.main(["-q", "tests/test_dora.py"], plugins=[plugin])
    print(f"ITSMLAB-TESTS: passed={plugin.passed} failed={plugin.failed}")
    sys.exit(0 if exit_code == 0 else 1)
