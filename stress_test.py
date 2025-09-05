#!/usr/bin/env python3
"""
LiveSectional Stress Testing Suite

Comprehensive stress testing framework to validate reliability improvements
and prevent crashes and lockups, particularly when LED blinking effects are enabled.
"""

import time
import threading
import random
import subprocess
import logging
import signal
import sys
import os
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import json

# Optional psutil import
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    psutil = None

# Import reliability modules
from reliability_manager import get_reliability_manager, HealthStatus
from animation_controller import get_animation_controller, create_blink_effect, create_weather_effect
from logging_config import setup_logging, get_logger
from leds import create_led_strip, managed_led_strip


@dataclass
class TestResult:
    """Test result data structure"""
    test_name: str
    passed: bool
    duration: float
    error_message: Optional[str] = None
    metrics: Dict[str, Any] = None


class StressTestSuite:
    """Comprehensive stress testing suite for LiveSectional reliability"""
    
    def __init__(self):
        self.logger = get_logger('stress_test')
        self.results = []
        self.running = False
        self.start_time = None
        self.led_strip = None
        self.animation_controller = None
        self.reliability_manager = get_reliability_manager()
        
        # Test configuration
        self.test_duration = 600  # 10 minutes default
        self.max_memory_mb = 500
        self.max_cpu_percent = 80
        self.target_fps = 30
        
    def setup(self):
        """Setup test environment"""
        setup_logging()
        self.logger.info("Setting up stress test environment")
        
        try:
            # Initialize LED strip
            self.led_strip = create_led_strip(300)  # Assume 300 LEDs
            self.animation_controller = get_animation_controller(self.led_strip, self.target_fps)
            self.logger.info("Test environment setup complete")
        except Exception as e:
            self.logger.error(f"Failed to setup test environment: {e}")
            raise
    
    def cleanup(self):
        """Cleanup test environment"""
        self.logger.info("Cleaning up test environment")
        
        if self.animation_controller:
            self.animation_controller.stop_animation()
            
        if self.led_strip:
            self.led_strip.emergency_shutdown()
            
        self.logger.info("Test environment cleanup complete")
    
    def run_test(self, test_func, test_name: str, duration: int = 60) -> TestResult:
        """Run a single test and return results"""
        self.logger.info(f"Starting test: {test_name}")
        start_time = time.time()
        error_message = None
        metrics = {}
        
        try:
            # Run the test
            test_func(duration)
            
            # Collect metrics
            metrics = self._collect_metrics()
            
            # Check if test passed
            passed = self._validate_test_results(metrics)
            
        except Exception as e:
            error_message = str(e)
            passed = False
            self.logger.error(f"Test {test_name} failed: {e}")
        
        duration_actual = time.time() - start_time
        
        result = TestResult(
            test_name=test_name,
            passed=passed,
            duration=duration_actual,
            error_message=error_message,
            metrics=metrics
        )
        
        self.results.append(result)
        self.logger.info(f"Test {test_name} completed: {'PASS' if passed else 'FAIL'}")
        
        return result
    
    def _collect_metrics(self) -> Dict[str, Any]:
        """Collect system and application metrics"""
        if PSUTIL_AVAILABLE:
            process = psutil.Process()
            return {
                'memory_mb': process.memory_info().rss / 1024 / 1024,
                'cpu_percent': process.cpu_percent(),
                'thread_count': process.num_threads(),
                'file_descriptors': process.num_fds() if hasattr(process, 'num_fds') else 0,
                'timestamp': time.time()
            }
        else:
            # Fallback metrics when psutil is not available
            return {
                'memory_mb': 0.0,
                'cpu_percent': 0.0,
                'thread_count': threading.active_count(),
                'file_descriptors': 0,
                'timestamp': time.time()
            }
    
    def _validate_test_results(self, metrics: Dict[str, Any]) -> bool:
        """Validate test results against criteria"""
        if metrics['memory_mb'] > self.max_memory_mb:
            self.logger.warning(f"Memory usage too high: {metrics['memory_mb']:.1f}MB")
            return False
            
        if metrics['cpu_percent'] > self.max_cpu_percent:
            self.logger.warning(f"CPU usage too high: {metrics['cpu_percent']:.1f}%")
            return False
            
        return True
    
    def test_blinking_effects_stress(self, duration: int):
        """Test rapid LED blinking effects for extended periods"""
        self.logger.info("Running blinking effects stress test")
        
        # Create multiple blinking effects
        effects = []
        for i in range(10):
            effect = create_blink_effect(
                effect_id=f"stress_blink_{i}",
                color=(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)),
                duty_cycle=0.5,
                blink_rate=random.uniform(1.0, 5.0),
                pixel_indices=list(range(i * 30, (i + 1) * 30))
            )
            effects.append(effect)
            self.animation_controller.add_effect(effect)
            self.animation_controller.start_effect(effect.effect_id)
        
        # Run for specified duration
        start_time = time.time()
        while time.time() - start_time < duration:
            self.animation_controller.update()
            time.sleep(0.01)  # 100 FPS update rate
            
            # Randomly toggle effects
            if random.random() < 0.1:  # 10% chance each iteration
                effect = random.choice(effects)
                if effect.state.value == "running":
                    self.animation_controller.stop_effect(effect.effect_id)
                else:
                    self.animation_controller.start_effect(effect.effect_id)
        
        # Cleanup
        for effect in effects:
            self.animation_controller.remove_effect(effect.effect_id)
    
    def test_weather_effects_stress(self, duration: int):
        """Test all weather effects simultaneously"""
        self.logger.info("Running weather effects stress test")
        
        weather_types = ["rain", "snow", "lightning", "fog"]
        effects = []
        
        for i, weather_type in enumerate(weather_types):
            effect = create_weather_effect(
                effect_id=f"stress_weather_{weather_type}",
                effect_type=weather_type,
                intensity=random.uniform(0.5, 1.0),
                pixel_indices=list(range(i * 75, (i + 1) * 75))
            )
            effects.append(effect)
            self.animation_controller.add_effect(effect)
            self.animation_controller.start_effect(effect.effect_id)
        
        # Run for specified duration
        start_time = time.time()
        while time.time() - start_time < duration:
            self.animation_controller.update()
            time.sleep(0.01)
        
        # Cleanup
        for effect in effects:
            self.animation_controller.remove_effect(effect.effect_id)
    
    def test_rapid_config_changes(self, duration: int):
        """Test rapid configuration changes to trigger restarts"""
        self.logger.info("Running rapid config changes test")
        
        config_files = ['config.py', 'airports', 'hmdata']
        
        start_time = time.time()
        while time.time() - start_time < duration:
            # Simulate config file changes
            for config_file in config_files:
                if os.path.exists(config_file):
                    # Touch the file to change modification time
                    os.utime(config_file, (time.time(), time.time()))
            
            time.sleep(0.1)  # 10 changes per second
    
    def test_memory_leak_detection(self, duration: int):
        """Test for memory leaks during extended operation"""
        self.logger.info("Running memory leak detection test")
        
        if not PSUTIL_AVAILABLE:
            self.logger.warning("psutil not available, skipping memory leak detection test")
            return
        
        initial_memory = psutil.Process().memory_info().rss / 1024 / 1024
        memory_samples = []
        
        start_time = time.time()
        while time.time() - start_time < duration:
            # Create and destroy effects repeatedly
            for i in range(50):
                effect = create_blink_effect(
                    effect_id=f"leak_test_{i}",
                    color=(255, 0, 0),
                    pixel_indices=[i]
                )
                self.animation_controller.add_effect(effect)
                self.animation_controller.start_effect(effect.effect_id)
                time.sleep(0.001)
                self.animation_controller.remove_effect(effect.effect_id)
            
            # Sample memory usage
            current_memory = psutil.Process().memory_info().rss / 1024 / 1024
            memory_samples.append(current_memory)
            
            time.sleep(1)
        
        # Check for memory growth
        final_memory = memory_samples[-1]
        memory_growth = final_memory - initial_memory
        
        if memory_growth > 50:  # More than 50MB growth
            raise Exception(f"Memory leak detected: {memory_growth:.1f}MB growth")
    
    def test_concurrent_led_access(self, duration: int):
        """Test concurrent LED access from multiple threads"""
        self.logger.info("Running concurrent LED access test")
        
        def led_worker(worker_id: int):
            """Worker thread for LED operations"""
            for i in range(1000):
                try:
                    # Random LED operations
                    pixel = random.randint(0, 299)
                    color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
                    
                    if random.random() < 0.5:
                        self.led_strip.set_pixel_color(pixel, color)
                    else:
                        self.led_strip.show_pixels()
                    
                    time.sleep(0.001)
                except Exception as e:
                    self.logger.error(f"LED worker {worker_id} error: {e}")
        
        # Start multiple worker threads
        threads = []
        for i in range(10):
            thread = threading.Thread(target=led_worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for duration
        time.sleep(duration)
        
        # Stop threads
        for thread in threads:
            thread.join(timeout=1)
    
    def test_network_failure_simulation(self, duration: int):
        """Test system behavior during network failures"""
        self.logger.info("Running network failure simulation test")
        
        # This would simulate network failures by blocking network access
        # For now, we'll just test the reliability manager's circuit breaker
        start_time = time.time()
        while time.time() - start_time < duration:
            try:
                # Simulate network operations that might fail
                self.reliability_manager.safe_call(
                    "network_test",
                    lambda: time.sleep(0.1)  # Simulate network call
                )
            except Exception as e:
                self.logger.debug(f"Expected network failure: {e}")
            
            time.sleep(0.1)
    
    def test_hardware_conflict_detection(self, duration: int):
        """Test hardware conflict detection and recovery"""
        self.logger.info("Running hardware conflict detection test")
        
        start_time = time.time()
        while time.time() - start_time < duration:
            # Test LED responsiveness
            if not self.led_strip.test_connection():
                self.logger.warning("LED responsiveness test failed")
            
            # Test hardware status
            status = self.led_strip.get_status()
            if not status['initialized']:
                raise Exception("LED strip lost initialization")
            
            time.sleep(1)
    
    def test_soak_test(self, duration: int = 3600):
        """Long-term soak test for 1 hour"""
        self.logger.info(f"Running soak test for {duration} seconds")
        
        start_time = time.time()
        iteration = 0
        
        while time.time() - start_time < duration:
            iteration += 1
            
            # Run a mix of all tests
            if iteration % 10 == 0:
                self.test_blinking_effects_stress(10)
            elif iteration % 10 == 1:
                self.test_weather_effects_stress(10)
            elif iteration % 10 == 2:
                self.test_concurrent_led_access(10)
            else:
                # Normal operation simulation
                self.animation_controller.update()
            
            # Health check
            health_status = self.reliability_manager.check_health(self.led_strip)
            if health_status == HealthStatus.CRITICAL:
                raise Exception("Critical health status detected during soak test")
            
            time.sleep(1)
    
    def run_all_tests(self, test_duration: int = 60):
        """Run all stress tests"""
        self.logger.info("Starting comprehensive stress test suite")
        self.start_time = time.time()
        self.running = True
        
        try:
            self.setup()
            
            # Run individual tests
            tests = [
                (self.test_blinking_effects_stress, "Blinking Effects Stress", test_duration),
                (self.test_weather_effects_stress, "Weather Effects Stress", test_duration),
                (self.test_rapid_config_changes, "Rapid Config Changes", test_duration // 2),
                (self.test_memory_leak_detection, "Memory Leak Detection", test_duration * 2),
                (self.test_concurrent_led_access, "Concurrent LED Access", test_duration),
                (self.test_network_failure_simulation, "Network Failure Simulation", test_duration),
                (self.test_hardware_conflict_detection, "Hardware Conflict Detection", test_duration),
            ]
            
            for test_func, test_name, duration in tests:
                if not self.running:
                    break
                    
                result = self.run_test(test_func, test_name, duration)
                if not result.passed:
                    self.logger.error(f"Test {test_name} failed, stopping test suite")
                    break
            
            # Run soak test if all individual tests passed
            if all(r.passed for r in self.results):
                self.logger.info("All individual tests passed, starting soak test")
                self.run_test(self.test_soak_test, "Soak Test", 3600)  # 1 hour
            
        except KeyboardInterrupt:
            self.logger.info("Stress test interrupted by user")
        except Exception as e:
            self.logger.error(f"Stress test suite failed: {e}")
        finally:
            self.cleanup()
            self.running = False
            self._generate_report()
    
    def _generate_report(self):
        """Generate test report"""
        total_duration = time.time() - self.start_time if self.start_time else 0
        passed_tests = sum(1 for r in self.results if r.passed)
        total_tests = len(self.results)
        
        report = {
            'summary': {
                'total_tests': total_tests,
                'passed_tests': passed_tests,
                'failed_tests': total_tests - passed_tests,
                'success_rate': (passed_tests / total_tests * 100) if total_tests > 0 else 0,
                'total_duration': total_duration
            },
            'results': [
                {
                    'test_name': r.test_name,
                    'passed': r.passed,
                    'duration': r.duration,
                    'error_message': r.error_message,
                    'metrics': r.metrics
                }
                for r in self.results
            ]
        }
        
        # Save report
        report_file = f"stress_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        # Print summary
        self.logger.info("=" * 50)
        self.logger.info("STRESS TEST REPORT")
        self.logger.info("=" * 50)
        self.logger.info(f"Total Tests: {total_tests}")
        self.logger.info(f"Passed: {passed_tests}")
        self.logger.info(f"Failed: {total_tests - passed_tests}")
        self.logger.info(f"Success Rate: {report['summary']['success_rate']:.1f}%")
        self.logger.info(f"Total Duration: {total_duration:.1f} seconds")
        self.logger.info(f"Report saved to: {report_file}")
        
        # Print individual results
        for result in self.results:
            status = "PASS" if result.passed else "FAIL"
            self.logger.info(f"{result.test_name}: {status} ({result.duration:.1f}s)")
            if result.error_message:
                self.logger.error(f"  Error: {result.error_message}")


def main():
    """Main function for running stress tests"""
    import argparse
    
    parser = argparse.ArgumentParser(description='LiveSectional Stress Test Suite')
    parser.add_argument('--duration', type=int, default=60, help='Test duration in seconds')
    parser.add_argument('--test', type=str, help='Run specific test only')
    parser.add_argument('--soak', action='store_true', help='Run soak test only')
    
    args = parser.parse_args()
    
    # Setup signal handler for graceful shutdown
    def signal_handler(signum, frame):
        print("\nReceived interrupt signal, shutting down gracefully...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Run tests
    suite = StressTestSuite()
    
    if args.soak:
        suite.setup()
        try:
            suite.run_test(suite.test_soak_test, "Soak Test", args.duration)
        finally:
            suite.cleanup()
    elif args.test:
        suite.setup()
        try:
            test_func = getattr(suite, f"test_{args.test}")
            suite.run_test(test_func, args.test.replace('_', ' ').title(), args.duration)
        finally:
            suite.cleanup()
    else:
        suite.run_all_tests(args.duration)


if __name__ == "__main__":
    main()
