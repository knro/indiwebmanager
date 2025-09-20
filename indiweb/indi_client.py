#!/usr/bin/env python

import socket
import threading
import xml.etree.ElementTree as ET
import time
import logging
import re
from collections import defaultdict


class INDIClient:
    """
    A simple INDI client for connecting to an INDI server and managing device properties.
    Based on the INDI protocol: https://indilib.org/develop/developer-manual/101-standard-properties.html
    """

    def __init__(self, host='localhost', port=7624):
        self.host = host
        self.port = port
        self.socket = None
        self.connected = False
        self.devices = {}
        self.properties = defaultdict(dict)
        self.dirty_properties = defaultdict(set)  # Track changed properties per device
        self.auto_connect_devices = True
        self.listeners = []
        self.receive_thread = None
        self.running = False

    def connect(self):
        """Connect to the INDI server"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10)  # 10 second timeout for connection
            self.socket.connect((self.host, self.port))
            self.socket.settimeout(None)  # Remove timeout after connection
            self.connected = True
            self.running = True

            # Start receive thread
            self.receive_thread = threading.Thread(target=self._receive_loop)
            self.receive_thread.daemon = True
            self.receive_thread.start()

            # Request device list
            self.send_message('<getProperties version="1.7"/>')
            logging.info(f"Connected to INDI server at {self.host}:{self.port}")

            # Wait a bit for initial properties to load
            time.sleep(1)
            return True

        except Exception as e:
            logging.error(f"Failed to connect to INDI server: {e}")
            self.connected = False
            return False

    def disconnect(self):
        """Disconnect from the INDI server"""
        self.running = False
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
        self.connected = False
        self.socket = None
        logging.info("Disconnected from INDI server")

    def send_message(self, message):
        """Send a message to the INDI server"""
        if not self.connected or not self.socket:
            return False

        try:
            self.socket.send(message.encode() + b'\n')
            return True
        except Exception as e:
            logging.error(f"Failed to send message: {e}")
            return False

    def _receive_loop(self):
        """Main receive loop for processing INDI messages"""
        buffer = ""

        while self.running and self.connected:
            try:
                data = self.socket.recv(4096).decode()
                if not data:
                    break

                buffer += data

                # Process complete XML messages
                while True:
                    # Find the start and end of an XML message
                    start = buffer.find('<')
                    if start == -1:
                        break

                    # Find the matching closing tag
                    tag_end = buffer.find('>', start)
                    if tag_end == -1:
                        break

                    tag_name = buffer[start+1:tag_end].split()[0]
                    if tag_name.endswith('/'):
                        # Self-closing tag
                        message = buffer[start:tag_end+1]
                        buffer = buffer[tag_end+1:]
                        self._process_message(message)
                    else:
                        # Find closing tag
                        closing_tag = f"</{tag_name}>"
                        end = buffer.find(closing_tag, tag_end)
                        if end == -1:
                            break

                        message = buffer[start:end + len(closing_tag)]
                        buffer = buffer[end + len(closing_tag):]
                        self._process_message(message)

            except Exception as e:
                logging.error(f"Error in receive loop: {e}")
                break

        self.connected = False

    def _process_message(self, message):
        """Process an INDI XML message"""
        try:
            root = ET.fromstring(message)

            if root.tag == 'defTextVector':
                self._process_def_property(root, 'text')
            elif root.tag == 'defNumberVector':
                self._process_def_property(root, 'number')
            elif root.tag == 'defSwitchVector':
                self._process_def_property(root, 'switch')
            elif root.tag == 'defLightVector':
                self._process_def_property(root, 'light')
            elif root.tag == 'defBLOBVector':
                self._process_def_property(root, 'blob')
            elif root.tag in ['setTextVector', 'setNumberVector', 'setSwitchVector', 'setLightVector', 'setBLOBVector']:
                self._process_set_property(root)
            elif root.tag == 'delProperty':
                self._process_del_property(root)
            elif root.tag == 'message':
                self._process_message_tag(root)

        except ET.ParseError as e:
            logging.warning(f"Failed to parse XML message: {e}")
        except Exception as e:
            logging.error(f"Error processing message: {e}")

    def _process_def_property(self, root, prop_type):
        """Process a property definition message"""
        device = root.get('device')
        name = root.get('name')
        label = root.get('label', name)
        group = root.get('group', 'Main')
        state = root.get('state', 'Idle')
        perm = root.get('perm', 'rw')
        rule = root.get('rule') if prop_type == 'switch' else None

        if device not in self.devices:
            self.devices[device] = {}

        elements = {}
        for child in root:
            if child.tag.startswith('def'):
                elem_name = child.get('name')
                elem_label = child.get('label', elem_name)
                elem_value = (child.text or '').strip()

                element = {
                    'name': elem_name,
                    'label': elem_label,
                    'value': elem_value
                }

                # Add type-specific attributes
                if prop_type == 'number':
                    element.update({
                        'min': child.get('min'),
                        'max': child.get('max'),
                        'step': child.get('step'),
                        'format': child.get('format')
                    })

                elements[elem_name] = element

        property_data = {
            'name': name,
            'label': label,
            'group': group,
            'type': prop_type,
            'state': state.lower(),
            'perm': perm,
            'rule': rule,
            'elements': elements,
            'device': device
        }

        # Apply formatting to number properties
        property_data = self._apply_formatting_to_property(property_data)

        self.properties[device][name] = property_data
        self.devices[device][name] = property_data

        # Mark property as dirty (new property)
        self.dirty_properties[device].add(name)

        # Auto-connect device if it has a CONNECTION property
        if self.auto_connect_devices and name == 'CONNECTION':
            self._auto_connect_device(device)

        # Notify listeners
        self._notify_listeners('property_defined', device, property_data)

    def _process_set_property(self, root):
        """Process a property update message"""
        device = root.get('device')
        name = root.get('name')
        state = root.get('state', 'Idle')

        if device in self.properties and name in self.properties[device]:
            prop = self.properties[device][name]
            prop['state'] = state.lower()

            # Update element values
            for child in root:
                if child.tag.startswith('one'):
                    elem_name = child.get('name')
                    if elem_name in prop['elements']:
                        prop['elements'][elem_name]['value'] = (child.text or '').strip()

            # Apply formatting to updated property
            prop = self._apply_formatting_to_property(prop)

            # Mark property as dirty (updated property)
            self.dirty_properties[device].add(name)

            # Notify listeners
            self._notify_listeners('property_updated', device, prop)

    def _process_del_property(self, root):
        """Process a property deletion message"""
        device = root.get('device')
        name = root.get('name')

        if device in self.properties:
            if name:
                # Delete specific property
                if name in self.properties[device]:
                    del self.properties[device][name]
                    self._notify_listeners('property_deleted', device, {'name': name})
            else:
                # Delete all properties for device
                self.properties[device] = {}
                if device in self.devices:
                    del self.devices[device]
                self._notify_listeners('device_deleted', device, None)

    def _process_message_tag(self, root):
        """Process a message tag"""
        device = root.get('device')
        message = root.text or ''
        timestamp = root.get('timestamp', str(time.time()))

        self._notify_listeners('message', device, {
            'message': message,
            'timestamp': timestamp
        })

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
        return list(self.devices.keys())

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
            if device_name in self.devices:
                return True
            time.sleep(0.1)
        return False

    def set_property(self, device_name, property_name, elements):
        """Set property values"""
        prop = self.get_property(device_name, property_name)
        if not prop:
            return False

        prop_type = prop['type']
        message = ""

        if prop_type == 'text':
            message = f'<newTextVector device="{device_name}" name="{property_name}">'
            for elem_name, value in elements.items():
                message += f'<oneText name="{elem_name}">{value}</oneText>'
            message += '</newTextVector>'

        elif prop_type == 'number':
            message = f'<newNumberVector device="{device_name}" name="{property_name}">'
            for elem_name, value in elements.items():
                message += f'<oneNumber name="{elem_name}">{value}</oneNumber>'
            message += '</newNumberVector>'

        elif prop_type == 'switch':
            message = f'<newSwitchVector device="{device_name}" name="{property_name}">'
            for elem_name, value in elements.items():
                message += f'<oneSwitch name="{elem_name}">{value}</oneSwitch>'
            message += '</newSwitchVector>'

        return self.send_message(message)

    def is_connected(self):
        """Check if connected to INDI server"""
        return self.connected

    def _auto_connect_device(self, device_name):
        """Automatically connect a device when it becomes available"""
        def connect_after_delay():
            time.sleep(2)  # Wait for device to be fully initialized
            logging.info(f"Auto-connecting device: {device_name}")
            connection_prop = self.get_property(device_name, 'CONNECTION')
            if connection_prop and connection_prop['elements'].get('CONNECT'):
                # Only connect if not already connected
                if connection_prop['elements']['CONNECT']['value'] != 'On':
                    self.set_property(device_name, 'CONNECTION', {'CONNECT': 'On', 'DISCONNECT': 'Off'})

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

    def get_dirty_properties(self, device_name):
        """Get list of properties that have changed since last check"""
        dirty_props = list(self.dirty_properties[device_name])
        # Clear dirty flags after returning them
        self.dirty_properties[device_name].clear()
        return dirty_props

    def get_changed_properties(self, device_name, property_names):
        """Get current values for specified properties"""
        if device_name not in self.properties:
            return {}

        result = {}
        for prop_name in property_names:
            if prop_name in self.properties[device_name]:
                result[prop_name] = self.properties[device_name][prop_name]

        return result

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