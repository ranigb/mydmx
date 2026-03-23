from __future__ import annotations

from enum import Enum

class Fixture:
    class Channels(Enum):
        """Enum for common channel types (can be extended as needed)"""
        INTENSITY = 0
        RED = 1
        GREEN = 2
        BLUE = 3
        WHITE = 4

    def __init__(self, fixture_id : int, start_address : int, num_channels : int, position: tuple[int, int] = (0, 0), angle: int = 0):
        self.fixture_id = fixture_id  # Unique identifier for the fixture
        self.start_address = start_address  # DMX start address (1-512)
        self.num_channels = num_channels  # Number of DMX channels used
        self.position = position  # (x, y) tuple for layout position
        self.angle = angle  # Direction in degrees (0-359)
        
    def get_channel_address(self, channel: "int | Fixture.Channels") -> int:
        """Get the DMX address for a specific channel (0-based)"""
        if isinstance(channel, Fixture.Channels):
            channel = channel.value
        if channel < 0 or channel >= self.num_channels:
            raise ValueError(f"Channel {channel} out of range (0-{self.num_channels-1})")
        return self.start_address + channel
        
    def get_all_addresses(self):
        """Get all DMX addresses used by this fixture"""
        return range(self.start_address, self.start_address + self.num_channels)
        
    def set_position(self, x: int, y: int):
        """Update fixture position"""
        self.position = (x, y)
        
    def set_angle(self, angle: int):
        """Update fixture angle"""
        self.angle = angle % 360  # Ensure angle is 0-359 
    

