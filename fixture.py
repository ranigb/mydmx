class Fixture:
    def __init__(self, fixture_id, start_address, num_channels, position=(0, 0), angle=0):
        self.fixture_id = fixture_id  # Unique identifier for the fixture
        self.start_address = start_address  # DMX start address (1-512)
        self.num_channels = num_channels  # Number of DMX channels used
        self.position = position  # (x, y) tuple for layout position
        self.angle = angle  # Direction in degrees (0-359)
        
    def get_channel_address(self, channel):
        """Get the DMX address for a specific channel (0-based)"""
        if channel < 0 or channel >= self.num_channels:
            raise ValueError(f"Channel {channel} out of range (0-{self.num_channels-1})")
        return self.start_address + channel
        
    def get_all_addresses(self):
        """Get all DMX addresses used by this fixture"""
        return range(self.start_address, self.start_address + self.num_channels)
        
    def set_position(self, x, y):
        """Update fixture position"""
        self.position = (x, y)
        
    def set_angle(self, angle):
        """Update fixture angle"""
        self.angle = angle % 360  # Ensure angle is 0-359 