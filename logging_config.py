"""
LiveSectional Logging Configuration

Provides production-grade logging with rotation, rate limiting, and SD card protection
to replace the basic log.py implementation.
"""

import logging
import logging.handlers
import os
import sys
import time
import threading
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import queue
import json


class RateLimitFilter(logging.Filter):
    """Filter to prevent log flooding with per-message counters"""
    
    def __init__(self, max_messages_per_second: int = 10):
        super().__init__()
        self.max_messages_per_second = max_messages_per_second
        self.message_times = {}  # defaultdict(deque) per message key
        self.lock = threading.Lock()
        
    def filter(self, record):
        """Filter log records based on per-message rate limiting"""
        with self.lock:
            current_time = time.time()
            message_key = f"{record.levelname}:{record.getMessage()}"
            
            # Initialize message key if not exists
            if message_key not in self.message_times:
                self.message_times[message_key] = []
            
            # Clean old timestamps for this message (older than 1 second)
            cutoff_time = current_time - 1.0
            self.message_times[message_key] = [
                t for t in self.message_times[message_key] 
                if t > cutoff_time
            ]
            
            # Check if we're under the rate limit for this specific message
            if len(self.message_times[message_key]) < self.max_messages_per_second:
                self.message_times[message_key].append(current_time)
                return True
            else:
                return False


class ContextFilter(logging.Filter):
    """Filter to add context information to log records"""
    
    def __init__(self, context_func: Optional[callable] = None):
        super().__init__()
        self.context_func = context_func or self._default_context
        
    def _default_context(self) -> Dict[str, Any]:
        """Default context information"""
        return {
            'timestamp': datetime.now().isoformat(),
            'process_id': os.getpid(),
            'thread_id': threading.get_ident()
        }
        
    def filter(self, record):
        """Add context to log record"""
        try:
            context = self.context_func()
            for key, value in context.items():
                setattr(record, key, value)
        except Exception:
            pass  # Don't let context errors break logging
        return True


class AsyncLogHandler(logging.Handler):
    """Asynchronous log handler to prevent blocking main loops"""
    
    def __init__(self, target_handler: logging.Handler, max_queue_size: int = 1000):
        super().__init__()
        self.target_handler = target_handler
        self.queue = queue.Queue(maxsize=max_queue_size)
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.shutdown = False
        self.thread.start()
        
    def _worker(self):
        """Worker thread for async logging"""
        while not self.shutdown:
            try:
                record = self.queue.get(timeout=1.0)
                if record is None:  # Shutdown signal
                    break
                self.target_handler.emit(record)
                self.queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error in async log handler: {e}", file=sys.stderr)
                
    def emit(self, record):
        """Emit log record asynchronously"""
        try:
            self.queue.put_nowait(record)
        except queue.Full:
            # Drop message if queue is full
            pass
            
    def close(self):
        """Close the async handler"""
        self.shutdown = True
        self.queue.put(None)  # Signal shutdown
        self.thread.join(timeout=5.0)


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging"""
    
    def __init__(self, include_context: bool = True):
        super().__init__()
        self.include_context = include_context
        
    def format(self, record):
        """Format log record as JSON"""
        log_entry = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        if self.include_context:
            # Add context fields
            for key in ['airport_code', 'cycle_number', 'timing_info', 'process_id', 'thread_id']:
                if hasattr(record, key):
                    log_entry[key] = getattr(record, key)
                    
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
            
        return json.dumps(log_entry, default=str)


class LoggingConfig:
    """Centralized logging configuration manager"""
    
    def __init__(self):
        self.loggers = {}
        self.handlers = {}
        self.handlers_raw = {}  # Store raw handlers before async wrapping
        self.initialized = False
        self.log_level = os.getenv('LIVESECTIONAL_LOG_LEVEL', 'INFO').upper()
        self.debug_timeout = None
        self.debug_start_time = None
        
    def setup_logging(self, 
                     log_dir: str = "/var/log/livesectional",
                     debug_log_dir: str = "/run/livesectional",
                     max_log_size: int = 5 * 1024 * 1024,  # 5MB
                     backup_count: int = 10,
                     enable_async: bool = True):
        """Setup comprehensive logging configuration"""
        
        if self.initialized:
            return
            
        # Create log directories
        os.makedirs(log_dir, exist_ok=True)
        os.makedirs(debug_log_dir, exist_ok=True)
        
        # Setup root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, self.log_level))
        
        # Clear existing handlers
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
            
        # Main application log (persistent)
        main_log_file = os.path.join(log_dir, "livesectional.log")
        main_handler = logging.handlers.RotatingFileHandler(
            main_log_file,
            maxBytes=max_log_size,
            backupCount=backup_count,
            encoding='utf-8'
        )
        main_handler.setLevel(logging.INFO)
        main_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        main_handler.setFormatter(main_formatter)
        main_handler.addFilter(RateLimitFilter(max_messages_per_second=10))
        
        # Debug log (tmpfs - high volume)
        debug_log_file = os.path.join(debug_log_dir, "debug.log")
        debug_handler = logging.handlers.RotatingFileHandler(
            debug_log_file,
            maxBytes=max_log_size,
            backupCount=5,  # Fewer backups for tmpfs
            encoding='utf-8'
        )
        debug_handler.setLevel(logging.DEBUG)
        debug_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        )
        debug_handler.setFormatter(debug_formatter)
        debug_handler.addFilter(RateLimitFilter(max_messages_per_second=50))
        
        # Error log (critical errors only)
        error_log_file = os.path.join(log_dir, "error.log")
        error_handler = logging.handlers.RotatingFileHandler(
            error_log_file,
            maxBytes=max_log_size,
            backupCount=20,  # Keep more error logs
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_formatter = StructuredFormatter(include_context=True)
        error_handler.setFormatter(error_formatter)
        
        # Performance metrics log
        perf_log_file = os.path.join(debug_log_dir, "performance.log")
        perf_handler = logging.handlers.RotatingFileHandler(
            perf_log_file,
            maxBytes=max_log_size,
            backupCount=5,
            encoding='utf-8'
        )
        perf_handler.setLevel(logging.INFO)
        perf_formatter = StructuredFormatter(include_context=True)
        perf_handler.setFormatter(perf_formatter)
        
        # Console handler for development
        if os.getenv('LIVESECTIONAL_CONSOLE_LOGGING', 'false').lower() == 'true':
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.INFO)
            console_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            console_handler.setFormatter(console_formatter)
            root_logger.addHandler(console_handler)
            
        # Store raw handlers before async wrapping
        self.handlers_raw = {
            'main': main_handler,
            'debug': debug_handler,
            'error': error_handler,
            'performance': perf_handler
        }
        
        # Wrap handlers with async if enabled
        if enable_async:
            main_handler = AsyncLogHandler(main_handler)
            debug_handler = AsyncLogHandler(debug_handler)
            error_handler = AsyncLogHandler(error_handler)
            perf_handler = AsyncLogHandler(perf_handler)
            
        # Add handlers to root logger
        root_logger.addHandler(main_handler)
        root_logger.addHandler(debug_handler)
        root_logger.addHandler(error_handler)
        root_logger.addHandler(perf_handler)
        
        # Store handlers for later reference
        self.handlers = {
            'main': main_handler,
            'debug': debug_handler,
            'error': error_handler,
            'performance': perf_handler
        }
        
        # Setup component-specific loggers
        self._setup_component_loggers()
        
        self.initialized = True
        
        # Log startup
        logger = logging.getLogger('logging_config')
        logger.info("Logging system initialized")
        logger.info(f"Log level: {self.log_level}")
        logger.info(f"Main log: {main_log_file}")
        logger.info(f"Debug log: {debug_log_file}")
        logger.info(f"Error log: {error_log_file}")
        
    def _setup_component_loggers(self):
        """Setup loggers for specific components"""
        
        # Main service logger
        main_logger = logging.getLogger('main')
        main_logger.setLevel(logging.INFO)
        
        # LED control logger
        led_logger = logging.getLogger('led')
        led_logger.setLevel(logging.INFO)
        
        # Network operations logger
        network_logger = logging.getLogger('network')
        network_logger.setLevel(logging.INFO)
        
        # Health monitoring logger
        health_logger = logging.getLogger('health')
        health_logger.setLevel(logging.INFO)
        
        # Animation logger
        animation_logger = logging.getLogger('animation')
        animation_logger.setLevel(logging.DEBUG)
        
        # Performance logger
        performance_logger = logging.getLogger('performance')
        performance_logger.setLevel(logging.INFO)
        
        # Store loggers
        self.loggers = {
            'main': main_logger,
            'led': led_logger,
            'network': network_logger,
            'health': health_logger,
            'animation': animation_logger,
            'performance': performance_logger
        }
        
    def get_logger(self, name: str) -> logging.Logger:
        """Get a component logger"""
        if not self.initialized:
            self.setup_logging()
        return self.loggers.get(name, logging.getLogger(name))
        
    def set_debug_mode(self, timeout_minutes: int = 60):
        """Enable debug mode with automatic timeout"""
        if not self.initialized:
            self.setup_logging()
            
        self.debug_start_time = time.time()
        self.debug_timeout = timeout_minutes * 60
        
        # Set all loggers to DEBUG
        for logger in self.loggers.values():
            logger.setLevel(logging.DEBUG)
            
        # Log debug mode activation
        logger = logging.getLogger('logging_config')
        logger.info(f"Debug mode enabled for {timeout_minutes} minutes")
        
    def check_debug_timeout(self):
        """Check if debug mode should timeout"""
        if self.debug_timeout and self.debug_start_time:
            if time.time() - self.debug_start_time > self.debug_timeout:
                self._disable_debug_mode()
                
    def _disable_debug_mode(self):
        """Disable debug mode and revert to normal logging"""
        for logger in self.loggers.values():
            logger.setLevel(logging.INFO)
            
        self.debug_timeout = None
        self.debug_start_time = None
        
        logger = logging.getLogger('logging_config')
        logger.info("Debug mode automatically disabled")
        
    def log_performance(self, operation: str, duration: float, **kwargs):
        """Log performance metrics"""
        perf_logger = self.get_logger('performance')
        perf_logger.info(f"Performance: {operation}", extra={
            'operation': operation,
            'duration_ms': duration * 1000,
            **kwargs
        })
        
    def log_health_metrics(self, metrics: Dict[str, Any]):
        """Log health monitoring metrics"""
        health_logger = self.get_logger('health')
        health_logger.info("Health metrics", extra=metrics)
        
    def rotate_logs(self):
        """Manually rotate all log files"""
        if not self.initialized:
            return
            
        logger = logging.getLogger('logging_config')
        logger.info("Manual log rotation requested")
        
        for name, handler in self.handlers.items():
            try:
                # Use raw handler for rotation if available
                raw_handler = self.handlers_raw.get(name)
                if raw_handler and hasattr(raw_handler, 'doRollover'):
                    raw_handler.doRollover()
                elif hasattr(handler, 'target_handler') and hasattr(handler.target_handler, 'doRollover'):
                    # AsyncLogHandler case - call on target handler
                    handler.target_handler.doRollover()
                elif hasattr(handler, 'doRollover'):
                    handler.doRollover()
            except Exception as e:
                logger.error(f"Error rotating log {name}: {e}")
                    
    def get_log_stats(self) -> Dict[str, Any]:
        """Get logging statistics"""
        stats = {
            'initialized': self.initialized,
            'log_level': self.log_level,
            'debug_mode': self.debug_timeout is not None,
            'handlers': {}
        }
        
        for name, handler in self.handlers.items():
            try:
                # Get file path from raw handler or AsyncLogHandler target
                file_path = None
                if hasattr(handler, 'target_handler') and hasattr(handler.target_handler, 'stream'):
                    # AsyncLogHandler case
                    file_path = handler.target_handler.stream.name
                elif hasattr(handler, 'stream') and hasattr(handler.stream, 'name'):
                    # Regular handler case
                    file_path = handler.stream.name
                
                if file_path:
                    file_size = os.path.getsize(file_path)
                    stats['handlers'][name] = {
                        'file': file_path,
                        'size_bytes': file_size,
                        'size_mb': file_size / 1024 / 1024
                    }
                else:
                    stats['handlers'][name] = {'file': 'unknown', 'size_bytes': 0}
            except:
                stats['handlers'][name] = {'file': 'unknown', 'size_bytes': 0}
                    
        return stats


# Global logging configuration instance
_logging_config = LoggingConfig()


def setup_logging(**kwargs):
    """Setup logging configuration"""
    _logging_config.setup_logging(**kwargs)


def get_logger(name: str) -> logging.Logger:
    """Get a component logger"""
    return _logging_config.get_logger(name)


def set_debug_mode(timeout_minutes: int = 60):
    """Enable debug mode with timeout"""
    _logging_config.set_debug_mode(timeout_minutes)


def log_performance(operation: str, duration: float, **kwargs):
    """Log performance metrics"""
    _logging_config.log_performance(operation, duration, **kwargs)


def log_health_metrics(metrics: Dict[str, Any]):
    """Log health monitoring metrics"""
    _logging_config.log_health_metrics(metrics)


def rotate_logs():
    """Manually rotate log files"""
    _logging_config.rotate_logs()


def get_log_stats() -> Dict[str, Any]:
    """Get logging statistics"""
    return _logging_config.get_log_stats()


# Context manager for logging context
@contextmanager
def logging_context(**context):
    """Context manager for adding context to log messages"""
    old_factory = logging.getLogRecordFactory()
    
    def record_factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)
        for key, value in context.items():
            setattr(record, key, value)
        return record
        
    logging.setLogRecordFactory(record_factory)
    try:
        yield
    finally:
        logging.setLogRecordFactory(old_factory)
