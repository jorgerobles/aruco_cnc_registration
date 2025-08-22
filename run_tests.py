#!/usr/bin/env python3
# run_tests.py
"""
Test Runner for GRBL Camera Registration Application
Runs unit tests and provides testing utilities
"""

import unittest
import sys
import os
import argparse
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def run_camera_manager_tests():
    """Run only CameraManager tests"""
    print("Running CameraManager Tests...")
    print("=" * 50)

    # Import test module
    from tests.test_camera_manager import TestCameraManager, TestCameraManagerIntegration

    # Create test suite using modern TestLoader
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test cases using loadTestsFromTestCase
    suite.addTests(loader.loadTestsFromTestCase(TestCameraManager))
    suite.addTests(loader.loadTestsFromTestCase(TestCameraManagerIntegration))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


def run_all_tests():
    """Run all available tests"""
    print("Running All Tests...")
    print("=" * 50)

    # Discover all tests
    loader = unittest.TestLoader()
    start_dir = 'tests'

    # Create tests directory if it doesn't exist
    Path(start_dir).mkdir(exist_ok=True)

    suite = loader.discover(start_dir, pattern='test_*.py')

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


def run_store_integration_tests():
    """Run store integration tests specifically"""
    print("Running Store Integration Tests...")
    print("=" * 50)

    from tests.test_camera_manager import TestCameraManagerIntegration

    # Create test suite using modern TestLoader
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestCameraManagerIntegration))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


def create_test_environment():
    """Create test environment and directories"""
    print("Creating test environment...")

    # Create test directories
    test_dirs = [
        'tests',
        'tests/fixtures',
        'tests/data',
        'config',
        'calibration'
    ]

    for test_dir in test_dirs:
        Path(test_dir).mkdir(exist_ok=True)
        print(f"✓ Created directory: {test_dir}")

    # Create test fixtures
    create_test_fixtures()

    print("Test environment ready!")


def create_test_fixtures():
    """Create test fixtures and sample data"""
    import numpy as np

    # Create sample calibration file
    calibration_dir = Path('tests/fixtures')
    calibration_file = calibration_dir / 'test_calibration.npz'

    # Sample calibration data
    camera_matrix = np.array([
        [800, 0, 320],
        [0, 800, 240],
        [0, 0, 1]
    ], dtype=np.float32)

    dist_coeffs = np.array([-0.1, 0.05, 0, 0, 0], dtype=np.float32)

    np.savez(str(calibration_file),
             camera_matrix=camera_matrix,
             dist_coeffs=dist_coeffs)

    print(f"✓ Created test calibration: {calibration_file}")


def run_coverage_analysis():
    """Run tests with coverage analysis if available"""
    try:
        import coverage
        print("Running tests with coverage analysis...")

        # Start coverage
        cov = coverage.Coverage()
        cov.start()

        # Run tests
        success = run_all_tests()

        # Stop coverage and report
        cov.stop()
        cov.save()

        print("\nCoverage Report:")
        print("=" * 50)
        cov.report(show_missing=True)

        # Generate HTML report
        html_dir = Path('tests/coverage_html')
        html_dir.mkdir(exist_ok=True)
        cov.html_report(directory=str(html_dir))
        print(f"HTML coverage report generated: {html_dir}/index.html")

        return success

    except ImportError:
        print("Coverage package not available. Install with: pip install coverage")
        print("Running tests without coverage...")
        return run_all_tests()


def validate_refactoring():
    """Validate that the refactoring maintains functionality"""
    print("Validating Refactoring...")
    print("=" * 50)

    validation_passed = True

    # Test 1: Import test
    try:
        from services.camera_manager import CameraManager
        from store.store import ApplicationStore
        print("✓ Import test passed")
    except ImportError as e:
        print(f"❌ Import test failed: {e}")
        validation_passed = False

    # Test 2: Instantiation test
    try:
        store = ApplicationStore()
        camera_manager = CameraManager(store=store)
        print("✓ Instantiation test passed")
    except Exception as e:
        print(f"❌ Instantiation test failed: {e}")
        validation_passed = False

    # Test 3: Method signature test
    try:
        store = ApplicationStore()
        camera_manager = CameraManager(store=store)

        # Test that methods return boolean values
        result_connect = camera_manager.connect()
        result_disconnect = camera_manager.disconnect()
        result_load_calib = camera_manager.load_calibration("non_existent.npz")

        assert isinstance(result_connect, bool), "connect() should return bool"
        assert isinstance(result_disconnect, bool), "disconnect() should return bool"
        assert isinstance(result_load_calib, bool), "load_calibration() should return bool"

        print("✓ Method signature test passed")
    except Exception as e:
        print(f"❌ Method signature test failed: {e}")
        validation_passed = False

    # Test 4: Store integration test
    try:
        store = ApplicationStore()
        camera_manager = CameraManager(store=store)

        # Check that store is accessible
        assert camera_manager.store is store, "Store should be accessible"

        print("✓ Store integration test passed")
    except Exception as e:
        print(f"❌ Store integration test failed: {e}")
        validation_passed = False

    if validation_passed:
        print("🎉 Refactoring validation PASSED!")
    else:
        print("❌ Refactoring validation FAILED!")

    return validation_passed


def benchmark_performance():
    """Basic performance benchmarking"""
    import time
    print("Running Performance Benchmarks...")
    print("=" * 50)

    # Mock benchmark for store operations
    from store.store import ApplicationStore
    from store.actions import CameraActions

    store = ApplicationStore()

    # Benchmark store dispatch performance
    start_time = time.time()
    num_dispatches = 1000

    for i in range(num_dispatches):
        store.dispatch(CameraActions.connection_changed(i % 2 == 0, 0))

    end_time = time.time()
    duration = end_time - start_time

    print(f"Store Dispatch Performance:")
    print(f"  {num_dispatches} dispatches in {duration:.4f} seconds")
    print(f"  {num_dispatches / duration:.0f} dispatches/second")

    if duration < 1.0:  # Should be very fast
        print("✓ Store performance acceptable")
    else:
        print("❌ Store performance may be slow")


def main():
    """Main test runner function"""
    parser = argparse.ArgumentParser(description='Test Runner for GRBL Camera Registration')
    parser.add_argument('--camera', action='store_true',
                        help='Run only CameraManager tests')
    parser.add_argument('--integration', action='store_true',
                        help='Run only integration tests')
    parser.add_argument('--coverage', action='store_true',
                        help='Run tests with coverage analysis')
    parser.add_argument('--validate', action='store_true',
                        help='Validate refactoring')
    parser.add_argument('--benchmark', action='store_true',
                        help='Run performance benchmarks')
    parser.add_argument('--setup', action='store_true',
                        help='Setup test environment')
    parser.add_argument('--all', action='store_true',
                        help='Run all tests and validations')

    args = parser.parse_args()

    # If no arguments, show help
    if not any(vars(args).values()):
        parser.print_help()
        return

    success = True

    # Setup test environment if requested
    if args.setup or args.all:
        create_test_environment()

    # Run validation if requested
    if args.validate or args.all:
        success &= validate_refactoring()

    # Run specific tests
    if args.camera:
        success &= run_camera_manager_tests()
    elif args.integration:
        success &= run_store_integration_tests()
    elif args.coverage:
        success &= run_coverage_analysis()
    elif args.all:
        success &= run_all_tests()
    else:
        # Default: run all tests
        success &= run_all_tests()

    # Run benchmarks if requested
    if args.benchmark or args.all:
        benchmark_performance()

    # Print final result
    print("\n" + "=" * 50)
    if success:
        print("🎉 ALL TESTS PASSED!")
        exit_code = 0
    else:
        print("❌ SOME TESTS FAILED!")
        exit_code = 1

    print("=" * 50)
    sys.exit(exit_code)


if __name__ == '__main__':
    main()