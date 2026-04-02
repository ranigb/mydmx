# Goal
The application should allow controlling light fixture for stage performance. It should allow planing different scenes and transitions between scenes and also using the scenes and modifying them during the show.

# Light fixtures
- Light fixtures are defined in fixture.py
- The color and brightness of each fixture can be controlled but the lightfixtures do not support tilt or pan

# Mandatory Rules
- communication.py should not be changed
- Communication to the light fixtures is done only through the DMXUpdateManager class. 
- Only DMXUpdateManager should use the class UDMX directly

# Architecture
The architecture of the tool is based on 3 main layers
- communication.py - responsible for sending commands to the light fixtures
- engine - this layer implements the instructions for displying a specific scene, fading between scenes, running sequences, and etc.
- gui - this layer allows designing scenes and sequences as well as instructing the engine to present a scene, fade between scenes, apply a sequence, and etc.