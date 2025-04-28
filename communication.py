import time
from pyudmx import pyudmx as udmx

class UDMX:
    def __init__(self):
        self.device = None
        self.connect()

    def connect(self):
        try:
            self.device = udmx.uDMXDevice()
            if not self.device.open():
                print("DMX device not found! Please check that:")
                print("1. The DMX interface is properly connected")
                print("2. You have sufficient permissions to access the device")
                return False
            return True
        except Exception as e:
            print(f"Error connecting to DMX device: {str(e)}")
            return False

    def reconnect(self):
        """Attempt to reconnect to the DMX device"""
        print("Attempting to reconnect to DMX device...")
        self.device = None  # Clear the existing device
        return self.connect()  # Try to connect again

    def cleanup(self):
        """Clean up resources when closing the application"""
        if self.device:
            try:
                self.device.close()
            except Exception as e:
                print(f"Note: Could not close device: {str(e)}")
            finally:
                self.device = None

    def send_frame(self, values):
        """Send complete DMX frame"""
        if self.device is None:
            if not self.reconnect():
                return False
            
        try:
            # Send all 512 channels at once
            self.device.send_multi_value(1, values)
            return True
        except Exception as e:
            print(f"Error sending DMX frame: {str(e)}")
            return self.reconnect()

class DMXUpdateManager:
    def __init__(self, dmx_device):
        self.dmx = dmx_device
        self.pending_values = None  # Buffer for pending changes
        self.last_update_time = 0
        self.update_interval = 0.1  # 100ms = 10Hz
        self.on_frame_sent = None

    def queue_update(self, channel, value):
        """Queue a single channel update"""
        if self.pending_values is None:
            self.pending_values = [None] * 512  # Initialize buffer when first update comes
        self.pending_values[channel] = value
        
    def queue_multi_update(self, start_channel, values):
        """Queue multiple channel updates"""
        if self.pending_values is None:
            self.pending_values = [None] * 512
        for i, value in enumerate(values):
            if value is not None:  # Only update if value is provided
                self.pending_values[start_channel + i] = value
    
    def process_updates(self, current_values):
        """Process pending updates at 10Hz"""
        current_time = time.time()
        
        # Check if it's time for an update and if there are pending changes
        if (current_time - self.last_update_time >= self.update_interval and 
            self.pending_values is not None):
            
            # Create frame to send by combining current values with pending changes
            frame_to_send = current_values.copy()
            for i, value in enumerate(self.pending_values):
                if value is not None:
                    frame_to_send[i] = value
            
            # Send the frame
            if self.dmx.send_frame(frame_to_send):
                self.last_update_time = current_time
                # Copy pending changes to current values
                for i, value in enumerate(self.pending_values):
                    if value is not None:
                        current_values[i] = value
                self.pending_values = None
                # Call the callback here
                if self.on_frame_sent:
                    self.on_frame_sent(frame_to_send)
                return True, frame_to_send
        
        return False, None 