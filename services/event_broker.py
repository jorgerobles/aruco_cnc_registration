"""
EventBroker - Enhanced with class decorator for automatic injection
Eliminates the need to manually pass event_broker instances around
"""

from typing import Callable, Dict, List, Any, Optional, Type, Union
from functools import wraps
import threading
from enum import Enum, auto
import weakref


class EventPriority(Enum):
    """Event priority levels"""
    LOW = auto()
    NORMAL = auto()
    HIGH = auto()
    CRITICAL = auto()


class EventBroker:
    """
    General-purpose event broker for managing publish-subscribe patterns
    Supports typed events, priorities, and error handling
    """

    # Global registry for event brokers
    _instances: Dict[str, 'EventBroker'] = {}
    _default_broker: Optional['EventBroker'] = None

    def __init__(self, name: str = "default", enable_logging: bool = False):
        self.name = name
        self._subscribers: Dict[str, List[Dict[str, Any]]] = {}
        self._lock = threading.RLock()
        self._enable_logging = enable_logging
        self._logger: Optional[Callable[[str, str], None]] = None

        # Register this broker
        EventBroker._instances[name] = self
        if name == "default":
            EventBroker._default_broker = self

    @classmethod
    def get_broker(cls, name: str = "default") -> 'EventBroker':
        """Get or create a named event broker"""
        if name not in cls._instances:
            cls._instances[name] = EventBroker(name)
        return cls._instances[name]

    @classmethod
    def get_default(cls) -> 'EventBroker':
        """Get the default event broker"""
        if cls._default_broker is None:
            cls._default_broker = EventBroker("default")
        return cls._default_broker

    def set_logger(self, logger: Callable[[str, str], None]):
        """Set logger function for debugging"""
        self._logger = logger

    def _log(self, message: str, level: str = "info"):
        """Internal logging"""
        return
        # if self._enable_logging and self._logger:
        #     self._logger(f"EventBroker[{self.name}]: {message}", level)

    def subscribe(self, event_type: str, callback: Callable,
                  priority: EventPriority = EventPriority.NORMAL,
                  error_handler: Optional[Callable[[Exception], None]] = None) -> str:
        """
        Subscribe to an event type

        Args:
            event_type: Name of the event to subscribe to
            callback: Function to call when event is published
            priority: Priority level for callback execution order
            error_handler: Optional error handler for this specific callback

        Returns:
            Subscription ID for unsubscribing
        """
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []

            subscription_id = f"{event_type}_{id(callback)}_{len(self._subscribers[event_type])}"

            subscriber_info = {
                'callback': callback,
                'priority': priority,
                'error_handler': error_handler,
                'subscription_id': subscription_id
            }

            # Insert based on priority (higher priority first)
            subscribers = self._subscribers[event_type]
            insert_index = 0
            for i, sub in enumerate(subscribers):
                if sub['priority'].value <= priority.value:
                    insert_index = i
                    break
                insert_index = i + 1

            subscribers.insert(insert_index, subscriber_info)

            self._log(f"Subscribed to '{event_type}' with priority {priority.name}")
            return subscription_id

    def unsubscribe(self, event_type: str, subscription_id: str = None, callback: Callable = None) -> bool:
        """Unsubscribe from an event type"""
        with self._lock:
            if event_type not in self._subscribers:
                return False

            subscribers = self._subscribers[event_type]

            # Find and remove subscriber
            for i, sub in enumerate(subscribers):
                if (subscription_id and sub['subscription_id'] == subscription_id) or \
                   (callback and sub['callback'] == callback):
                    removed_sub = subscribers.pop(i)
                    self._log(f"Unsubscribed from '{event_type}'")
                    return True

            return False

    def unsubscribe_all(self, event_type: str = None):
        """Unsubscribe all callbacks from event type, or clear all events"""
        with self._lock:
            if event_type:
                if event_type in self._subscribers:
                    del self._subscribers[event_type]
                    self._log(f"Cleared all subscribers for '{event_type}'")
            else:
                self._subscribers.clear()
                self._log("Cleared all subscribers")

    def publish(self, event_type: str, *args, **kwargs) -> int:
        """Publish an event to all subscribers"""
        with self._lock:
            if event_type not in self._subscribers:
                self._log(f"No subscribers for event '{event_type}'")
                return 0

            subscribers = self._subscribers[event_type].copy()

        successful_calls = 0
        self._log(f"Publishing '{event_type}' to {len(subscribers)} subscribers")

        for subscriber in subscribers:
            try:
                subscriber['callback'](*args, **kwargs)
                successful_calls += 1
            except Exception as e:
                error_msg = f"Error in subscriber for '{event_type}': {e}"
                self._log(error_msg, "error")

                if subscriber['error_handler']:
                    try:
                        subscriber['error_handler'](e)
                    except Exception as handler_error:
                        self._log(f"Error in error handler: {handler_error}", "error")

        return successful_calls

    def has_subscribers(self, event_type: str) -> bool:
        """Check if event type has any subscribers"""
        with self._lock:
            return event_type in self._subscribers and len(self._subscribers[event_type]) > 0

    def get_subscriber_count(self, event_type: str) -> int:
        """Get number of subscribers for event type"""
        with self._lock:
            return len(self._subscribers.get(event_type, []))

    def list_event_types(self) -> List[str]:
        """Get list of all event types with subscribers"""
        with self._lock:
            return list(self._subscribers.keys())


def event_aware(broker_name: str = "default"):
    """
    Class decorator that automatically injects EventBroker functionality

    Usage:
        @event_aware()
        class MyClass:
            def __init__(self):
                # self._event_broker is automatically available
                self.emit('my.event', data)

        @event_aware("my_broker")
        class MyOtherClass:
            pass
    """
    def decorator(cls: Type) -> Type:
        # Store original __init__
        original_init = cls.__init__

        @wraps(original_init)
        def new_init(self, *args, **kwargs):
            # Get or create the named broker
            self._event_broker = EventBroker.get_broker(broker_name)
            self._subscriptions: List[tuple] = []

            # Call original __init__
            original_init(self, *args, **kwargs)

            # Auto-register event handlers
            self._auto_register_handlers()

        # Replace __init__
        cls.__init__ = new_init

        # Add event methods to class
        def emit(self, event_type: str, *args, **kwargs) -> int:
            """Emit an event"""
            return self._event_broker.publish(event_type, *args, **kwargs)

        def listen(self, event_type: str, callback: Callable,
                   priority: EventPriority = EventPriority.NORMAL,
                   error_handler: Optional[Callable[[Exception], None]] = None) -> str:
            """Subscribe to an event and track the subscription"""
            subscription_id = self._event_broker.subscribe(
                event_type, callback, priority, error_handler
            )
            self._subscriptions.append((event_type, subscription_id))
            return subscription_id

        def stop_listening(self, event_type: str, subscription_id: str = None, callback: Callable = None) -> bool:
            """Unsubscribe from an event"""
            success = self._event_broker.unsubscribe(event_type, subscription_id, callback)
            if success:
                self._subscriptions = [
                    (et, sid) for et, sid in self._subscriptions
                    if not (et == event_type and (sid == subscription_id or callback))
                ]
            return success

        def cleanup_subscriptions(self):
            """Clean up all subscriptions"""
            for event_type, subscription_id in self._subscriptions:
                self._event_broker.unsubscribe(event_type, subscription_id)
            self._subscriptions.clear()

        def has_listeners(self, event_type: str) -> bool:
            """Check if anyone is listening to this event type"""
            return self._event_broker.has_subscribers(event_type)

        def _auto_register_handlers(self):
            """Find and register all decorated event handler methods"""
            for attr_name in dir(self):
                attr = getattr(self, attr_name)
                if callable(attr) and hasattr(attr, '_event_type'):
                    self.listen(
                        attr._event_type,
                        attr,
                        attr._event_priority
                    )

        # Add methods to class
        cls.emit = emit
        cls.listen = listen
        cls.stop_listening = stop_listening
        cls.cleanup_subscriptions = cleanup_subscriptions
        cls.has_listeners = has_listeners
        cls._auto_register_handlers = _auto_register_handlers

        return cls

    return decorator


def event_handler(event_type: str, priority: EventPriority = EventPriority.NORMAL):
    """
    Decorator for automatically registering event handlers
    Usage: @event_handler('camera.connected')
    """
    def decorator(func):
        func._event_type = event_type
        func._event_priority = priority
        return func
    return decorator


# Legacy support - these classes are now optional but kept for backwards compatibility
class EventPublisher:
    """Legacy EventPublisher - use @event_aware decorator instead"""
    def __init__(self, event_broker: EventBroker = None):
        self._event_broker = event_broker or EventBroker.get_default()

    def set_event_broker(self, broker: EventBroker):
        self._event_broker = broker

    def emit(self, event_type: str, *args, **kwargs) -> int:
        return self._event_broker.publish(event_type, *args, **kwargs)

    def has_listeners(self, event_type: str) -> bool:
        return self._event_broker.has_subscribers(event_type)


class EventSubscriber:
    """Legacy EventSubscriber - use @event_aware decorator instead"""
    def __init__(self, event_broker: EventBroker = None):
        self._event_broker = event_broker or EventBroker.get_default()
        self._subscriptions: List[tuple] = []

    def set_event_broker(self, broker: EventBroker):
        self._event_broker = broker

    def listen(self, event_type: str, callback: Callable,
               priority: EventPriority = EventPriority.NORMAL,
               error_handler: Optional[Callable[[Exception], None]] = None) -> str:
        subscription_id = self._event_broker.subscribe(
            event_type, callback, priority, error_handler
        )
        self._subscriptions.append((event_type, subscription_id))
        return subscription_id

    def stop_listening(self, event_type: str, subscription_id: str = None, callback: Callable = None) -> bool:
        success = self._event_broker.unsubscribe(event_type, subscription_id, callback)
        if success:
            self._subscriptions = [
                (et, sid) for et, sid in self._subscriptions
                if not (et == event_type and (sid == subscription_id or callback))
            ]
        return success

    def cleanup_subscriptions(self):
        for event_type, subscription_id in self._subscriptions:
            self._event_broker.unsubscribe(event_type, subscription_id)
        self._subscriptions.clear()


class AutoEventSubscriber(EventSubscriber):
    """Legacy AutoEventSubscriber - use @event_aware decorator instead"""
    def __init__(self, event_broker: EventBroker = None):
        super().__init__(event_broker)
        self._auto_register_handlers()

    def _auto_register_handlers(self):
        for attr_name in dir(self):
            attr = getattr(self, attr_name)
            if callable(attr) and hasattr(attr, '_event_type'):
                self.listen(
                    attr._event_type,
                    attr,
                    attr._event_priority
                )

# Predefined event types - Updated to include DEBUG_INFO
class CameraEvents:
    CONNECTED = "camera.connected"
    DISCONNECTED = "camera.disconnected"
    FRAME_CAPTURED = "camera.frame_captured"
    ERROR = "camera.error"
    CALIBRATION_LOADED = "camera.calibration_loaded"


class GRBLEvents:
    CONNECTED = "grbl.connected"
    DISCONNECTED = "grbl.disconnected"
    POSITION_CHANGED = "grbl.position_changed"
    STATUS_CHANGED = "grbl.status_changed"
    ERROR = "grbl.error"
    COMMAND_SENT = "grbl.command_sent"
    RESPONSE_RECEIVED = "grbl.response_received"
    DEBUG_INFO = "grbl.debug_info"  # NEW: For GRBL internal debug messages


class RegistrationEvents:
    POINT_ADDED = "registration.point_added"
    POINT_REMOVED = "registration.point_removed"
    POINT_TRANSFORMED = "registration.point_transformed"
    BATCH_TRANSFORMED = "registration.batch_transformed"
    COMPUTED = "registration.computed"
    AUTO_COMPUTED = "registration.auto_computed"
    CLEARED = "registration.cleared"
    RESET = "registration.reset"
    SAVED = "registration.saved"
    LOADED = "registration.loaded"
    VALIDATION_PASSED = "registration.validation_passed"
    VALIDATION_FAILED = "registration.validation_failed"
    ERROR = "registration.error"
    DEBUG_INFO = "registration.debug_info"  # New event for debug information


class ApplicationEvents:
    STARTUP = "app.startup"
    SHUTDOWN = "app.shutdown"
    MODE_CHANGED = "app.mode_changed"
    ERROR = "app.error"