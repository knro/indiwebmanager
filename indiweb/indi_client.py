#!/usr/bin/env python

import time
import logging
import threading
from collections import defaultdict

try:
    import PyIndi
except ImportError:
    print("PyIndi module not found. Please install pyindi-client.")
    raise


class INDIClient(PyIndi.BaseClient):
    """
    An INDI client for connecting to an INDI server and managing device properties.
    Based on the INDI protocol: https://indilib.org/develop/developer-manual/101-standard-properties.html
    """

    def __init__(self, host='localhost', port=7624):
        super(INDIClient, self).__init__()
        self.host = host
        self.port = port
        self.connected = False
        self.properties = defaultdict(dict)
        self.auto_connect_devices = True
        self.listeners = []
        self.connection_lock = threading.Lock()

    def connect(self):
        """Connect to the INDI server"""
        try:
            with self.connection_lock:
                self.setServer(self.host, self.port)
                success = self.connectServer()
                if success:
                    # Don't set connected=True here, wait for serverConnected() callback
                    logging.info(f"Attempting to connect to INDI server at {self.host}:{self.port}")
                    # Wait a bit for connection to establish and initial properties to load
                    time.sleep(2)
                    return self.connected  # Return actual connection status from callback
                return False
        except Exception as e:
            logging.error(f"Failed to connect to INDI server: {e}")
            self.connected = False
            return False

    def disconnect(self):
        """Disconnect from the INDI server"""
        with self.connection_lock:
            if self.connected:
                self.disconnectServer()
                self.connected = False
                logging.info("Disconnected from INDI server")

    # PyIndi callback methods
    def newDevice(self, device):
        """Called when a new device is created"""
        device_name = device.getDeviceName()
        logging.debug(f"New device: {device_name}")
        self._notify_listeners('device_added', device_name, None)

    def removeDevice(self, device):
        """Called when a device is removed"""
        device_name = device.getDeviceName()
        if device_name in self.properties:
            del self.properties[device_name]
        logging.debug(f"Removed device: {device_name}")
        self._notify_listeners('device_deleted', device_name, None)

    def newProperty(self, prop):
        """Called when a new property is created"""
        device_name = prop.getDeviceName()
        prop_name = prop.getName()

        property_data = self._convert_property_to_dict(prop)

        if device_name not in self.properties:
            self.properties[device_name] = {}

        self.properties[device_name][prop_name] = property_data

        # Auto-connect device if it has a CONNECTION property
        if self.auto_connect_devices and prop_name == 'CONNECTION':
            self._auto_connect_device(device_name)

        # Notify listeners
        self._notify_listeners('property_defined', device_name, property_data)

    def updateProperty(self, prop):
        """Called when a property is updated"""
        device_name = prop.getDeviceName()
        prop_name = prop.getName()

        property_data = self._convert_property_to_dict(prop)

        if device_name in self.properties and prop_name in self.properties[device_name]:
            # Update the property data
            self.properties[device_name][prop_name] = property_data

            # Notify listeners
            self._notify_listeners('property_updated', device_name, property_data)

    def removeProperty(self, prop):
        """Called when a property is removed"""
        device_name = prop.getDeviceName()
        prop_name = prop.getName()

        if device_name in self.properties and prop_name in self.properties[device_name]:
            del self.properties[device_name][prop_name]
            self._notify_listeners('property_deleted', device_name, {'name': prop_name})

    def newMessage(self, device, message_id):
        """Called when a new message arrives"""
        device_name = device.getDeviceName() if device else "Server"
        message_text = device.messageQueue(message_id) if device else ""

        self._notify_listeners('message', device_name, {
            'message': message_text,
            'timestamp': str(time.time())
        })

    def serverConnected(self):
        """Called when server connects"""
        self.connected = True
        logging.info(f"Server connected ({self.getHost()}:{self.getPort()})")

    def serverDisconnected(self, exit_code):
        """Called when server disconnects"""
        self.connected = False
        logging.info(f"Server disconnected (exit code = {exit_code})")

    def _convert_property_to_dict(self, prop):
        """Convert a PyIndi property to dictionary format"""
        device_name = prop.getDeviceName()
        prop_name = prop.getName()
        prop_label = prop.getLabel()
        prop_group = prop.getGroupName()
        prop_state = prop.getStateAsString().lower()
        # Convert permission number to string
        perm_num = prop.getPermission()
        if perm_num == PyIndi.IP_RO:
            prop_perm = 'ro'
        elif perm_num == PyIndi.IP_WO:
            prop_perm = 'wo'
        elif perm_num == PyIndi.IP_RW:
            prop_perm = 'rw'
        else:
            prop_perm = 'rw'  # default
        prop_type_str = prop.getTypeAsString().lower()

        # Map PyIndi property types to our format
        # PyIndi returns "INDI_Text", "INDI_Number", etc.
        type_mapping = {
            'indi_text': 'text',
            'indi_number': 'number',
            'indi_switch': 'switch',
            'indi_light': 'light',
            'indi_blob': 'blob'
        }
        prop_type = type_mapping.get(prop_type_str, prop_type_str)

        elements = {}
        switch_rule = None  # Initialize for switch properties

        if prop.getType() == PyIndi.INDI_TEXT:
            text_prop = PyIndi.PropertyText(prop)
            for widget in text_prop:
                elements[widget.name] = {
                    'name': widget.name,
                    'label': widget.label,
                    'value': widget.text
                }

        elif prop.getType() == PyIndi.INDI_NUMBER:
            number_prop = PyIndi.PropertyNumber(prop)
            for widget in number_prop:
                element = {
                    'name': widget.name,
                    'label': widget.label,
                    'value': str(widget.value),
                    'min': str(widget.min) if widget.min is not None else None,
                    'max': str(widget.max) if widget.max is not None else None,
                    'step': str(widget.step) if widget.step is not None else None,
                    'format': widget.format if widget.format else None
                }
                elements[widget.name] = element

        elif prop.getType() == PyIndi.INDI_SWITCH:
            switch_prop = PyIndi.PropertySwitch(prop)
            # Get the rule from the switch property - this will be used later in property_data
            switch_rule = switch_prop.getRule() if hasattr(switch_prop, 'getRule') else None
            if switch_rule is not None:
                # Convert PyIndi rule constants to strings
                if switch_rule == PyIndi.ISR_1OFMANY:
                    switch_rule = 'OneOfMany'
                elif switch_rule == PyIndi.ISR_ATMOST1:
                    switch_rule = 'AtMostOne'
                elif switch_rule == PyIndi.ISR_NOFMANY:
                    switch_rule = 'AnyOfMany'
                else:
                    switch_rule = 'OneOfMany'  # default

            for widget in switch_prop:
                elements[widget.name] = {
                    'name': widget.name,
                    'label': widget.label,
                    'value': 'On' if widget.s == PyIndi.ISS_ON else 'Off'
                }

        elif prop.getType() == PyIndi.INDI_LIGHT:
            light_prop = PyIndi.PropertyLight(prop)
            for widget in light_prop:
                # Convert light state to string
                state_str = 'Idle'
                if widget.s == PyIndi.IPS_IDLE:
                    state_str = 'Idle'
                elif widget.s == PyIndi.IPS_OK:
                    state_str = 'Ok'
                elif widget.s == PyIndi.IPS_BUSY:
                    state_str = 'Busy'
                elif widget.s == PyIndi.IPS_ALERT:
                    state_str = 'Alert'

                elements[widget.name] = {
                    'name': widget.name,
                    'label': widget.label,
                    'value': state_str
                }

        elif prop.getType() == PyIndi.INDI_BLOB:
            blob_prop = PyIndi.PropertyBlob(prop)
            for widget in blob_prop:
                size = getattr(widget, 'size', 0) if hasattr(widget, 'size') else 0
                elements[widget.name] = {
                    'name': widget.name,
                    'label': widget.label,
                    'value': f'<blob {size} bytes>'
                }

        # Set the rule based on property type
        rule_value = None
        if prop.getType() == PyIndi.INDI_SWITCH:
            rule_value = switch_rule

        property_data = {
            'name': prop_name,
            'label': prop_label,
            'group': prop_group,
            'type': prop_type,
            'state': prop_state,
            'perm': prop_perm.lower(),
            'rule': rule_value,
            'elements': elements,
            'device': device_name
        }

        # Apply formatting to number properties
        property_data = self._apply_formatting_to_property(property_data)

        return property_data





    def _notify_listeners(self, event_type, device, data):
        """Notify all registered listeners of an event"""
        for listener in self.listeners:
            try:
                listener(event_type, device, data)
            except Exception as e:
                logging.error(f"Error in listener callback: {e}")

    def add_listener(self, callback):
        """Add a listener for INDI events"""
        self.listeners.append(callback)

    def remove_listener(self, callback):
        """Remove a listener"""
        if callback in self.listeners:
            self.listeners.remove(callback)

    def get_devices(self):
        """Get list of available devices"""
        if self.connected:
            pyindi_devices = self.getDevices()
            return [device.getDeviceName() for device in pyindi_devices]
        return list(self.properties.keys())

    def get_device_properties(self, device_name):
        """Get all properties for a specific device"""
        return self.properties.get(device_name, {})

    def get_property(self, device_name, property_name):
        """Get a specific property"""
        device_props = self.properties.get(device_name, {})
        return device_props.get(property_name)

    def wait_for_device(self, device_name, timeout=5):
        """Wait for a device to become available"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.connected:
                device = self.getDevice(device_name)
                if device:
                    return True
            elif device_name in self.properties:
                return True
            time.sleep(0.1)
        return False

    def set_property(self, device_name, property_name, elements):
        """
        Set property values and return detailed result information.

        Args:
            device_name (str): Name of the device
            property_name (str): Name of the property
            elements (dict): Dictionary of element names and values

        Returns:
            dict: Result with success status, message, and details
        """
        prop = self.get_property(device_name, property_name)
        if not prop:
            return {
                'success': False,
                'error': f'Property {device_name}.{property_name} not found',
                'error_type': 'property_not_found'
            }

        # Check if property is writable
        perm = prop.get('perm', 'rw')
        if perm not in ['rw', 'wo']:
            return {
                'success': False,
                'error': f'Property {device_name}.{property_name} is read-only',
                'error_type': 'permission_denied'
            }

        # Validate elements exist
        for elem_name in elements:
            if elem_name not in prop.get('elements', {}):
                return {
                    'success': False,
                    'error': f'Element {elem_name} not found in property {device_name}.{property_name}',
                    'error_type': 'element_not_found'
                }

        prop_type = prop['type']
        original_prop_type = prop_type

        # Normalize property type (handle both old and new formats)
        if prop_type.startswith('indi_'):
            prop_type = prop_type[5:]  # Remove 'indi_' prefix

        logging.info(f"Setting property {device_name}.{property_name}: original type '{original_prop_type}' -> normalized type '{prop_type}'")

        if prop_type == 'text':
            message = f'<newTextVector device="{device_name}" name="{property_name}">'
            for elem_name, value in elements.items():
                message += f'<oneText name="{elem_name}">{value}</oneText>'
            message += '</newTextVector>'

        elif prop_type == 'number':
            message = f'<newNumberVector device="{device_name}" name="{property_name}">'
            for elem_name, value in elements.items():
                try:
                    # Validate number format
                    float(value)
                    message += f'<oneNumber name="{elem_name}">{value}</oneNumber>'
                except ValueError:
                    return {
                        'success': False,
                        'error': f'Invalid number format for element {elem_name}: {value}',
                        'error_type': 'invalid_value'
                    }
            message += '</newNumberVector>'

        elif prop_type == 'switch':
            message = f'<newSwitchVector device="{device_name}" name="{property_name}">'
            for elem_name, value in elements.items():
                # Validate switch values
                if value not in ['On', 'Off', 'ON', 'OFF']:
                    return {
                        'success': False,
                        'error': f'Invalid switch value for element {elem_name}: {value}. Must be On/Off',
                        'error_type': 'invalid_value'
                    }
                message += f'<oneSwitch name="{elem_name}">{value}</oneSwitch>'
            message += '</newSwitchVector>'

        else:
            return {
                'success': False,
                'error': f'Unsupported property type: {original_prop_type} (normalized: {prop_type})',
                'error_type': 'unsupported_type'
            }

        # Send using PyIndi methods
        device = self.getDevice(device_name)
        if not device:
            return {
                'success': False,
                'error': f'Device {device_name} not found',
                'error_type': 'device_not_found'
            }

        property_obj = device.getProperty(property_name)
        if not property_obj:
            return {
                'success': False,
                'error': f'Property {device_name}.{property_name} not found',
                'error_type': 'property_not_found'
            }

        try:
            if prop_type == 'text':
                text_prop = PyIndi.PropertyText(property_obj)
                for elem_name, value in elements.items():
                    widget = text_prop.findWidgetByName(elem_name)
                    if widget:
                        widget.setText(str(value))
                self.sendNewProperty(text_prop)

            elif prop_type == 'number':
                number_prop = PyIndi.PropertyNumber(property_obj)
                for elem_name, value in elements.items():
                    widget = number_prop.findWidgetByName(elem_name)
                    if widget:
                        widget.setValue(float(value))
                self.sendNewProperty(number_prop)

            elif prop_type == 'switch':
                switch_prop = PyIndi.PropertySwitch(property_obj)
                for elem_name, value in elements.items():
                    widget = switch_prop.findWidgetByName(elem_name)
                    if widget:
                        if value in ['On', 'ON']:
                            widget.setState(PyIndi.ISS_ON)
                        else:
                            widget.setState(PyIndi.ISS_OFF)
                self.sendNewProperty(switch_prop)

        except Exception as e:
            return {
                'success': False,
                'error': f'Failed to send property update: {str(e)}',
                'error_type': 'communication_error'
            }

        # All INDI operations are asynchronous - return success immediately after sending
        # The actual property updates will be received via PyIndi callbacks and polling
        return {
            'success': True,
            'message': f'Property {property_name} command sent successfully',
            'property': property_name,
            'device': device_name,
            'elements': elements
        }

    def is_connected(self):
        """Check if connected to INDI server"""
        return self.connected

    # Removed _cleanup_old_operations - no longer needed with asynchronous operations

    def _auto_connect_device(self, device_name):
        """Automatically connect a device when it becomes available"""
        def connect_after_delay():
            time.sleep(2)  # Wait for device to be fully initialized
            logging.info(f"Auto-connecting device: {device_name}")
            device = self.getDevice(device_name)
            if device and not device.isConnected():
                connection_prop = device.getProperty('CONNECTION')
                if connection_prop:
                    switch_prop = PyIndi.PropertySwitch(connection_prop)
                    connect_widget = switch_prop.findWidgetByName('CONNECT')
                    disconnect_widget = switch_prop.findWidgetByName('DISCONNECT')
                    if connect_widget and disconnect_widget:
                        connect_widget.setState(PyIndi.ISS_ON)
                        disconnect_widget.setState(PyIndi.ISS_OFF)
                        self.sendNewProperty(switch_prop)

        # Run in separate thread to avoid blocking
        thread = threading.Thread(target=connect_after_delay)
        thread.daemon = True
        thread.start()

    def get_device_structure(self, device_name):
        """Get the current property structure for a device"""
        if device_name not in self.properties:
            return None

        device_props = self.properties[device_name]
        structure = {}

        # Group properties by group
        for prop_name, prop_data in device_props.items():
            group_name = prop_data.get('group', 'Main')
            if group_name not in structure:
                structure[group_name] = {}
            structure[group_name][prop_name] = prop_data

        return structure

    def _format_number_value(self, value, format_str):
        """Format a number value according to INDI printf-style format"""
        if not format_str or not value:
            return value

        try:
            # Convert value to float for formatting
            num_value = float(value)

            # Handle INDI-specific %m sexagesimal format
            if 'm' in format_str and format_str.startswith('%'):
                return self._format_sexagesimal(num_value, format_str)

            # Handle INDI-specific format patterns
            elif format_str.startswith('%') and ('d' in format_str or 'i' in format_str):
                # Integer format
                return f"{int(num_value)}"
            elif format_str.startswith('%') and ('f' in format_str or 'e' in format_str or 'E' in format_str or 'g' in format_str or 'G' in format_str):
                # Float format - use Python's % formatting
                return format_str % num_value
            elif ':' in format_str:
                # Time format (hours:minutes:seconds)
                if format_str.count(':') == 2:
                    # HH:MM:SS format
                    hours = int(num_value)
                    minutes = int((num_value - hours) * 60)
                    seconds = ((num_value - hours) * 60 - minutes) * 60
                    return f"{hours:02d}:{minutes:02d}:{seconds:06.3f}"
                elif format_str.count(':') == 1:
                    # MM:SS format
                    minutes = int(num_value)
                    seconds = (num_value - minutes) * 60
                    return f"{minutes:02d}:{seconds:06.3f}"
            else:
                # Default float formatting
                return f"{num_value:.6g}"

        except (ValueError, TypeError):
            # If formatting fails, return original value
            return value

    def _format_sexagesimal(self, value, format_str):
        """Format a number as sexagesimal using INDI %m format specification

        Format: %<w>.<f>m where:
        - <w> = total field width
        - <f> = precision specification:
          - 9 → :mm:ss.ss (HH:MM:SS.ss)
          - 8 → :mm:ss.s (HH:MM:SS.s)
          - 6 → :mm:ss (HH:MM:SS)
          - 5 → :mm.m (HH:MM.m)
          - 3 → :mm (HH:MM)
        """
        try:
            # Parse format like %10.6m or %9m
            import re
            match = re.match(r'%(\d+)(?:\.(\d+))?m', format_str)
            if not match:
                return str(value)

            width = int(match.group(1))
            precision = int(match.group(2)) if match.group(2) else width

            # Handle negative values
            is_negative = value < 0
            abs_value = abs(value)

            # Calculate degrees, minutes, seconds
            degrees = int(abs_value)
            minutes_float = (abs_value - degrees) * 60
            minutes = int(minutes_float)
            seconds = (minutes_float - minutes) * 60

            # Format according to precision specification
            if precision == 9:
                # :mm:ss.ss format
                result = f"{degrees:02d}:{minutes:02d}:{seconds:05.2f}"
            elif precision == 8:
                # :mm:ss.s format
                result = f"{degrees:02d}:{minutes:02d}:{seconds:04.1f}"
            elif precision == 6:
                # :mm:ss format
                result = f"{degrees:02d}:{minutes:02d}:{seconds:02.0f}"
            elif precision == 5:
                # :mm.m format
                minutes_with_decimal = minutes + seconds / 60
                result = f"{degrees:02d}:{minutes_with_decimal:04.1f}"
            elif precision == 3:
                # :mm format
                minutes_rounded = round(minutes + seconds / 60)
                result = f"{degrees:02d}:{minutes_rounded:02d}"
            else:
                # Default to full precision
                result = f"{degrees:02d}:{minutes:02d}:{seconds:05.2f}"

            # Add negative sign if needed
            if is_negative:
                result = '-' + result

            return result

        except (ValueError, TypeError, AttributeError):
            # If formatting fails, return original value
            return str(value)

    def _apply_formatting_to_property(self, prop_data):
        """Apply formatting to number property elements"""
        if prop_data['type'] == 'number':
            for elem_name, element in prop_data['elements'].items():
                if 'format' in element and element['format']:
                    formatted_value = self._format_number_value(element['value'], element['format'])
                    element['formatted_value'] = formatted_value
                else:
                    element['formatted_value'] = element['value']
        return prop_data


# Global INDI client instance
indi_client = None


def get_indi_client():
    """Get the global INDI client instance"""
    global indi_client
    if indi_client is None:
        indi_client = INDIClient()
    return indi_client


def start_indi_client(host='localhost', port=7624):
    """Start the INDI client connection"""
    client = get_indi_client()
    if not client.is_connected():
        return client.connect()
    return True


def stop_indi_client():
    """Stop the INDI client connection"""
    global indi_client
    if indi_client:
        indi_client.disconnect()
        indi_client = None