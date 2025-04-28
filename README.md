# DMX Light Controller

A Python application for controlling DMX lights through a USB dongle. This application supports controlling up to 12 fixtures with 8 channels each.

## Requirements
- Python 3.6 or higher
- pyserial library

## Setup
1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

2. Connect your DMX USB dongle to your computer

3. Update the serial port in `dmx_controller.py`:
   - Find the line `port='COM3'` in the code
   - Change 'COM3' to match your USB dongle's port number
   - You can find the correct port number in Windows Device Manager under "Ports (COM & LPT)"

## Usage
1. Run the application:
```bash
python dmx_controller.py
```

2. Using the interface:
   - Select the fixtures you want to control using the checkboxes
   - Use the sliders to control different channels for the selected fixtures
   - Channel values range from 0 to 255
   - The first fixture starts at DMX address 1, and each fixture uses 8 channels

## Troubleshooting
- If you see "Could not open serial port" error:
  - Make sure your USB dongle is properly connected
  - Verify you're using the correct COM port number
  - Check if you have the necessary permissions to access the port
  - Make sure no other application is using the port

## Notes
- The DMX protocol implementation might need adjustments based on your specific USB dongle
- The application assumes each fixture uses 8 consecutive DMX channels
- Fixtures are addressed sequentially starting from address 1 