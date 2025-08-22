# store/store.py
"""
Main ApplicationStore implementation
Redux-like store with subscription and middleware support
"""

import threading
from typing import Callable, List, Optional

from .actions import Action
from .reducers import root_reducer
from .state import ApplicationState


class ApplicationStore:
    """
    Redux-like store for application state management
    Thread-safe with subscription support
    """

    def __init__(self, initial_state: Optional[ApplicationState] = None):
        self._state = initial_state or ApplicationState()
        self._subscribers: List[Callable[[ApplicationState], None]] = []
        self._middleware: List[Callable[[Action, ApplicationState], Optional[Action]]] = []
        self._lock = threading.RLock()
        self._action_history: List[Action] = []
        self._max_history = 100

    def get_state(self) -> ApplicationState:
        """Get current state (immutable copy)"""
        with self._lock:
            return self._state

    def dispatch(self, action: Action) -> None:
        """Dispatch action to update state"""
        with self._lock:
            # Apply middleware (can modify or block actions)
            processed_action = action
            for middleware in self._middleware:
                processed_action = middleware(processed_action, self._state)
                if processed_action is None:
                    return  # Action was blocked by middleware

            # Apply reducer to get new state
            new_state = root_reducer(self._state, processed_action)

            # Only update if state actually changed
            if new_state != self._state:
                self._state = new_state
                self._add_to_history(processed_action)
                self._notify_subscribers()

    def subscribe(self, callback: Callable[[ApplicationState], None]) -> Callable:
        """
        Subscribe to state changes
        Returns unsubscribe function
        """
        with self._lock:
            self._subscribers.append(callback)

        def unsubscribe():
            with self._lock:
                if callback in self._subscribers:
                    self._subscribers.remove(callback)

        return unsubscribe

    def add_middleware(self, middleware: Callable[[Action, ApplicationState], Optional[Action]]):
        """Add middleware function"""
        with self._lock:
            self._middleware.append(middleware)

    def get_action_history(self) -> List[Action]:
        """Get recent action history for debugging"""
        with self._lock:
            return self._action_history.copy()

    def _add_to_history(self, action: Action):
        """Add action to history with size limit"""
        self._action_history.append(action)
        if len(self._action_history) > self._max_history:
            self._action_history.pop(0)

    def _notify_subscribers(self):
        """Notify all subscribers of state change"""
        for callback in self._subscribers:
            try:
                callback(self._state)
            except Exception as e:
                # Log error but don't break other subscribers
                print(f"Error in store subscriber: {e}")


# Global store instance
_store_instance: Optional[ApplicationStore] = None


def get_store() -> ApplicationStore:
    """Get global store instance (singleton pattern)"""
    global _store_instance
    if _store_instance is None:
        _store_instance = ApplicationStore()
    return _store_instance


def initialize_store(initial_state: Optional[ApplicationState] = None) -> ApplicationStore:
    """Initialize global store with optional initial state"""
    global _store_instance
    _store_instance = ApplicationStore(initial_state)
    return _store_instance
