import tkinter as tk
from tkinter import ttk
from tkinter import simpledialog, messagebox
import math
import time
from communication import UDMX, DMXUpdateManager
from fixture import Fixture

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
            
            # Calculate HSV values
            h = angle / 360.0  # Hue from 0 to 1
            s = 1.0  # Full saturation
            v = 1.0  # Full value
            
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
            # Calculate angle (standard mathematical angle, 0 at right, increasing counterclockwise)
            angle = math.degrees(math.atan2(-dy, dx))  # Negative dy because y increases downward
            if angle < 0:
                angle += 360
                
            # Calculate dimmer value based on distance (0 at center, 255 at edge)
            dimmer = int((distance / self.radius) * 255)
            
            # Calculate HSV values
            h = angle / 360.0  # Hue from 0 to 1
            s = 1.0  # Full saturation
            v = 1.0  # Full value
            
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
            
            # Update RGB sliders and dimmer
            if hasattr(self, 'callback'):
                self.callback(r, g, b, dimmer)

class StageLayout(tk.Canvas):
    def __init__(self, parent, fixtures, positions=None, angles=None, 
                 sync_callback=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.fixtures = fixtures  # List of Fixture objects
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
        for i, fixture in enumerate(self.fixtures):
            # Calculate position if not already set
            if i not in self.fixture_positions:
                row = i // 6
                col = i % 6
                x = 65 + col * 75  # Increased spacing between columns
                y = 60 if row == 0 else 190  # Increased vertical separation between rows
                self.fixture_positions[i] = (x, y)
                fixture.set_position(x, y)
                
            if i not in self.fixture_angles:
                # Set initial angle (90 for top row pointing down, 270 for bottom row pointing up)
                angle = 90 if i < 6 else 270
                self.fixture_angles[i] = angle
                fixture.set_angle(angle)
                
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
                        text=str(self.fixtures[i].fixture_id), fill='white', tags=f'fixture_{i}')

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
            self.fixtures[self.rotating].set_angle(new_angle)
            
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
        self.create_text(x + num_dx, y + num_dy, 
                        text=str(self.fixtures[fixture_num].fixture_id), 
                        fill='white', tags=f'fixture_{fixture_num}')
                    
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
            self.fixtures[self.dragging].set_position(new_x, new_y)
            
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
            
            # Force update of the canvas
            self.update_idletasks()

    def update_fixture_position(self, fixture_num, x, y, angle):
        """Update a fixture's position and angle"""
        # Remove old fixture elements
        for item in self.find_withtag(f'fixture_{fixture_num}'):
            self.delete(item)
            
        # Create new fixture at updated position
        color = self.fixture_colors.get(fixture_num, 'gray')
        self.create_fixture(fixture_num, x, y, angle, color)

class MasterDimmer(ttk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        
        # Create label
        ttk.Label(self, text="Master Dimmer").grid(row=0, column=0, pady=(0, 5))
        
        # Create slider
        self.dimmer_var = tk.DoubleVar(value=1.0)
        self.slider = ttk.Scale(
            self,
            from_=0.0,
            to=1.0,
            orient="vertical",
            variable=self.dimmer_var,
            command=self._on_slider_change
        )
        self.slider.grid(row=1, column=0, padx=5, pady=5)
        
        # Create value label
        self.value_label = ttk.Label(self, text="100%")
        self.value_label.grid(row=2, column=0, pady=(5, 0))
        
        # Initialize callback
        self.callback = None
        
    def _on_slider_change(self, value):
        """Handle slider changes and call the callback if set"""
        try:
            # Convert slider value to float
            dimmer_value = float(value)
            
            # Update label with percentage
            percentage = int(dimmer_value * 100)
            self.value_label.configure(text=f"{percentage}%")
            
            # Call the callback if set
            if self.callback:
                self.callback(dimmer_value)
        except ValueError:
            pass
            
    def get_value(self):
        """Get the current dimmer value"""
        return self.dimmer_var.get()
        
    def set_value(self, value):
        """Set the dimmer value"""
        self.dimmer_var.set(value)
        self._on_slider_change(value) 

class DMXControllerGUI(ttk.Frame):
    def __init__(self, parent, dmx_controller):
        super().__init__(parent)
        self.dmx_controller = dmx_controller
        self.create_widgets()
        
    def create_widgets(self):
        # Create main container
        main_frame = ttk.Frame(self)
        main_frame.grid(row=0, column=0, padx=10, pady=5, sticky="nsew")
        
        # Create tab control
        self.tab_control = ttk.Notebook(main_frame)
        self.tab_control.grid(row=0, column=0, columnspan=3, sticky="ew")
        
        # Bind events for tab control
        self.tab_control.bind("<Button-3>", self.dmx_controller.show_tab_menu)
        self.tab_control.bind("<Button-1>", self.dmx_controller.on_tab_press)
        self.tab_control.bind("<B1-Motion>", self.dmx_controller.on_tab_drag)
        self.tab_control.bind("<ButtonRelease-1>", self.dmx_controller.on_tab_release)
        self.tab_control.bind("<<NotebookTabChanged>>", self.dmx_controller.on_tab_changed)
        
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
        self.frame_layout = StageLayout(frame_stage_frame, self.dmx_controller.fixtures, 
                                      width=500, height=250, bg='#333333',
                                      positions=self.dmx_controller.shared_fixture_positions,
                                      angles=self.dmx_controller.shared_fixture_angles,
                                      sync_callback=self.dmx_controller.sync_layouts)
        self.frame_layout.grid(row=0, column=0, padx=5, pady=5)
        
        self.dmx_layout = StageLayout(dmx_stage_frame, self.dmx_controller.fixtures, 
                                    width=500, height=250, bg='#333333',
                                    positions=self.dmx_controller.shared_fixture_positions,
                                    angles=self.dmx_controller.shared_fixture_angles,
                                    sync_callback=self.dmx_controller.sync_layouts)
        self.dmx_layout.grid(row=0, column=0, padx=5, pady=5)
        
        # Add master dimmer next to DMX output
        self.master_dimmer = MasterDimmer(dmx_stage_frame)
        self.master_dimmer.grid(row=0, column=1, padx=5, pady=5, sticky="n")
        self.master_dimmer.callback = self.dmx_controller.on_master_dimmer_change
        
        # Set callbacks
        self.frame_layout.callback = self.dmx_controller.on_fixture_click
        self.dmx_layout.callback = self.dmx_controller.on_fixture_click
        
        # Create left frame for fixture selection and configuration
        left_frame = ttk.Frame(main_frame)
        left_frame.grid(row=1, column=1, padx=5, pady=5, sticky="nsew")
        
        # Create fixture configuration frame
        fixture_config_frame = ttk.LabelFrame(left_frame, text="Fixture Configuration", padding="10")
        fixture_config_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        
        # Add Configure Fixtures button
        self.configure_button = ttk.Button(
            fixture_config_frame,
            text="Configure Fixtures",
            command=self.dmx_controller.show_fixture_config
        )
        self.configure_button.grid(row=0, column=0, padx=5, pady=5)
        
        # Create fixture selection frame
        fixture_frame = ttk.LabelFrame(left_frame, text="Fixture Selection", padding="10")
        fixture_frame.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")
        self.fixture_frame = fixture_frame  # Store reference to fixture frame
        
        # Add selection buttons at the top of the fixture frame
        self.selection_buttons_frame = ttk.Frame(fixture_frame)
        self.selection_buttons_frame.grid(row=0, column=0, columnspan=3, padx=5, pady=5, sticky="ew")
        
        # Add Select All button
        self.select_all_button = ttk.Button(
            self.selection_buttons_frame, 
            text="Select All", 
            command=self.dmx_controller.toggle_select_all
        )
        self.select_all_button.grid(row=0, column=0, padx=5, pady=5)
        
        # Add Clear Selection button
        self.clear_selection_button = ttk.Button(
            self.selection_buttons_frame, 
            text="Clear Selection", 
            command=self.dmx_controller.clear_selection
        )
        self.clear_selection_button.grid(row=0, column=1, padx=5, pady=5)
        
        # Create fixture checkbuttons and color indicators
        self.fixture_vars = []
        self.color_indicators = []
        self.create_fixture_controls(fixture_frame)
        
        # Create control buttons frame BELOW fixture selection
        control_buttons_frame = ttk.Frame(left_frame)
        control_buttons_frame.grid(row=2, column=0, padx=5, pady=5, sticky="ew")

        # Add Apply button
        self.apply_button = ttk.Button(
            control_buttons_frame, 
            text="Apply", 
            command=self.dmx_controller.apply_current_values
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
            command=self.dmx_controller.fade_in_values
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
        self.channel_frame = channel_frame  # Store reference to channel frame

        # Create sliders for each channel
        self.channel_values = []
        self.create_channel_controls(channel_frame)
        
        # Create color wheel frame
        color_frame = ttk.LabelFrame(right_frame, text="Color Wheel", padding="10")
        color_frame.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")
        
        # Create color wheel
        self.color_wheel = ColorWheel(color_frame, size=200)
        self.color_wheel.grid(row=0, column=0, padx=5, pady=5)
        self.color_wheel.callback = self.dmx_controller.update_rgb_from_wheel
        
        # Configure grid weights
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(1, weight=1)
        main_frame.grid_columnconfigure(0, weight=3)
        main_frame.grid_columnconfigure(1, weight=1)
        main_frame.grid_columnconfigure(2, weight=1)

    def create_fixture_controls(self, parent):
        """Create fixture selection controls"""
        # Clear existing controls except the selection buttons frame
        for widget in parent.winfo_children():
            if widget != self.selection_buttons_frame:
                widget.destroy()
        
        self.fixture_vars = []
        self.color_indicators = []
        
        # Create controls for each fixture
        for i, fixture in enumerate(self.dmx_controller.fixtures):
            # Create frame for each fixture
            fixture_item = ttk.Frame(parent)
            fixture_item.grid(row=i//3 + 1, column=i%3, padx=5, pady=2)  # Start from row 1 to leave space for buttons
            
            # Create checkbutton
            var = tk.BooleanVar()
            self.fixture_vars.append(var)
            ttk.Checkbutton(
                fixture_item, 
                text=f"Fixture {fixture.fixture_id}",
                variable=var,
                command=self.dmx_controller.update_selected_fixtures
            ).grid(row=0, column=0, padx=2)
            
            # Create color indicator
            color_canvas = tk.Canvas(fixture_item, width=24, height=24, bg='white', highlightthickness=0)
            color_canvas.grid(row=0, column=1, padx=2)
            color_canvas.create_rectangle(0, 0, 24, 24, fill='black', outline='black')
            color_canvas.create_oval(4, 4, 20, 20, fill='black', outline='black')
            self.color_indicators.append(color_canvas)

    def create_channel_controls(self, parent):
        """Create channel control sliders"""
        # Clear existing controls
        for widget in parent.winfo_children():
            widget.destroy()
        
        self.channel_values = []
        
        # Get the maximum number of channels from fixtures
        max_channels = max((f.num_channels for f in self.dmx_controller.fixtures), default=8)
        
        # Create sliders for each channel in the correct order
        for i in range(max_channels):
            label = self.dmx_controller.default_channel_labels[i] if i < len(self.dmx_controller.default_channel_labels) else f"Channel {i+1}"
            ttk.Label(parent, text=label).grid(row=i, column=0, padx=5)
            value = tk.IntVar()
            self.channel_values.append(value)
            
            def create_slider_command(channel):
                def slider_command(val):
                    try:
                        int_val = int(float(val))
                        self.channel_values[channel].set(int_val)
                        self.dmx_controller.on_slider_change(channel)
                    except ValueError:
                        pass
                return slider_command
            
            slider = ttk.Scale(
                parent,
                from_=0,
                to=255,
                orient="horizontal",
                variable=value,
                command=create_slider_command(i)
            )
            slider.grid(row=i, column=1, padx=5, pady=2, sticky="ew")
            value_label = ttk.Label(parent, textvariable=value)
            value_label.grid(row=i, column=2, padx=5) 