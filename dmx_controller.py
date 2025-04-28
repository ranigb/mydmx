import tkinter as tk
from tkinter import ttk
from tkinter import simpledialog, messagebox
from pyudmx import pyudmx as udmx
import time
import math
import usb.core

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

class ColorWheel(tk.Canvas):
    def __init__(self, parent, size=200, **kwargs):
        super().__init__(parent, width=size, height=size, **kwargs)
        self.size = size
        self.center = size // 2
        self.radius = (size - 20) // 2  # Leave some margin
        
        # Create the color wheel
        self.create_color_wheel()
        
        # Bind mouse events
        self.bind('<Button-1>', self.on_click)
        self.bind('<B1-Motion>', self.on_drag)
        self.bind('<ButtonRelease-1>', self.on_release)
        
    def create_color_wheel(self):
        # Create the color wheel using arcs
        for angle in range(360):
            # Convert angle to radians
            rad = math.radians(angle)
            
            # Calculate color based on angle (HSV to RGB conversion)
            h = angle / 360.0
            s = 1.0
            v = 1.0
            
            # Convert HSV to RGB
            if s == 0.0:
                r, g, b = v, v, v
            else:
                h *= 6.0
                i = int(h)
                f = h - i
                p = v * (1.0 - s)
                q = v * (1.0 - s * f)
                t = v * (1.0 - s * (1.0 - f))
                
                if i == 0:
                    r, g, b = v, t, p
                elif i == 1:
                    r, g, b = q, v, p
                elif i == 2:
                    r, g, b = p, v, t
                elif i == 3:
                    r, g, b = p, q, v
                elif i == 4:
                    r, g, b = t, p, v
                else:
                    r, g, b = v, p, q
            
            # Convert to hex color
            color = f'#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}'
            
            # Create arc segment
            self.create_arc(
                self.center - self.radius,
                self.center - self.radius,
                self.center + self.radius,
                self.center + self.radius,
                start=angle,
                extent=1,
                fill=color,
                outline=color
            )
    
    def on_click(self, event):
        self.update_color(event.x, event.y)
    
    def on_drag(self, event):
        self.update_color(event.x, event.y)
    
    def on_release(self, event):
        pass
    
    def update_color(self, x, y):
        # Calculate distance from center
        dx = x - self.center
        dy = y - self.center
        distance = math.sqrt(dx*dx + dy*dy)
        
        if distance <= self.radius:
            # Calculate angle
            angle = math.degrees(math.atan2(dy, dx))
            if angle < 0:
                angle += 360
                
            # Calculate RGB values
            h = angle / 360.0
            s = 1.0
            v = 1.0
            
            # Convert HSV to RGB
            if s == 0.0:
                r, g, b = v, v, v
            else:
                h *= 6.0
                i = int(h)
                f = h - i
                p = v * (1.0 - s)
                q = v * (1.0 - s * f)
                t = v * (1.0 - s * (1.0 - f))
                
                if i == 0:
                    r, g, b = v, t, p
                elif i == 1:
                    r, g, b = q, v, p
                elif i == 2:
                    r, g, b = p, v, t
                elif i == 3:
                    r, g, b = p, q, v
                elif i == 4:
                    r, g, b = t, p, v
                else:
                    r, g, b = v, p, q
            
            # Convert to 0-255 range
            r = int(r * 255)
            g = int(g * 255)
            b = int(b * 255)
            
            # Update RGB sliders
            if hasattr(self, 'callback'):
                self.callback(r, g, b)

class StageLayout(tk.Canvas):
    def __init__(self, parent, num_fixtures, positions=None, angles=None, 
                 sync_callback=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.num_fixtures = num_fixtures
        self.fixture_positions = positions if positions is not None else {}
        self.fixture_angles = angles if angles is not None else {}
        self.fixture_colors = {}
        self.sync_callback = sync_callback
        self.dragging = None
        self.drag_start = None
        self.rotating = None
        self.rotate_start = None
        self.callback = None  # Callback for fixture selection
        
        # Create grid
        self.create_grid()
        
        # Create fixtures
        self.create_fixtures()
        
        # Bind mouse events
        self.bind('<Button-1>', self.on_click)
        self.bind('<B1-Motion>', self.on_drag)
        self.bind('<ButtonRelease-1>', self.on_release)
        self.bind('<Button-3>', self.on_right_click)  # Right click for rotation
        self.bind('<B3-Motion>', self.on_rotate)
        
    def create_grid(self):
        # Draw grid lines
        width = self.winfo_reqwidth()
        height = self.winfo_reqheight()
        
        # Draw vertical lines
        for x in range(0, width, 50):
            self.create_line(x, 0, x, height, fill='#666666', dash=(2, 2))
            
        # Draw horizontal lines
        for y in range(0, height, 50):
            self.create_line(0, y, width, y, fill='#666666', dash=(2, 2))
            
    def create_fixtures(self):
        # Create initial fixture positions
        for i in range(self.num_fixtures):
            # Calculate position if not already set
            if i not in self.fixture_positions:
                row = i // 6
                col = i % 6
                x = 65 + col * 75  # Increased spacing between columns
                y = 60 if row == 0 else 190  # Increased vertical separation between rows
                self.fixture_positions[i] = (x, y)
                
            if i not in self.fixture_angles:
                # Set initial angle (90 for top row pointing down, 270 for bottom row pointing up)
                self.fixture_angles[i] = 90 if i < 6 else 270
                
            x, y = self.fixture_positions[i]
            angle = self.fixture_angles[i]
            color = 'gray'
            
            # Create fixtures with current positions and angles
            self.create_fixture(i, x, y, angle, color)

    def create_fixture(self, i, x, y, angle, color):
        # Create white intensity square
        self.create_rectangle(x-15, y-15, x+15, y+15, 
                            fill='black', tags=f'fixture_{i}')
        
        # Create arrow
        self.create_arrow(x, y, angle, color, f'fixture_{i}')
        
        # Create fixture label
        rad = math.radians(angle + 180)
        num_dx = math.cos(rad) * 25
        num_dy = math.sin(rad) * 25
        self.create_text(x + num_dx, y + num_dy, 
                        text=str(i+1), fill='white', tags=f'fixture_{i}')

    def create_arrow(self, x, y, angle, color, tags):
        """Create an arrow shape like a one-way road sign"""
        # Arrow parameters
        length = 35  # Length of the arrow
        width = 20   # Width of the arrow
        
        # Calculate arrow points
        rad = math.radians(angle)
        
        # Calculate the three points of the triangle
        # Base point (center)
        base_x = x
        base_y = y
        
        # Tip point
        tip_x = x + math.cos(rad) * length
        tip_y = y + math.sin(rad) * length
        
        # Calculate perpendicular offset for the base points
        perp_rad = rad + math.pi/2  # 90 degrees
        offset_x = math.cos(perp_rad) * width/2
        offset_y = math.sin(perp_rad) * width/2
        
        # Base points
        base1_x = x + offset_x
        base1_y = y + offset_y
        base2_x = x - offset_x
        base2_y = y - offset_y
        
        # Create arrow shape (triangle)
        points = [
            base1_x, base1_y,  # First base point
            tip_x, tip_y,      # Tip point
            base2_x, base2_y   # Second base point
        ]
        
        # Create solid arrow
        return self.create_polygon(points, fill=color, outline='white', tags=tags)
            
    def on_click(self, event):
        # Find clicked fixture
        items = self.find_closest(event.x, event.y)
        if items:
            tags = self.gettags(items[0])
            for tag in tags:
                if tag.startswith('fixture_'):
                    fixture_num = int(tag.split('_')[1])
                    self.dragging = fixture_num
                    self.drag_start = (event.x, event.y)
                    
                    # Call the callback with the fixture number
                    if self.callback:
                        self.callback(fixture_num)
                    break
                    
    def on_right_click(self, event):
        # Find clicked fixture
        items = self.find_closest(event.x, event.y)
        if items:
            tags = self.gettags(items[0])
            for tag in tags:
                if tag.startswith('fixture_'):
                    self.rotating = int(tag.split('_')[1])
                    self.rotate_start = (event.x, event.y)
                    break
                    
    def on_rotate(self, event):
        if self.rotating is not None:
            # Calculate angle
            x, y = self.fixture_positions[self.rotating]
            start_angle = math.atan2(self.rotate_start[1] - y, self.rotate_start[0] - x)
            current_angle = math.atan2(event.y - y, event.x - x)
            angle_diff = math.degrees(current_angle - start_angle)
            
            # Update fixture angle
            new_angle = (self.fixture_angles[self.rotating] + angle_diff) % 360
            self.fixture_angles[self.rotating] = new_angle
            
            # Update rotate start
            self.rotate_start = (event.x, event.y)
            
            # Call sync callback to update both layouts
            if self.sync_callback:
                self.sync_callback()
            
    def update_arrow(self, fixture_num):
        """Update the arrow for a fixture"""
        x, y = self.fixture_positions[fixture_num]
        angle = self.fixture_angles[fixture_num]
        color = self.fixture_colors[fixture_num]
        
        # Remove old arrow and number
        for item in self.find_withtag(f'fixture_{fixture_num}'):
            if self.type(item) in ['polygon', 'text']:
                self.delete(item)
                
        # Create new arrow
        self.create_arrow(x, y, angle, color, f'fixture_{fixture_num}')
        
        # Update number position
        rad = math.radians(angle + 180)  # Opposite direction
        num_dx = math.cos(rad) * 25  # Increased offset to 25 pixels
        num_dy = math.sin(rad) * 25
        
        # Create new number
        self.create_text(x + num_dx, y + num_dy, text=str(fixture_num+1), fill='white', tags=f'fixture_{fixture_num}')
                    
    def on_drag(self, event):
        if self.dragging is not None:
            # Calculate movement
            dx = event.x - self.drag_start[0]
            dy = event.y - self.drag_start[1]
            
            # Update position
            x, y = self.fixture_positions[self.dragging]
            new_x = x + dx
            new_y = y + dy
            self.fixture_positions[self.dragging] = (new_x, new_y)
            
            # Update drag start position
            self.drag_start = (event.x, event.y)
            
            # Call sync callback to update both layouts
            if self.sync_callback:
                self.sync_callback()
            
    def on_release(self, event):
        self.dragging = None
        self.drag_start = None
        self.rotating = None
        self.rotate_start = None
        
    def update_fixture_color(self, fixture_num, color, white_intensity):
        """Update the color of a fixture"""
        if fixture_num in self.fixture_positions:
            # Store the new color
            self.fixture_colors[fixture_num] = color
            
            # Update white intensity square
            for item in self.find_withtag(f'fixture_{fixture_num}'):
                if self.type(item) == 'rectangle':
                    # Ensure white intensity is properly formatted as hex
                    white_color = f'#{white_intensity:02x}{white_intensity:02x}{white_intensity:02x}'
                    self.itemconfig(item, fill=white_color)
                elif self.type(item) == 'polygon':
                    # Ensure color is properly formatted as hex
                    if not color.startswith('#'):
                        color = f'#{color}'
                    self.itemconfig(item, fill=color)
                    break

    def update_fixture_position(self, fixture_num, x, y, angle):
        """Update a fixture's position and angle"""
        # Remove old fixture elements
        for item in self.find_withtag(f'fixture_{fixture_num}'):
            self.delete(item)
            
        # Create new fixture at updated position
        color = self.fixture_colors.get(fixture_num, 'gray')
        self.create_fixture(fixture_num, x, y, angle, color)

class DMXController:
    def __init__(self, root):
        self.root = root
        self.root.title("DMX Light Controller (uDMX)")
        
        # DMX Configuration
        self.num_fixtures = 12
        self.channels_per_fixture = 8
        self.selected_fixtures = set()  # To store selected fixtures
        self.dmx_values = [0] * 512  # Store all DMX values
        
        # Frame management
        self.frames = {}  # Dictionary to store frame values
        self.current_frame = None  # Initialize current_frame
        
        # Channel labels
        self.channel_labels = [
            "Dimmer",
            "Red",
            "Green",
            "Blue",
            "White",
            "Strobe",
            "Chasser",
            "NA"
        ]
        
        # Initialize uDMX connection
        self.dmx = UDMX()
        
        # Add shared layout state
        self.shared_fixture_positions = {}
        self.shared_fixture_angles = {}
        
        # DMX output state
        self.pending_changes = False  # Flag to track if changes need to be sent
        self.last_dmx_send = 0  # Time of last DMX send
        
        # Add dictionary to store selected fixtures for each frame
        self.frame_selections = {}  # Dictionary to store selected fixtures for each frame
        
        # Initialize DMX update manager
        self.update_manager = DMXUpdateManager(self.dmx)
        self.update_manager.on_frame_sent = self.update_dmx_layout
        
        # Create widgets
        self.create_widgets()
        
        # Create initial frame and set it as current
        self.create_frame_tab("Frame 1")
        self.current_frame = "Frame 1"
        self.frames["Frame 1"] = [0] * 512  # Initialize with zeros
        
        # Start periodic connection check
        self.root.after(1000, self.check_connection)
        
        # Start periodic DMX update
        self.root.after(100, self.update_dmx_output)
        
        # Start periodic live track update
        self.root.after(50, self.periodic_live_track_update)
        
        # Add fade-related attributes
        self._fade_in_progress = False
        self._fade_state = None
        
        # Flag to track if DMX values match frame values
        self.dmx_matches_frame = False

    def create_widgets(self):
        # Create main container
        main_frame = ttk.Frame(self.root)
        main_frame.grid(row=0, column=0, padx=10, pady=5, sticky="nsew")
        
        # Create tab control
        self.tab_control = ttk.Notebook(main_frame)
        self.tab_control.grid(row=0, column=0, columnspan=3, sticky="ew")
        
        # Bind events for tab control
        self.tab_control.bind("<Button-3>", self.show_tab_menu)
        self.tab_control.bind("<Button-1>", self.on_tab_press)
        self.tab_control.bind("<B1-Motion>", self.on_tab_drag)
        self.tab_control.bind("<ButtonRelease-1>", self.on_tab_release)
        self.tab_control.bind("<<NotebookTabChanged>>", self.on_tab_changed)
        
        # Create stage layouts container frame
        stage_layouts_frame = ttk.Frame(main_frame)
        stage_layouts_frame.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")

        # Create frame layout frame
        frame_stage_frame = ttk.LabelFrame(stage_layouts_frame, text="Frame Values", padding="10")
        frame_stage_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        
        # Create DMX output layout frame
        dmx_stage_frame = ttk.LabelFrame(stage_layouts_frame, text="DMX Output", padding="10")
        dmx_stage_frame.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")
        
        # Create stage layout canvases with shared state
        self.frame_layout = StageLayout(frame_stage_frame, self.num_fixtures, 
                                      width=500, height=250, bg='#333333',
                                      positions=self.shared_fixture_positions,
                                      angles=self.shared_fixture_angles,
                                      sync_callback=self.sync_layouts)
        self.frame_layout.grid(row=0, column=0, padx=5, pady=5)
        
        self.dmx_layout = StageLayout(dmx_stage_frame, self.num_fixtures, 
                                    width=500, height=250, bg='#333333',
                                    positions=self.shared_fixture_positions,
                                    angles=self.shared_fixture_angles,
                                    sync_callback=self.sync_layouts)
        self.dmx_layout.grid(row=0, column=0, padx=5, pady=5)
        
        # Set callbacks
        self.frame_layout.callback = self.on_fixture_click
        self.dmx_layout.callback = self.on_fixture_click
        
        # Create left frame for fixture selection
        left_frame = ttk.Frame(main_frame)
        left_frame.grid(row=1, column=1, padx=5, pady=5, sticky="nsew")
        
        # Create fixture selection frame
        fixture_frame = ttk.LabelFrame(left_frame, text="Fixture Selection", padding="10")
        fixture_frame.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")
        
        # Add selection buttons at the top of the fixture frame
        selection_buttons_frame = ttk.Frame(fixture_frame)
        selection_buttons_frame.grid(row=0, column=0, columnspan=3, padx=5, pady=5, sticky="ew")
        
        # Add Select All button
        self.select_all_button = ttk.Button(
            selection_buttons_frame, 
            text="Select All", 
            command=self.toggle_select_all
        )
        self.select_all_button.grid(row=0, column=0, padx=5)
        
        # Add Clear Selection button
        self.clear_selection_button = ttk.Button(
            selection_buttons_frame, 
            text="Clear Selection", 
            command=self.clear_selection
        )
        self.clear_selection_button.grid(row=0, column=1, padx=5)
        
        # Create fixture checkbuttons and color indicators
        self.fixture_vars = []
        self.color_indicators = []
        for i in range(self.num_fixtures):
            # Create frame for each fixture
            fixture_item = ttk.Frame(fixture_frame)
            fixture_item.grid(row=i//3 + 1, column=i%3, padx=5, pady=2)  # Added +1 to row to account for buttons
            
            # Create checkbutton
            var = tk.BooleanVar()
            self.fixture_vars.append(var)
            ttk.Checkbutton(
                fixture_item, 
                text=f"Fixture {i+1}",
                variable=var,
                command=self.update_selected_fixtures
            ).grid(row=0, column=0, padx=2)
            
            # Create color indicator (circle with white intensity square)
            color_canvas = tk.Canvas(fixture_item, width=24, height=24, bg='white', highlightthickness=0)
            color_canvas.grid(row=0, column=1, padx=2)
            # Create the white intensity square
            color_canvas.create_rectangle(0, 0, 24, 24, fill='black', outline='black')
            # Create the color circle
            color_canvas.create_oval(4, 4, 20, 20, fill='black', outline='black')
            self.color_indicators.append(color_canvas)
        
        # Create control buttons frame BELOW fixture selection
        control_buttons_frame = ttk.Frame(left_frame)
        control_buttons_frame.grid(row=2, column=0, padx=5, pady=5, sticky="ew")

        # Add Apply button
        self.apply_button = ttk.Button(
            control_buttons_frame, 
            text="Apply", 
            command=self.apply_current_values
        )
        self.apply_button.grid(row=0, column=0, padx=5)

        # Add Live Track checkbox
        self.live_track = tk.BooleanVar(value=False)
        self.live_track_cb = ttk.Checkbutton(
            control_buttons_frame,
            text="Live Track",
            variable=self.live_track
        )
        self.live_track_cb.grid(row=0, column=1, padx=5)

        # Add Fade In controls (new row)
        fade_frame = ttk.Frame(control_buttons_frame)
        fade_frame.grid(row=1, column=0, columnspan=2, padx=5, pady=(5,0), sticky="ew")

        # Add Fade In button
        self.fade_button = ttk.Button(
            fade_frame,
            text="Fade In",
            command=self.fade_in_values
        )
        self.fade_button.grid(row=0, column=0, padx=5)

        # Add Fade Time slider
        self.fade_time = tk.DoubleVar(value=2.0)  # Default 2 seconds
        fade_slider = ttk.Scale(
            fade_frame,
            from_=0.1,
            to=10.0,
            orient="horizontal",
            variable=self.fade_time
        )
        fade_slider.grid(row=0, column=1, padx=5, sticky="ew")

        # Add Fade Time label
        self.fade_time_label = ttk.Label(fade_frame, text="2.0s")
        self.fade_time_label.grid(row=0, column=2, padx=5)

        # Update fade time label when slider changes
        def update_fade_label(val):
            self.fade_time_label.configure(text=f"{float(val):.1f}s")
        fade_slider.configure(command=update_fade_label)

        # Create right frame for controls
        right_frame = ttk.Frame(main_frame)
        right_frame.grid(row=1, column=2, padx=5, pady=5, sticky="nsew")
        
        # Create channel control frame
        channel_frame = ttk.LabelFrame(right_frame, text="Channel Controls", padding="10")
        channel_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")

        # Create sliders for each channel
        self.channel_values = []
        for i in range(self.channels_per_fixture):
            ttk.Label(channel_frame, text=f"{self.channel_labels[i]}").grid(row=i, column=0, padx=5)
            value = tk.IntVar()
            self.channel_values.append(value)
            
            def create_slider_command(channel):
                def slider_command(val):
                    try:
                        int_val = int(float(val))
                        self.channel_values[channel].set(int_val)
                        self.on_slider_change(channel)
                    except ValueError:
                        pass
                return slider_command
            
            slider = ttk.Scale(
                channel_frame,
                from_=0,
                to=255,
                orient="horizontal",
                variable=value,
                command=create_slider_command(i)
            )
            slider.grid(row=i, column=1, padx=5, pady=2, sticky="ew")
            value_label = ttk.Label(channel_frame, textvariable=value)
            value_label.grid(row=i, column=2, padx=5)
        
        # Create color wheel frame
        color_frame = ttk.LabelFrame(right_frame, text="Color Wheel", padding="10")
        color_frame.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")
        
        # Create color wheel
        self.color_wheel = ColorWheel(color_frame, size=200)
        self.color_wheel.grid(row=0, column=0, padx=5, pady=5)
        self.color_wheel.callback = self.update_rgb_from_wheel

    def create_frame_tab(self, frame_name):
        """Create a new tab for a frame"""
        frame = ttk.Frame(self.tab_control)
        self.tab_control.add(frame, text=frame_name)
        self.tab_control.select(frame)  # Select the new tab
        
        # Initialize empty selection set for new frame
        self.frame_selections[frame_name] = set()

    def show_tab_menu(self, event):
        """Show context menu for tab operations"""
        # Get the clicked tab
        clicked_tab = self.tab_control.identify(event.x, event.y)
        if not clicked_tab:
            return
        
        # Get the tab number that was clicked
        try:
            tab_index = self.tab_control.index('@%d,%d' % (event.x, event.y))
            frame_name = self.tab_control.tab(tab_index, "text")
            
            # Create context menu
            menu = tk.Menu(self.root, tearoff=0)
            menu.add_command(label="Apply", command=lambda: self.apply_frame(frame_name))
            menu.add_separator()
            menu.add_command(label="Rename", command=lambda: self.rename_frame(frame_name))
            menu.add_command(label="Delete", command=lambda: self.delete_frame(frame_name))
            menu.add_command(label="Copy", command=lambda: self.copy_frame(frame_name))
            menu.add_separator()
            menu.add_command(label="New Frame", command=self.create_new_frame)
            
            # Show the menu at the mouse position
            menu.post(event.x_root, event.y_root)
        except:
            # If we couldn't identify the tab, just show the "New Frame" option
            menu = tk.Menu(self.root, tearoff=0)
            menu.add_command(label="New Frame", command=self.create_new_frame)
            menu.post(event.x_root, event.y_root)

    def get_frame_name_from_tab(self, tab):
        """Get the frame name from a tab index"""
        try:
            return self.tab_control.tab(tab, "text")
        except:
            return None

    def rename_frame(self, frame_name):
        """Rename the current frame"""
        if not frame_name:
            return
            
        new_name = simpledialog.askstring("Rename Frame", "Enter new name:", initialvalue=frame_name)
        if new_name and new_name != frame_name:
            # Update tab name
            for tab in range(self.tab_control.index('end')):
                if self.tab_control.tab(tab, "text") == frame_name:
                    self.tab_control.tab(tab, text=new_name)
                    break
            # Update frames dictionary and selections
            if frame_name in self.frames:
                self.frames[new_name] = self.frames.pop(frame_name)
                self.frame_selections[new_name] = self.frame_selections.pop(frame_name)
                if self.current_frame == frame_name:
                    self.current_frame = new_name

    def delete_frame(self, frame_name):
        """Delete the current frame"""
        if not frame_name:
            return
            
        if frame_name == "Frame 1":
            messagebox.showwarning("Cannot Delete", "Cannot delete Frame 1!")
            return
            
        if messagebox.askyesno("Delete Frame", f"Are you sure you want to delete frame '{frame_name}'?"):
            # Find and remove the tab
            for tab in range(self.tab_control.index('end')):
                if self.tab_control.tab(tab, "text") == frame_name:
                    self.tab_control.forget(tab)
                    break
            # Remove from frames dictionary and selections
            if frame_name in self.frames:
                del self.frames[frame_name]
                del self.frame_selections[frame_name]  # Remove stored selections
                # Switch to default frame if needed
                if self.current_frame == frame_name:
                    self.current_frame = "Frame 1"
                    self.load_frame("Frame 1")
                    self.restore_frame_selections("Frame 1")

    def copy_frame(self, frame_name):
        """Create a copy of the current frame"""
        if not frame_name:
            return
            
        # Create new name with (copy) suffix
        new_name = f"{frame_name} (copy)"
        
        # Create new frame with copied values and selections
        if frame_name in self.frames:
            self.frames[new_name] = self.frames[frame_name].copy()
            self.frame_selections[new_name] = self.frame_selections.get(frame_name, set()).copy()
            # Create new tab
            self.create_frame_tab(new_name)
            # Switch to the new frame
            self.load_frame(new_name)
            self.restore_frame_selections(new_name)

    def create_new_frame(self):
        """Create a new empty frame"""
        new_name = simpledialog.askstring("New Frame", "Enter name for new frame:")
        if new_name:
            # Create new frame with current values
            self.frames[new_name] = [0] * 512  # Initialize with zeros
            # Create new tab
            self.create_frame_tab(new_name)
            # Switch to the new frame
            self.load_frame(new_name)

    def load_frame(self, frame_name, apply_values=False):
        """
        Load a frame's values
        apply_values: If True, send values to DMX device
        """
        if not frame_name or frame_name not in self.frames:
            return
            
        # Update current frame
        self.current_frame = frame_name
        
        # Load the frame's values to the UI only, not to DMX output
        frame_values = self.frames[frame_name].copy()
        
        # Update sliders with frame values, but don't send to DMX
        for fixture in range(self.num_fixtures):
            start_channel = fixture * self.channels_per_fixture
            for channel in range(self.channels_per_fixture):
                # Update slider values only
                self.channel_values[channel].set(frame_values[start_channel + channel])
        
        # Update frame layout visualization
        self.update_frame_layout(frame_values)
        
        # Only send values to DMX if apply_values is True
        if apply_values:
            # Update DMX values and send to output
            self.dmx_values = frame_values.copy()
            self.dmx.send_frame(self.dmx_values)
            # Update DMX layout visualization
            self.update_dmx_layout(self.dmx_values)
            self.dmx_matches_frame = True
            print(f"Applied frame '{frame_name}' values to DMX output")
        else:
            # Set flag to indicate DMX values don't match frame values
            self.dmx_matches_frame = False
            print(f"Loaded frame '{frame_name}' to UI without applying to DMX")

    def update_frame_layout(self, values):
        """Update the frame layout with specified values"""
        for i in range(self.num_fixtures):
            start_idx = i * self.channels_per_fixture
            r = values[start_idx + 1]  # Red channel
            g = values[start_idx + 2]  # Green channel
            b = values[start_idx + 3]  # Blue channel
            w = values[start_idx + 4]  # White channel
            
            # Convert to hex color with proper formatting
            color = f'#{r:02x}{g:02x}{b:02x}'
            
            # Update frame layout fixture color
            self.frame_layout.update_fixture_color(i, color, w)

    def apply_current_values(self):
        """Apply current frame values to DMX output"""
        selected = {i for i, var in enumerate(self.fixture_vars) if var.get()}
        
        if not selected:
            return
        
        for fixture in selected:
            start_idx = fixture * self.channels_per_fixture
            values = []
            for channel in range(self.channels_per_fixture):
                values.append(self.frames[self.current_frame][start_idx + channel])
            
            # Queue the updates through the update manager
            self.update_manager.queue_multi_update(start_idx, values)
            
            # Update DMX values to match frame values
            for channel in range(self.channels_per_fixture):
                self.dmx_values[start_idx + channel] = self.frames[self.current_frame][start_idx + channel]
        
        # Set flag to indicate DMX values match frame values for selected fixtures
        self.dmx_matches_frame = True
        
        print("Applied frame values to DMX output")

    def apply_frame(self, frame_name):
        """Apply the current frame's values to the DMX device, but only for selected fixtures"""
        if frame_name in self.frames:
            # Use the current selection state from the checkboxes
            selected = {i for i, var in enumerate(self.fixture_vars) if var.get()}
            
            if not selected:  # If no fixtures are selected, do nothing
                return
            
            # Only update DMX values for currently selected fixtures
            for fixture in selected:
                start_idx = fixture * self.channels_per_fixture
                values = []
                for channel in range(self.channels_per_fixture):
                    # Copy values from frame to DMX output
                    self.dmx_values[start_idx + channel] = self.frames[frame_name][start_idx + channel]
                    values.append(self.frames[frame_name][start_idx + channel])
                
                # Queue the updates through the update manager
                self.update_manager.queue_multi_update(start_idx, values)

    def update_dmx_layout(self, values):
        """Update the DMX output layout with current values"""
        for i in range(self.num_fixtures):
            start_idx = i * self.channels_per_fixture
            r = values[start_idx + 1]  # Red channel
            g = values[start_idx + 2]  # Green channel
            b = values[start_idx + 3]  # Blue channel
            w = values[start_idx + 4]  # White channel
            
            # Convert to hex color with proper formatting
            color = f'#{r:02x}{g:02x}{b:02x}'
            
            # Update DMX layout fixture color
            self.dmx_layout.update_fixture_color(i, color, w)

    def on_tab_changed(self, event):
        """Handle tab change event"""
        # Save current frame's values and selections
        if self.current_frame in self.frames:
            self.frames[self.current_frame] = self.dmx_values.copy()
            self.frame_selections[self.current_frame] = self.selected_fixtures.copy()
        
        # Get the new frame name
        tab = self.tab_control.select()
        frame_name = self.tab_control.tab(tab, "text")
        
        # Load the new frame's values without sending to DMX
        self.load_frame(frame_name, apply_values=False)
        
        # Restore fixture selections for this frame
        self.restore_frame_selections(frame_name)
        
        print(f"Switched to frame: {frame_name}")

    def restore_frame_selections(self, frame_name):
        """Restore the fixture selections for a frame"""
        # Get the saved selections for this frame, or empty set if none
        saved_selections = self.frame_selections.get(frame_name, set())
        
        # Update checkboxes to match saved selections
        for i, var in enumerate(self.fixture_vars):
            var.set(i in saved_selections)
        
        # Update selected fixtures set
        self.selected_fixtures = saved_selections.copy()

    def update_color_indicators(self):
        """Update the color indicators for all fixtures"""
        for i in range(self.num_fixtures):
            # Get RGB values for this fixture
            start_idx = i * self.channels_per_fixture
            r = self.dmx_values[start_idx + 1]  # Red channel
            g = self.dmx_values[start_idx + 2]  # Green channel
            b = self.dmx_values[start_idx + 3]  # Blue channel
            w = self.dmx_values[start_idx + 4]  # White channel
            
            # Convert to hex color
            color = f'#{r:02x}{g:02x}{b:02x}'
            
            # Calculate white intensity color (black to white)
            white_color = f'#{w:02x}{w:02x}{w:02x}'
            
            # Update the color indicator
            self.color_indicators[i].itemconfig(1, fill=white_color, outline=white_color)
            self.color_indicators[i].itemconfig(2, fill=color, outline=color)
            
            # Update frame layout fixture color
            self.frame_layout.update_fixture_color(i, color, w)

    def on_slider_change(self, channel):
        if not self.dmx.device:
            return

        for fixture in self.selected_fixtures:
            start_address = fixture * self.channels_per_fixture
            channel_value = int(self.channel_values[channel].get())
            dmx_channel = start_address + channel
            
            # Update the frame values
            if self.current_frame in self.frames:
                self.frames[self.current_frame][dmx_channel] = channel_value

            # Only send DMX updates if live track is enabled
            if self.live_track.get():
                self.dmx_values[dmx_channel] = channel_value
                self.update_manager.queue_update(dmx_channel, channel_value)
                self.dmx_matches_frame = True
            else:
                # If not live tracking, mark that DMX no longer matches frame
                self.dmx_matches_frame = False

            # Update layout fixture colors
            start_idx = fixture * self.channels_per_fixture
            r = self.frames[self.current_frame][start_idx + 1]  # Red channel
            g = self.frames[self.current_frame][start_idx + 2]  # Green channel
            b = self.frames[self.current_frame][start_idx + 3]  # Blue channel
            w = self.frames[self.current_frame][start_idx + 4]  # White channel
            
            # Convert to hex color with proper formatting
            color = f'#{r:02x}{g:02x}{b:02x}'
            
            # Update fixture colors in both layouts
            self.frame_layout.update_fixture_color(fixture, color, w)
            if self.live_track.get():
                self.dmx_layout.update_fixture_color(fixture, color, w)

    def update_rgb_from_wheel(self, r, g, b):
        self.channel_values[1].set(r)  # Red
        self.channel_values[2].set(b)  # Blue (swapped with Green)
        self.channel_values[3].set(g)  # Green (swapped with Blue)

        for channel in [1, 2, 3]:
            for fixture in self.selected_fixtures:
                start_address = fixture * self.channels_per_fixture
                channel_value = int(self.channel_values[channel].get())
                dmx_channel = start_address + channel
                self.dmx_values[dmx_channel] = channel_value

                # Update the current frame's values
                if self.current_frame in self.frames:
                    self.frames[self.current_frame][dmx_channel] = channel_value

                # Only send DMX updates if live track is enabled
                if self.live_track.get():
                    self.update_manager.queue_update(dmx_channel, channel_value)

        # Update fixture colors
        for fixture in self.selected_fixtures:
            start_idx = fixture * self.channels_per_fixture
            r = self.dmx_values[start_idx + 1]  # Red channel
            g = self.dmx_values[start_idx + 2]  # Green channel
            b = self.dmx_values[start_idx + 3]  # Blue channel
            w = self.dmx_values[start_idx + 4]  # White channel
            
            # Convert to hex color with proper formatting
            color = f'#{r:02x}{g:02x}{b:02x}'
            
            # Update fixture colors in both layouts
            self.frame_layout.update_fixture_color(fixture, color, w)
            if self.live_track.get():
                self.dmx_layout.update_fixture_color(fixture, color, w)

    def check_connection(self):
        """Periodically check if the device is still connected"""
        if not self.dmx.device:
            print("Device disconnected, attempting to reconnect...")
            if self.dmx.reconnect():
                print("Device reconnected successfully")
                # Resend current values after reconnection
                self.resend_all_values()
            else:
                print("Reconnection failed, please check the USB connection")
        
        # Schedule next check
        self.root.after(1000, self.check_connection)
        
    def resend_all_values(self):
        """Resend all current values after reconnection"""
        # Queue all current values through the update manager
        for i in range(0, len(self.dmx_values), self.channels_per_fixture):
            values = self.dmx_values[i:i + self.channels_per_fixture]
            self.update_manager.queue_multi_update(i, values)

    def cleanup(self):
        if self.dmx:
            self.dmx.cleanup()

    def on_fixture_click(self, fixture_num):
        """Handle fixture click in the stage layout"""
        # Update sliders with the fixture's values
        start_idx = fixture_num * self.channels_per_fixture
        for i in range(self.channels_per_fixture):
            value = self.dmx_values[start_idx + i]
            self.channel_values[i].set(value)

    def update_selected_fixtures(self):
        """Update the set of selected fixtures based on checkbox states"""
        self.selected_fixtures = {i for i, var in enumerate(self.fixture_vars) if var.get()}

    def on_tab_press(self, event):
        """Handle tab press for reordering"""
        # Get the current tab
        current_tab = self.tab_control.select()
        if current_tab:
            try:
                self.drag_start = event.x
                self.drag_tab = current_tab
                self.drag_tab_index = self.tab_control.index(current_tab)
                self.drag_tab_name = self.tab_control.tab(current_tab, "text")
            except:
                self.drag_start = None
                self.drag_tab = None
                self.drag_tab_index = None
                self.drag_tab_name = None

    def on_tab_drag(self, event):
        """Handle tab drag for reordering"""
        if hasattr(self, 'drag_start') and hasattr(self, 'drag_tab') and hasattr(self, 'drag_tab_index'):
            if self.drag_tab is None or self.drag_tab_index is None or self.drag_tab_name is None:
                return
                
            try:
                # Get the tab at the current mouse position
                target_index = self.tab_control.index('@%d,%d' % (event.x, event.y))
                if target_index != self.drag_tab_index and target_index >= 0:
                    # Get the tab widget
                    tab = self.tab_control.select()
                    
                    # Insert the tab at the new position
                    self.tab_control.insert(target_index, tab)
                    
                    # Update drag state
                    self.drag_tab_index = target_index
                    self.drag_start = event.x
            except:
                pass

    def on_tab_release(self, event):
        """Handle tab release after reordering"""
        if hasattr(self, 'drag_start'):
            delattr(self, 'drag_start')
        if hasattr(self, 'drag_tab'):
            delattr(self, 'drag_tab')
        if hasattr(self, 'drag_tab_index'):
            delattr(self, 'drag_tab_index')
        if hasattr(self, 'drag_tab_name'):
            delattr(self, 'drag_tab_name')

    def sync_layouts(self):
        """Synchronize both layouts when positions or angles change"""
        for i in range(self.num_fixtures):
            if i in self.shared_fixture_positions:
                pos = self.shared_fixture_positions[i]
                angle = self.shared_fixture_angles[i]
                self.frame_layout.update_fixture_position(i, pos[0], pos[1], angle)
                self.dmx_layout.update_fixture_position(i, pos[0], pos[1], angle)

    def update_dmx_output(self):
        """Process DMX updates and handle fade operations"""
        updated, new_values = self.update_manager.process_updates(self.dmx_values)
        if updated and new_values:
            self.dmx_values = new_values

            # Update the DMX layout if not in a fade and callback is set
            fade_in_progress = self._fade_in_progress and self._fade_state is not None
            if not fade_in_progress and self.update_manager.on_frame_sent:
                self.update_manager.on_frame_sent(new_values)

        self.root.after(10, self.update_dmx_output)

    def toggle_select_all(self):
        """Toggle selection state of all fixtures"""
        # Check if all fixtures are currently selected
        all_selected = len(self.selected_fixtures) == self.num_fixtures
        
        # Toggle selection state
        for i, var in enumerate(self.fixture_vars):
            var.set(not all_selected)
        
        # Update selected fixtures set
        self.update_selected_fixtures()

    def clear_selection(self):
        """Clear all fixture selections"""
        for var in self.fixture_vars:
            var.set(False)
        self.update_selected_fixtures()

    def fade_in_values(self):
        """Fade in the selected fixtures from current to target values"""
        if not self.selected_fixtures:
            return  # No fixtures selected
            
        # Get fade time in seconds
        fade_time = self.fade_time.get()
        
        # Calculate number of steps (10Hz update rate)
        steps = int(fade_time * 10)  # 10 steps per second
        if steps < 1:
            steps = 1
            
        print(f"Starting fade over {fade_time} seconds with {steps} steps")
            
        # Store start values (current DMX output) and target values (from current frame)
        start_values = {}
        target_values = {}
        has_changes = False  # Flag to track if there are any changes to fade
        
        for fixture in self.selected_fixtures:
            start_idx = fixture * self.channels_per_fixture
            
            # Get current DMX values from actual DMX output
            start_values[fixture] = self.dmx_values[start_idx:start_idx + self.channels_per_fixture].copy()
            
            # Get target values from current frame
            target_values[fixture] = self.frames[self.current_frame][start_idx:start_idx + self.channels_per_fixture].copy()
            
            # Check if there are any differences between start and target values
            for i in range(self.channels_per_fixture):
                if abs(start_values[fixture][i] - target_values[fixture][i]) > 0:
                    has_changes = True
                    
                    # Log significant changes for debugging
                    if i in [0, 1, 2, 3, 4]:  # Only log important channels (dimmer, RGB, white)
                        ch_name = self.channel_labels[i]
                        delta = target_values[fixture][i] - start_values[fixture][i]
                        print(f"Fixture {fixture+1}, {ch_name}: {start_values[fixture][i]} → {target_values[fixture][i]}, Delta: {delta}")
            
            # Log the RGB values for debugging
            print(f"Fixture {fixture+1} start: R:{start_values[fixture][1]} G:{start_values[fixture][2]} B:{start_values[fixture][3]} W:{start_values[fixture][4]}")
            print(f"Fixture {fixture+1} target: R:{target_values[fixture][1]} G:{target_values[fixture][2]} B:{target_values[fixture][3]} W:{target_values[fixture][4]}")
        
        # If there are no changes to make, just return
        if not has_changes:
            print("No changes detected between DMX output and frame values. Skipping fade.")
            return
            
        # Start the fade
        self.start_fade(start_values, target_values, list(self.selected_fixtures), steps)
        
        # Disable fade button during fade
        self.fade_button.config(state="disabled")

    def start_fade(self, start_values, target_values, selected_fixtures, steps):
        """Start a fade operation"""
        # Store fade state
        self._fade_in_progress = True
        self._fade_state = {
            "start_values": start_values,
            "target_values": target_values,
            "selected_fixtures": selected_fixtures,
            "step": 0,
            "steps": steps,
            "last_update_time": time.time()
        }
        
        # Disable automatic DMX layout updates
        self._original_callback = self.update_manager.on_frame_sent
        self.update_manager.on_frame_sent = None
        
        # Start the fade loop
        self._perform_fade_step()

    def _perform_fade_step(self):
        """Perform a single step of the fade operation"""
        if not self._fade_in_progress or not self._fade_state:
            return
            
        fade = self._fade_state
        current_step = fade["step"]
        total_steps = fade["steps"]
        
        if current_step > total_steps:
            # Fade complete
            print(f"Fade complete after {current_step} steps")
            self.fade_button.config(state="normal")
            self._fade_in_progress = False
            self._fade_state = None
            
            # Restore the original callback
            self.update_manager.on_frame_sent = self._original_callback
            return
        
        # Calculate time between steps for accurate timing
        now = time.time()
        time_since_last = now - fade["last_update_time"]
        step_time = 0.1  # 100ms per step (10Hz)
        
        if time_since_last < step_time:
            # Not time for next step yet, schedule another check
            self.root.after(int((step_time - time_since_last) * 1000), self._perform_fade_step)
            return
            
        # It's time for the next step
        fade["last_update_time"] = now
        
        # Process this step
        self._process_fade_step(current_step)
        
        # Increment step and schedule next iteration
        fade["step"] = current_step + 1
        self.root.after(int(step_time * 1000), self._perform_fade_step)

    def _process_fade_step(self, step):
        """Process a specific step of the fade operation"""
        if not self._fade_state:
            return
            
        fade = self._fade_state
        start_values = fade["start_values"]
        target_values = fade["target_values"]
        selected_fixtures = fade["selected_fixtures"]
        total_steps = fade["steps"]
        
        # Debug print for tracking
        if step % 5 == 0 or step == total_steps:  # Print every 5 steps and the final step
            print(f"Processing fade step {step} of {total_steps}")
            
        # Process each selected fixture
        for fixture in selected_fixtures:
            # Get start and target values for this fixture
            fixture_start = start_values[fixture]
            fixture_target = target_values[fixture]
            
            # Calculate values for current step (direct linear interpolation)
            current_values = []
            for i in range(len(fixture_start)):
                # Linear interpolation between start and target
                if step >= total_steps:  # Final step or beyond
                    value = fixture_target[i]
                else:
                    # Calculate percentage of completion (0.0 to 1.0)
                    percentage = step / total_steps
                    # Linear interpolation: start + percentage * (target - start)
                    value = fixture_start[i] + (percentage * (fixture_target[i] - fixture_start[i]))
                # Ensure value is valid (0-255) and an integer
                value = max(0, min(255, int(round(value))))
                current_values.append(value)
            
            # Update DMX values for this fixture
            start_idx = fixture * self.channels_per_fixture
            for j, value in enumerate(current_values):
                self.dmx_values[start_idx + j] = value
            
            # Queue the updates through the update manager
            self.update_manager.queue_multi_update(start_idx, current_values)
            
            # Get RGB values for this fixture for visualization
            r = current_values[1]  # Red channel
            g = current_values[2]  # Green channel
            b = current_values[3]  # Blue channel
            w = current_values[4]  # White channel
            color = f'#{r:02x}{g:02x}{b:02x}'
            
            # Debug print for a sample fixture
            if fixture == selected_fixtures[0] and (step % 5 == 0 or step == total_steps):
                print(f"  Step {step}: Fixture {fixture+1} - RGB({r},{g},{b}) W:{w} - Color: {color}")
            
            # DIRECT update to DMX layout visualization
            try:
                # Update DMX layout (output visualization)
                if fixture in self.dmx_layout.fixture_positions:
                    self.dmx_layout.fixture_colors[fixture] = color
                    white_color = f'#{w:02x}{w:02x}{w:02x}'
                    for item in self.dmx_layout.find_withtag(f'fixture_{fixture}'):
                        if self.dmx_layout.type(item) == 'rectangle':
                            self.dmx_layout.itemconfig(item, fill=white_color)
                        elif self.dmx_layout.type(item) == 'polygon':
                            self.dmx_layout.itemconfig(item, fill=color)
            except Exception as e:
                print(f"Error updating DMX layout: {e}")
        
        # Force UI update to ensure visualization is updated
        self.root.update()

    def _queue_fade_step(self, step):
        """Legacy method - will be called from update_dmx_output if not using new fade system"""
        # Call the new method instead
        if self._fade_state:
            self._process_fade_step(step)

    def periodic_live_track_update(self):
        if self.live_track.get():
            for fixture in self.selected_fixtures:
                start_idx = fixture * self.channels_per_fixture
                values = [self.dmx_values[start_idx + ch] for ch in range(self.channels_per_fixture)]
                self.update_manager.queue_multi_update(start_idx, values)
        self.root.after(50, self.periodic_live_track_update)  # 20Hz, safe for UI, DMX throttled to 10Hz

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

if __name__ == "__main__":
    root = tk.Tk()
    app = DMXController(root)
    root.protocol("WM_DELETE_WINDOW", lambda: (app.cleanup(), root.destroy()))
    root.mainloop() 