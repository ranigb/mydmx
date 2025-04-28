import tkinter as tk
from tkinter import ttk
from tkinter import simpledialog, messagebox
import math

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