"""
LiveSectional Reliability Manager

Provides centralized reliability services including health monitoring, circuit breakers,
resource management, and frame rate limiting to prevent system crashes and lockups.
"""

import time
import threading
import logging
import signal
import sys
import os
from contextlib import contextmanager
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass
from enum import Enum
import subprocess

# Optional psutil import
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    psutil = None


class HealthStatus(Enum):
    """Health status enumeration"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    FAILED = "failed"


@dataclass
class HealthMetrics:
    """Health monitoring metrics"""
    timestamp: float
    main_loop_heartbeat: float
    memory_usage_mb: float
    cpu_usage_percent: float
    led_responsive: bool
    last_metar_update: float
    log_file_size_mb: float
    disk_space_mb: int
    frame_rate: float
    error_count: int


class CircuitBreaker:
    """Circuit breaker pattern for repeated failures"""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        
    def call(self, func: Callable, *args, **kwargs):
        """Execute function with circuit breaker protection"""
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "HALF_OPEN"
            else:
                raise Exception("Circuit breaker is OPEN")
        
        try:
            result = func(*args, **kwargs)
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
            
            raise e


class FrameRateLimiter:
    """Frame rate limiter to prevent CPU thrashing during LED updates"""
    
    def __init__(self, target_fps: int = 30):
        self.target_fps = target_fps
        self.frame_time = 1.0 / target_fps
        self.last_frame_time = 0
        self.frame_skip_count = 0
        self.max_frame_time = 0.1  # 100ms max frame time (potential hang detection)
        
    def wait_for_next_frame(self) -> bool:
        """Wait for next frame time, returns True if frame should be rendered"""
        current_time = time.time()
        elapsed = current_time - self.last_frame_time
        
        # Detect potential hangs
        if elapsed > self.max_frame_time:
            logging.warning(f"Frame time exceeded {self.max_frame_time}s: {elapsed:.3f}s")
            self.frame_skip_count += 1
            if self.frame_skip_count > 10:
                raise Exception("Excessive frame skipping detected - potential hang")
        
        # Frame rate limiting
        if elapsed < self.frame_time:
            sleep_time = self.frame_time - elapsed
            time.sleep(sleep_time)
            self.frame_skip_count = 0
        else:
            self.frame_skip_count = 0
            
        self.last_frame_time = time.time()
        return True


class SharedClock:
    """Shared timing clock for coordinated animations"""
    
    def __init__(self):
        self.start_time = time.time()
        self.paused = False
        self.pause_offset = 0
        
    def get_time(self) -> float:
        """Get current time accounting for pauses"""
        if self.paused:
            return self.start_time + self.pause_offset
        return time.time() - self.start_time + self.pause_offset
        
    def pause(self):
        """Pause the clock"""
        if not self.paused:
            self.pause_offset = self.get_time()
            self.paused = True
            
    def resume(self):
        """Resume the clock"""
        if self.paused:
            self.start_time = time.time()
            self.paused = False


class ResourceManager:
    """Context manager for resource cleanup"""
    
    def __init__(self):
        self.resources = []
        self.cleanup_handlers = []
        
    def register_resource(self, resource, cleanup_func: Callable):
        """Register a resource with its cleanup function"""
        self.resources.append((resource, cleanup_func))
        
    def register_cleanup(self, cleanup_func: Callable):
        """Register a general cleanup function"""
        self.cleanup_handlers.append(cleanup_func)
        
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Cleanup resources in reverse order
        for resource, cleanup_func in reversed(self.resources):
            try:
                cleanup_func(resource)
            except Exception as e:
                logging.error(f"Error cleaning up resource: {e}")
                
        # Run general cleanup handlers
        for cleanup_func in self.cleanup_handlers:
            try:
                cleanup_func()
            except Exception as e:
                logging.error(f"Error in cleanup handler: {e}")


class HealthMonitor:
    """Health monitoring and self-test system"""
    
    def __init__(self, check_interval: int = 30):
        self.check_interval = check_interval
        self.last_heartbeat = time.time()
        self.last_metar_update = 0
        self.led_last_test = 0
        self.led_test_interval = 60  # Test LED every 60 seconds
        self.metrics_history = []
        self.max_history = 100
        self.logger = logging.getLogger('health')
        
        # Health thresholds
        self.memory_warning_mb = 200
        self.memory_critical_mb = 400
        self.cpu_warning_percent = 70
        self.cpu_critical_percent = 90
        self.heartbeat_timeout = 60
        self.metar_timeout = 300  # 5 minutes
        
    def heartbeat(self):
        """Update main loop heartbeat"""
        self.last_heartbeat = time.time()
        
        # Send systemd watchdog notification
        try:
            from systemd.daemon import notify
            notify('WATCHDOG=1')
        except ImportError:
            pass  # systemd not available
        
    def update_metar(self):
        """Update last METAR update timestamp"""
        self.last_metar_update = time.time()
        
    def test_led_responsiveness(self, led_controller) -> bool:
        """Test LED strip responsiveness"""
        try:
            if not hasattr(led_controller, 'test_connection'):
                return True  # Skip test if not supported
                
            start_time = time.time()
            led_controller.test_connection()
            response_time = time.time() - start_time
            
            # LED should respond within 100ms
            return response_time < 0.1
        except Exception as e:
            self.logger.error(f"LED responsiveness test failed: {e}")
            return False
            
    def collect_metrics(self, led_controller=None) -> HealthMetrics:
        """Collect current health metrics"""
        current_time = time.time()
        
        # Memory usage
        if PSUTIL_AVAILABLE:
            process = psutil.Process()
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024
            cpu_percent = process.cpu_percent()
        else:
            # Fallback to /proc/meminfo and /proc/stat
            memory_mb = self._get_memory_usage_fallback()
            cpu_percent = self._get_cpu_usage_fallback()
        
        # LED responsiveness
        led_responsive = True
        if led_controller and current_time - self.led_last_test > self.led_test_interval:
            led_responsive = self.test_led_responsiveness(led_controller)
            self.led_last_test = current_time
            
        # Log file size
        log_size_mb = 0
        try:
            log_file = "/var/log/livesectional/livesectional.log"
            if os.path.exists(log_file):
                log_size_mb = os.path.getsize(log_file) / 1024 / 1024
        except:
            pass
            
        # Disk space
        disk_space_mb = 0
        try:
            if PSUTIL_AVAILABLE:
                disk_usage = psutil.disk_usage('/')
                disk_space_mb = disk_usage.free / 1024 / 1024
            else:
                disk_space_mb = self._get_disk_usage_fallback()
        except:
            pass
            
        # Frame rate (simplified - would need actual frame tracking)
        frame_rate = 30.0  # Placeholder
        
        metrics = HealthMetrics(
            timestamp=current_time,
            main_loop_heartbeat=self.last_heartbeat,
            memory_usage_mb=memory_mb,
            cpu_usage_percent=cpu_percent,
            led_responsive=led_responsive,
            last_metar_update=self.last_metar_update,
            log_file_size_mb=log_size_mb,
            disk_space_mb=disk_space_mb,
            frame_rate=frame_rate,
            error_count=0  # Would track actual error count
        )
        
        # Store in history
        self.metrics_history.append(metrics)
        if len(self.metrics_history) > self.max_history:
            self.metrics_history.pop(0)
            
        return metrics
        
    def get_health_status(self) -> HealthStatus:
        """Determine current health status"""
        if not self.metrics_history:
            return HealthStatus.HEALTHY
            
        latest = self.metrics_history[-1]
        current_time = time.time()
        
        # Check for critical conditions
        if (latest.memory_usage_mb > self.memory_critical_mb or
            latest.cpu_usage_percent > self.cpu_critical_percent or
            current_time - latest.main_loop_heartbeat > self.heartbeat_timeout or
            not latest.led_responsive):
            return HealthStatus.CRITICAL
            
        # Check for degraded conditions
        if (latest.memory_usage_mb > self.memory_warning_mb or
            latest.cpu_usage_percent > self.cpu_warning_percent or
            current_time - latest.last_metar_update > self.metar_timeout or
            latest.log_file_size_mb > 50):  # Log file too large
            return HealthStatus.DEGRADED
            
        return HealthStatus.HEALTHY
        
    def _get_memory_usage_fallback(self) -> float:
        """Fallback memory usage calculation using /proc/meminfo"""
        try:
            with open('/proc/meminfo', 'r') as f:
                for line in f:
                    if line.startswith('MemAvailable:'):
                        # Convert from KB to MB
                        return float(line.split()[1]) / 1024
            # Fallback if MemAvailable not found
            with open('/proc/meminfo', 'r') as f:
                for line in f:
                    if line.startswith('MemFree:'):
                        return float(line.split()[1]) / 1024
        except:
            pass
        return 0.0
        
    def _get_cpu_usage_fallback(self) -> float:
        """Fallback CPU usage calculation using /proc/stat"""
        try:
            with open('/proc/stat', 'r') as f:
                line = f.readline()
                if line.startswith('cpu '):
                    values = line.split()
                    # Calculate idle time
                    idle = int(values[4]) + int(values[5])
                    total = sum(int(v) for v in values[1:8])
                    return 100.0 * (1.0 - idle / total) if total > 0 else 0.0
        except:
            pass
        return 0.0
        
    def _get_disk_usage_fallback(self) -> int:
        """Fallback disk usage calculation using shutil"""
        try:
            import shutil
            usage = shutil.disk_usage('/')
            return usage.free / 1024 / 1024  # Convert to MB
        except:
            pass
        return 0
        
    def should_restart(self) -> bool:
        """Determine if system should restart due to health issues"""
        status = self.get_health_status()
        return status in [HealthStatus.CRITICAL, HealthStatus.FAILED]


class ReliabilityManager:
    """Main reliability manager coordinating all reliability services"""
    
    def __init__(self):
        self.health_monitor = HealthMonitor()
        self.frame_limiter = FrameRateLimiter()
        self.shared_clock = SharedClock()
        self.circuit_breakers = {}
        self.resource_manager = ResourceManager()
        self.logger = logging.getLogger('reliability')
        self.shutdown_requested = False
        
        # Setup signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, initiating graceful shutdown")
        self.shutdown_requested = True
        
    def get_circuit_breaker(self, name: str) -> CircuitBreaker:
        """Get or create a circuit breaker for a specific operation"""
        if name not in self.circuit_breakers:
            self.circuit_breakers[name] = CircuitBreaker()
        return self.circuit_breakers[name]
        
    def safe_call(self, name: str, func: Callable, *args, **kwargs):
        """Execute function with circuit breaker protection"""
        breaker = self.get_circuit_breaker(name)
        return breaker.call(func, *args, **kwargs)
        
    def check_health(self, led_controller=None) -> HealthStatus:
        """Check system health and return status"""
        self.health_monitor.heartbeat()
        metrics = self.health_monitor.collect_metrics(led_controller)
        status = self.health_monitor.get_health_status()
        
        if status != HealthStatus.HEALTHY:
            self.logger.warning(f"Health status: {status}, metrics: {metrics}")
            
        return status
        
    def should_restart(self) -> bool:
        """Check if system should restart"""
        return self.health_monitor.should_restart()
        
    def is_shutdown_requested(self) -> bool:
        """Check if shutdown has been requested"""
        return self.shutdown_requested
        
    def emergency_shutdown(self, led_controller=None):
        """Emergency shutdown with resource cleanup"""
        self.logger.critical("Emergency shutdown initiated")
        
        try:
            if led_controller:
                led_controller.emergency_shutdown()
        except Exception as e:
            self.logger.error(f"Error during LED emergency shutdown: {e}")
            
        # Cleanup resources
        try:
            self.resource_manager.__exit__(None, None, None)
        except Exception as e:
            self.logger.error(f"Error during resource cleanup: {e}")


# Global reliability manager instance
reliability_manager = ReliabilityManager()


@contextmanager
def managed_resources():
    """Context manager for automatic resource cleanup"""
    with reliability_manager.resource_manager as rm:
        yield rm


def get_reliability_manager() -> ReliabilityManager:
    """Get the global reliability manager instance"""
    return reliability_manager
