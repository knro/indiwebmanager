#!/usr/bin/env python

import logging
import asyncio
from typing import Dict, Set
from fastapi import WebSocket
from collections import defaultdict


class WebSocketManager:
    """
    Manages WebSocket connections for INDI device updates.
    Bridges INDI client callbacks to WebSocket clients.
    """

    def __init__(self):
        # Dictionary of device_name -> set of WebSocket connections
        self.connections: Dict[str, Set[WebSocket]] = defaultdict(set)
        # Lock for thread-safe operations
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, device_name: str):
        """Register a new WebSocket connection for a device"""
        await websocket.accept()
        async with self._lock:
            self.connections[device_name].add(websocket)
        logging.info(f"WebSocket connected for device: {device_name} (total connections: {len(self.connections[device_name])})")

    async def disconnect(self, websocket: WebSocket, device_name: str):
        """Remove a WebSocket connection for a device"""
        async with self._lock:
            self.connections[device_name].discard(websocket)
        logging.info(f"WebSocket disconnected for device: {device_name} (remaining connections: {len(self.connections[device_name])})")

    async def send_event(self, device_name: str, event_type: str, data: dict):
        """
        Send an event to all WebSocket clients listening to a specific device.

        Args:
            device_name: Name of the device
            event_type: Type of event (property_updated, property_defined, message, etc.)
            data: Event data to send
        """
        if device_name not in self.connections or not self.connections[device_name]:
            return

        message = {
            "event": event_type,
            "device": device_name,
            "data": data
        }

        # Create a copy of connections to avoid modification during iteration
        async with self._lock:
            connections = list(self.connections[device_name])

        # Send to all connected clients
        disconnected = []
        for websocket in connections:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logging.error(f"Error sending to WebSocket for {device_name}: {e}")
                disconnected.append(websocket)

        # Clean up disconnected clients
        if disconnected:
            async with self._lock:
                for websocket in disconnected:
                    self.connections[device_name].discard(websocket)

    def get_connection_count(self, device_name: str = None) -> int:
        """Get the number of active connections for a device or all devices"""
        if device_name:
            return len(self.connections.get(device_name, set()))
        return sum(len(conns) for conns in self.connections.values())


# Global WebSocket manager instance
websocket_manager = WebSocketManager()


def get_websocket_manager() -> WebSocketManager:
    """Get the global WebSocket manager instance"""
    return websocket_manager


def create_indi_event_listener(indi_client, event_loop):
    """
    Create and register an INDI event listener that forwards events to WebSocket clients.

    Args:
        indi_client: The INDI client instance
        event_loop: The asyncio event loop to use for async operations

    Returns:
        The listener function (for potential removal later)
    """
    manager = get_websocket_manager()

    def indi_event_listener(event_type: str, device_name: str, data: dict):
        """
        Callback for INDI client events. Runs in INDI client thread.
        Forwards events to WebSocket clients in the main event loop.
        """
        if not data:
            return

        # Schedule the coroutine in the main event loop (thread-safe)
        asyncio.run_coroutine_threadsafe(
            manager.send_event(device_name, event_type, data),
            event_loop
        )

    # Register the listener with the INDI client
    indi_client.add_listener(indi_event_listener)

    logging.info("INDI event listener registered with WebSocket manager")

    return indi_event_listener
