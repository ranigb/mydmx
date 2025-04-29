# DMX Light Controller

A Python application for controlling DMX lights through a USB dongle. This application supports controlling up to 12 fixtures with 8 channels each, featuring a modern GUI with frame management and real-time control.

## Features
- Control up to 12 fixtures with 8 channels each
- Modern GUI with frame management system
- Real-time DMX output visualization
- Master dimmer control
- Color wheel for RGB control
- Stage layout visualization
- Frame saving and loading
- Live tracking mode
- Fade in/out effects
- Automatic device reconnection

## Requirements
- Python 3.6 or higher
- pyudmx library
- tkinter (usually comes with Python)

## Setup
1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

2. Connect your DMX USB dongle to your computer

3. Run the application:
```bash
python mydmx.py
```

## Usage
1. **Fixture Selection**
   - Use the checkboxes to select which fixtures to control
   - Use "Select All" and "Clear Selection" buttons for quick selection

2. **Channel Control**
   - Use the sliders to control different channels for selected fixtures
   - Channel values range from 0 to 255
   - Channels: Dimmer, Red, Green, Blue, White, Strobe, Chaser, NA

3. **Frame Management**
   - Create and manage multiple frames
   - Right-click on tabs to access frame operations
   - Save and load frame values
   - Copy frames with the "Copy" option

4. **Master Dimmer**
   - Control overall intensity of all fixtures
   - Located next to the DMX output visualization
   - Values range from 0% to 100%

5. **Stage Layout**
   - Visual representation of fixture positions
   - Drag fixtures to reposition
   - Right-click and drag to rotate fixtures
   - Changes sync between frame and DMX views

6. **Color Control**
   - Use the color wheel for RGB control
   - Adjust white intensity separately
   - Live preview in stage layout

7. **Live Tracking**
   - Enable "Live Track" to update DMX output in real-time
   - Disable to make changes without affecting output

8. **Fade Effects**
   - Use "Fade In" button to smoothly transition to current frame values
   - Adjust fade time using the slider
   - Only affects selected fixtures

## Troubleshooting
- If the device disconnects:
  - The application will attempt to reconnect automatically
  - Check USB connection if reconnection fails
  - Verify device compatibility with pyudmx

- If values don't update:
  - Check if "Live Track" is enabled
  - Verify fixture selection
  - Check master dimmer setting

## Notes
- The application uses the pyudmx library for DMX communication
- Each fixture uses 8 consecutive DMX channels
- Fixtures are addressed sequentially starting from address 1
- The stage layout is saved between sessions
- Frame values are preserved until the application is closed 