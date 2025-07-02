"""
Logging capabilities decorator for adding consistent logging functionality to any class
Provides flexible logging with multiple backends and automatic method call tracking
"""

import functools
import inspect
import time
from typing import Callable, Optional, Any, Dict, List
from enum import Enum


class LogLevel(Enum):
    """Standard logging levels"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class LoggingConfig:
    """Configuration for logging behavior"""

    def __init__(self):
        self.auto_log_methods: bool = False  # Automatically log method calls
        self.log_method_args: bool = False  # Include method arguments in logs
        self.log_method_timing: bool = False  # Include method execution time
        self.log_prefix: str = ""  # Custom prefix for all logs
        self.min_log_level: LogLevel = LogLevel.DEBUG  # Minimum level to log
        self.exclude_methods: List[str] = ['log', '__init__', '__str__', '__repr__']


def with_logging(
        logger: Optional[Callable] = None,
        prefix: str = "",
        auto_log_methods: bool = False,
        log_method_args: bool = False,
        log_method_timing: bool = False,
        exclude_methods: Optional[List[str]] = None
):
    """
    Decorator to add logging capabilities to a class.

    Args:
        logger: Optional external logger function
        prefix: Prefix for all log messages
        auto_log_methods: Automatically log all method calls
        log_method_args: Include arguments in method call logs
        log_method_timing: Include execution time in method logs
        exclude_methods: Methods to exclude from auto-logging

    Usage:
        @with_logging(prefix="MyClass", auto_log_methods=True)
        class MyClass:
            pass
    """

    def decorator(cls):
        # Store original __init__
        original_init = cls.__init__

        # Create logging configuration
        config = LoggingConfig()
        config.auto_log_methods = auto_log_methods
        config.log_method_args = log_method_args
        config.log_method_timing = log_method_timing
        config.log_prefix = prefix or cls.__name__
        if exclude_methods:
            config.exclude_methods.extend(exclude_methods)

        def enhanced_init(self, *args, **kwargs):
            # Initialize logging attributes
            self._logger = logger
            self._logging_config = config
            self._log_history: List[Dict] = []

            # Call original __init__
            original_init(self, *args, **kwargs)

            # Auto-detect logger from constructor args if not provided
            if not self._logger:
                self._auto_detect_logger(args, kwargs)

            # Log initialization
            self.log(f"{config.log_prefix} initialized", LogLevel.INFO)

        # Replace __init__
        cls.__init__ = enhanced_init

        # Add logging methods to class
        cls.log = _create_log_method()
        cls.set_logger = _create_set_logger_method()
        cls.get_log_history = _create_get_log_history_method()
        cls.clear_log_history = _create_clear_log_history_method()
        cls.log_debug = lambda self, msg: self.log(msg, LogLevel.DEBUG)
        cls.log_info = lambda self, msg: self.log(msg, LogLevel.INFO)
        cls.log_warning = lambda self, msg: self.log(msg, LogLevel.WARNING)
        cls.log_error = lambda self, msg: self.log(msg, LogLevel.ERROR)
        cls.log_critical = lambda self, msg: self.log(msg, LogLevel.CRITICAL)
        cls._auto_detect_logger = _create_auto_detect_logger_method()

        # Wrap methods for auto-logging if enabled
        if auto_log_methods:
            _wrap_methods_for_logging(cls, config)

        return cls

    return decorator


def _create_log_method():
    """Create the main log method"""

    def log(self, message: str, level: LogLevel = LogLevel.INFO, category: str = "general"):
        """
        Log a message with specified level and category

        Args:
            message: Message to log
            level: Log level (LogLevel enum)
            category: Category for organizing logs
        """
        if not isinstance(level, LogLevel):
            # Convert string to LogLevel if needed
            try:
                level = LogLevel(level.lower())
            except ValueError:
                level = LogLevel.INFO

        # Check minimum log level
        if hasattr(self, '_logging_config'):
            level_priority = {
                LogLevel.DEBUG: 0,
                LogLevel.INFO: 1,
                LogLevel.WARNING: 2,
                LogLevel.ERROR: 3,
                LogLevel.CRITICAL: 4
            }
            if level_priority[level] < level_priority[self._logging_config.min_log_level]:
                return

        # Format message with prefix
        prefix = getattr(self._logging_config, 'log_prefix', self.__class__.__name__)
        formatted_message = f"{prefix}: {message}"

        # Create log entry
        log_entry = {
            'timestamp': time.time(),
            'level': level.value,
            'category': category,
            'message': message,
            'formatted_message': formatted_message,
            'class': self.__class__.__name__
        }

        # Store in history
        if hasattr(self, '_log_history'):
            self._log_history.append(log_entry)
            # Keep only last 1000 entries to prevent memory issues
            if len(self._log_history) > 1000:
                self._log_history = self._log_history[-1000:]

        # Send to external logger if available
        if hasattr(self, '_logger') and self._logger:
            try:
                self._logger(formatted_message, level.value)
            except Exception as e:
                # Fallback to print if external logger fails
                print(f"[Logger Error] {e}")
                print(f"[{level.value.upper()}] {formatted_message}")
        else:
            # Fallback to print
            print(f"[{level.value.upper()}] {formatted_message}")

    return log


def _create_set_logger_method():
    """Create set_logger method"""

    def set_logger(self, logger: Callable):
        """Set or update the logger function"""
        self._logger = logger
        self.log(f"Logger updated", LogLevel.DEBUG)

    return set_logger


def _create_get_log_history_method():
    """Create get_log_history method"""

    def get_log_history(self, level: Optional[LogLevel] = None, category: Optional[str] = None,
                        limit: Optional[int] = None):
        """
        Get log history with optional filtering

        Args:
            level: Filter by log level
            category: Filter by category
            limit: Maximum number of entries to return (most recent first)
        """
        if not hasattr(self, '_log_history'):
            return []

        history = self._log_history.copy()

        # Apply filters
        if level:
            history = [entry for entry in history if entry['level'] == level.value]

        if category:
            history = [entry for entry in history if entry['category'] == category]

        # Apply limit (most recent first)
        if limit:
            history = history[-limit:]

        return history

    return get_log_history


def _create_clear_log_history_method():
    """Create clear_log_history method"""

    def clear_log_history(self):
        """Clear the log history"""
        if hasattr(self, '_log_history'):
            self._log_history.clear()
            self.log("Log history cleared", LogLevel.DEBUG)

    return clear_log_history


def _create_auto_detect_logger_method():
    """Create auto-detect logger method"""

    def _auto_detect_logger(self, args, kwargs):
        """Try to auto-detect logger from constructor arguments"""
        # Look for common logger parameter names
        logger_names = ['logger', 'log_func', 'log_function', 'log_callback']

        # Check kwargs first
        for name in logger_names:
            if name in kwargs and callable(kwargs[name]):
                self._logger = kwargs[name]
                return

        # Check if any positional args are callable (might be logger)
        for arg in args:
            if callable(arg) and hasattr(arg, '__name__'):
                # Simple heuristic: if callable name contains 'log', assume it's a logger
                if 'log' in arg.__name__.lower():
                    self._logger = arg
                    return

    return _auto_detect_logger


def _wrap_methods_for_logging(cls, config: LoggingConfig):
    """Wrap class methods for automatic logging"""
    for attr_name in dir(cls):
        if attr_name.startswith('_') or attr_name in config.exclude_methods:
            continue

        attr = getattr(cls, attr_name)
        if inspect.isfunction(attr):
            # Wrap the method
            wrapped_method = _create_method_wrapper(attr_name, attr, config)
            setattr(cls, attr_name, wrapped_method)


def _create_method_wrapper(method_name: str, original_method: Callable, config: LoggingConfig):
    """Create a wrapper for automatic method logging"""

    @functools.wraps(original_method)
    def wrapper(self, *args, **kwargs):
        start_time = time.time() if config.log_method_timing else None

        # Prepare log message
        msg_parts = [f"→ {method_name}()"]

        if config.log_method_args and (args or kwargs):
            arg_strs = []
            if args:
                arg_strs.extend([str(arg)[:50] for arg in args])  # Limit arg length
            if kwargs:
                arg_strs.extend([f"{k}={str(v)[:50]}" for k, v in kwargs.items()])
            msg_parts.append(f"({', '.join(arg_strs)})")

        # Log method entry
        self.log(" ".join(msg_parts), LogLevel.DEBUG, "method_call")

        try:
            # Call original method
            result = original_method(self, *args, **kwargs)

            # Log successful completion
            completion_msg = f"✓ {method_name}()"
            if config.log_method_timing and start_time:
                duration = time.time() - start_time
                completion_msg += f" [{duration:.3f}s]"

            self.log(completion_msg, LogLevel.DEBUG, "method_call")

            return result

        except Exception as e:
            # Log method failure
            error_msg = f"✗ {method_name}() failed: {str(e)}"
            if config.log_method_timing and start_time:
                duration = time.time() - start_time
                error_msg += f" [{duration:.3f}s]"

            self.log(error_msg, LogLevel.ERROR, "method_call")
            raise  # Re-raise the exception

    return wrapper


# Convenience decorators for common use cases
def simple_logging(logger: Optional[Callable] = None, prefix: str = ""):
    """Simple logging decorator - just adds basic log capability"""
    return with_logging(logger=logger, prefix=prefix)


def debug_logging(logger: Optional[Callable] = None, prefix: str = ""):
    """Debug logging decorator - logs all method calls with timing"""
    return with_logging(
        logger=logger,
        prefix=prefix,
        auto_log_methods=True,
        log_method_timing=True,
        log_method_args=True
    )


def method_tracing(logger: Optional[Callable] = None, prefix: str = ""):
    """Method tracing decorator - logs method entry/exit without args"""
    return with_logging(
        logger=logger,
        prefix=prefix,
        auto_log_methods=True,
        log_method_timing=True,
        log_method_args=False
    )