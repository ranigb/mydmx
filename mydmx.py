import tkinter as tk
from tkinter import ttk
from tkinter import simpledialog, messagebox
import time
from communication import UDMX, DMXUpdateManager
from gui import DMXControllerGUI
from fixture import Fixture

class DMXController:
    def __init__(self, root):
        self.root = root
        self.root.title("DMX Light Controller (uDMX)")
        
        # DMX Configuration
        self.fixtures = []  # List of Fixture objects
        
        # Define channel mappings (0-based index)
        self.CHANNEL_DIMMER = 0  # Channel 1
        self.CHANNEL_RED = 1     # Channel 2
        self.CHANNEL_GREEN = 2   # Channel 3
        self.CHANNEL_BLUE = 3    # Channel 4
        self.CHANNEL_WHITE = 4    # Channel 5
        self.CHANNEL_STROBE = 5   # Channel 6
        self.CHANNEL_CHASER = 6   # Channel 7
        self.CHANNEL_NA = 7       # Channel 8
        
        # Channel labels (default for RGB fixtures)
        self.default_channel_labels = [
            "Dimmer",  # Channel 1
            "Red",     # Channel 2
            "Green",   # Channel 3
            "Blue",    # Channel 4
            "White",   # Channel 5
            "Strobe",  # Channel 6
            "Chasser", # Channel 7
            "NA"       # Channel 8
        ]
        
        # Create some default fixtures
        for i in range(12):  # Create 12 default fixtures
            fixture = Fixture(
                fixture_id=i+1,
                start_address=i*8+1,  # Each fixture starts 8 channels after the previous
                num_channels=8,  # Default 8 channels per fixture
                position=(0, 0),  # Will be set by layout
                angle=0  # Will be set by layout
            )
            self.fixtures.append(fixture)
        self.selected_fixtures = set()  # To store selected fixtures
        self.dmx_values = [0] * 512  # Store all DMX values
        self.master_dimmer = 1.0  # Master dimmer value (0.0 to 1.0)
        
        # Frame management
        self.frames = {}  # Dictionary to store frame values
        self.current_frame = None  # Initialize current_frame
        
        # Initialize DMX update manager
        self.dmx = UDMX()
        self.update_manager = DMXUpdateManager(self.dmx)
        self.update_manager.on_frame_sent = self.update_dmx_layout
        
        # Add shared layout state
        self.shared_fixture_positions = {}
        self.shared_fixture_angles = {}
        
        # DMX output state
        self.pending_changes = False  # Flag to track if changes need to be sent
        self.last_dmx_send = 0  # Time of last DMX send
        
        # Add dictionary to store selected fixtures for each frame
        self.frame_selections = {}  # Dictionary to store selected fixtures for each frame
        
        # Create GUI
        self.gui = DMXControllerGUI(root, self)
        self.gui.grid(row=0, column=0, sticky="nsew")  # Make GUI fill the window
        
        # Configure root window grid
        root.grid_rowconfigure(0, weight=1)
        root.grid_columnconfigure(0, weight=1)
        
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
        self.frame_layout = StageLayout(frame_stage_frame, self.fixtures, 
                                      width=500, height=250, bg='#333333',
                                      positions=self.shared_fixture_positions,
                                      angles=self.shared_fixture_angles,
                                      sync_callback=self.sync_layouts)
        self.frame_layout.grid(row=0, column=0, padx=5, pady=5)
        
        self.dmx_layout = StageLayout(dmx_stage_frame, self.fixtures, 
                                    width=500, height=250, bg='#333333',
                                    positions=self.shared_fixture_positions,
                                    angles=self.shared_fixture_angles,
                                    sync_callback=self.sync_layouts)
        self.dmx_layout.grid(row=0, column=0, padx=5, pady=5)
        
        # Add master dimmer next to DMX output
        self.master_dimmer = MasterDimmer(dmx_stage_frame)
        self.master_dimmer.grid(row=0, column=1, padx=5, pady=5, sticky="n")
        self.master_dimmer.callback = self.on_master_dimmer_change
        
        # Set callbacks
        self.frame_layout.callback = self.on_fixture_click
        self.dmx_layout.callback = self.on_fixture_click
        
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
            command=self.show_fixture_config
        )
        self.configure_button.grid(row=0, column=0, padx=5, pady=5)
        
        # Create fixture selection frame
        fixture_frame = ttk.LabelFrame(left_frame, text="Fixture Selection", padding="10")
        fixture_frame.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")
        self.fixture_frame = fixture_frame  # Store reference to fixture frame
        
        # Add selection buttons at the top of the fixture frame
        selection_buttons_frame = ttk.Frame(fixture_frame)
        selection_buttons_frame.grid(row=0, column=0, columnspan=3, padx=5, pady=5, sticky="ew")
        
        # Add Select All button
        self.select_all_button = ttk.Button(
            selection_buttons_frame, 
            text="Select All", 
            command=self.toggle_select_all
        )
        self.select_all_button.grid(row=0, column=0, padx=5, pady=5)
        
        # Add Clear Selection button
        self.clear_selection_button = ttk.Button(
            selection_buttons_frame, 
            text="Clear Selection", 
            command=self.clear_selection
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
        self.channel_frame = channel_frame  # Store reference to channel frame

        # Create sliders for each channel
        self.channel_values = []
        self.create_channel_controls(channel_frame)
        
        # Create color wheel frame
        color_frame = ttk.LabelFrame(right_frame, text="Color Wheel", padding="10")
        color_frame.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")

    def create_fixture_controls(self, parent):
        """Create fixture selection controls"""
        # Clear existing controls
        for widget in parent.winfo_children():
            if widget not in [self.select_all_button, self.clear_selection_button]:
                widget.destroy()
        
        self.fixture_vars = []
        self.color_indicators = []
        
        # Create controls for each fixture
        for i, fixture in enumerate(self.fixtures):
            # Create frame for each fixture
            fixture_item = ttk.Frame(parent)
            fixture_item.grid(row=i//3 + 2, column=i%3, padx=5, pady=2)  # Start from row 2 to leave space for buttons
            
            # Create checkbutton
            var = tk.BooleanVar()
            self.fixture_vars.append(var)
            ttk.Checkbutton(
                fixture_item, 
                text=f"Fixture {fixture.fixture_id}",
                variable=var,
                command=self.update_selected_fixtures
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
        max_channels = max((f.num_channels for f in self.fixtures), default=8)
        
        # Create sliders for each channel in the correct order
        for i in range(max_channels):
            label = self.default_channel_labels[i] if i < len(self.default_channel_labels) else f"Channel {i+1}"
            ttk.Label(parent, text=label).grid(row=i, column=0, padx=5)
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

    def show_fixture_config(self):
        """Show fixture configuration dialog"""
        # Create configuration window
        config_window = tk.Toplevel(self.root)
        config_window.title("Configure Fixtures")
        config_window.geometry("400x500")
        
        # Create scrollable frame
        canvas = tk.Canvas(config_window)
        scrollbar = ttk.Scrollbar(config_window, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Add fixtures
        fixture_frames = []
        for i, fixture in enumerate(self.fixtures):
            frame = ttk.LabelFrame(scrollable_frame, text=f"Fixture {fixture.fixture_id}")
            frame.grid(row=i, column=0, padx=5, pady=5, sticky="ew")
            
            # Start address
            ttk.Label(frame, text="Start Address:").grid(row=0, column=0, padx=5, pady=2)
            start_var = tk.IntVar(value=fixture.start_address)
            start_entry = ttk.Entry(frame, textvariable=start_var, width=10)
            start_entry.grid(row=0, column=1, padx=5, pady=2)
            
            # Number of channels
            ttk.Label(frame, text="Channels:").grid(row=1, column=0, padx=5, pady=2)
            channels_var = tk.IntVar(value=fixture.num_channels)
            channels_entry = ttk.Entry(frame, textvariable=channels_var, width=10)
            channels_entry.grid(row=1, column=1, padx=5, pady=2)
            
            fixture_frames.append((frame, start_var, channels_var))
        
        # Add buttons
        button_frame = ttk.Frame(config_window)
        button_frame.grid(row=1, column=0, padx=5, pady=5)
        
        ttk.Button(
            button_frame,
            text="Add Fixture",
            command=lambda: self.add_fixture_config(fixture_frames, scrollable_frame)
        ).grid(row=0, column=0, padx=5)
        
        ttk.Button(
            button_frame,
            text="Save",
            command=lambda: self.save_fixture_config(fixture_frames, config_window)
        ).grid(row=0, column=1, padx=5)
        
        # Pack the scrollable area
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        config_window.grid_rowconfigure(0, weight=1)
        config_window.grid_columnconfigure(0, weight=1)

    def add_fixture_config(self, fixture_frames, parent):
        """Add a new fixture configuration"""
        fixture_id = len(self.fixtures) + 1
        frame = ttk.LabelFrame(parent, text=f"Fixture {fixture_id}")
        frame.grid(row=len(fixture_frames), column=0, padx=5, pady=5, sticky="ew")
        
        # Start address
        ttk.Label(frame, text="Start Address:").grid(row=0, column=0, padx=5, pady=2)
        start_var = tk.IntVar(value=1)
        start_entry = ttk.Entry(frame, textvariable=start_var, width=10)
        start_entry.grid(row=0, column=1, padx=5, pady=2)
        
        # Number of channels
        ttk.Label(frame, text="Channels:").grid(row=1, column=0, padx=5, pady=2)
        channels_var = tk.IntVar(value=8)
        channels_entry = ttk.Entry(frame, textvariable=channels_var, width=10)
        channels_entry.grid(row=1, column=1, padx=5, pady=2)
        
        fixture_frames.append((frame, start_var, channels_var))
        
        # Calculate center position of the canvas
        canvas_width = self.frame_layout.winfo_width()
        canvas_height = self.frame_layout.winfo_height()
        center_x = canvas_width // 2
        center_y = canvas_height // 2
        
        # Create a temporary fixture for the layouts
        temp_fixture = Fixture(
            fixture_id=fixture_id,
            start_address=start_var.get(),
            num_channels=channels_var.get(),
            position=(center_x, center_y),
            angle=0
        )
        self.fixtures.append(temp_fixture)
        
        # Update layouts with the new fixture
        self.frame_layout.fixtures = self.fixtures
        self.dmx_layout.fixtures = self.fixtures
        
        # Recreate fixtures in layouts
        self.frame_layout.delete("all")
        self.frame_layout.create_grid()
        self.frame_layout.create_fixtures()
        
        self.dmx_layout.delete("all")
        self.dmx_layout.create_grid()
        self.dmx_layout.create_fixtures()
        
        # Update fixture colors in layouts
        for i, fixture in enumerate(self.fixtures):
            start_idx = fixture.start_address - 1
            r = self.dmx_values[start_idx + 1] if start_idx + 1 < len(self.dmx_values) else 0
            g = self.dmx_values[start_idx + 2] if start_idx + 2 < len(self.dmx_values) else 0
            b = self.dmx_values[start_idx + 3] if start_idx + 3 < len(self.dmx_values) else 0
            w = self.dmx_values[start_idx + 4] if start_idx + 4 < len(self.dmx_values) else 0
            
            color = f'#{r:02x}{g:02x}{b:02x}'
            
            self.frame_layout.update_fixture_color(i, color, w)
            self.dmx_layout.update_fixture_color(i, color, w)
        
        # Get the canvas that contains the scrollable frame
        canvas = parent.master
        
        # Schedule scrolling after the frame is added and layout is updated
        def scroll_to_bottom():
            # Update the scroll region to include the new frame
            canvas.configure(scrollregion=canvas.bbox("all"))
            # Scroll to the bottom to show the new fixture
            canvas.yview_moveto(1.0)
            # Set focus to the start address entry
            start_entry.focus_set()
        
        # Schedule the scroll after the frame is added and layouts are updated
        self.root.after(50, scroll_to_bottom)

    def save_fixture_config(self, fixture_frames, window):
        """Save fixture configuration"""
        # Create new fixtures list
        new_fixtures = []
        for i, (frame, start_var, channels_var) in enumerate(fixture_frames):
            try:
                start = start_var.get()
                channels = channels_var.get()
                
                # Validate values
                if start < 1 or start > 512:
                    raise ValueError("Start address must be between 1 and 512")
                if channels < 1 or channels > 512:
                    raise ValueError("Number of channels must be between 1 and 512")
                if start + channels - 1 > 512:
                    raise ValueError("Fixture exceeds DMX universe (512 channels)")
                
                # Check for overlapping fixtures
                for existing in new_fixtures:
                    if (start <= existing.start_address + existing.num_channels - 1 and
                        start + channels - 1 >= existing.start_address):
                        raise ValueError(f"Fixture {i+1} overlaps with Fixture {existing.fixture_id}")
                
                # Create new fixture
                fixture = Fixture(
                    fixture_id=i+1,
                    start_address=start,
                    num_channels=channels,
                    position=self.fixtures[i].position if i < len(self.fixtures) else (0, 0),
                    angle=self.fixtures[i].angle if i < len(self.fixtures) else 0
                )
                new_fixtures.append(fixture)
                
            except ValueError as e:
                messagebox.showerror("Configuration Error", str(e))
                return
        
        # Update fixtures
        self.fixtures = new_fixtures
        
        # Update UI
        self.create_fixture_controls(self.fixture_frame)
        self.create_channel_controls(self.channel_frame)
        
        # Update layouts
        self.frame_layout.fixtures = self.fixtures
        self.dmx_layout.fixtures = self.fixtures
        
        # Recreate fixtures in layouts
        self.frame_layout.delete("all")  # Clear existing fixtures
        self.frame_layout.create_grid()  # Recreate grid
        self.frame_layout.create_fixtures()  # Recreate fixtures
        
        self.dmx_layout.delete("all")  # Clear existing fixtures
        self.dmx_layout.create_grid()  # Recreate grid
        self.dmx_layout.create_fixtures()  # Recreate fixtures
        
        # Update fixture colors in layouts
        for i, fixture in enumerate(self.fixtures):
            start_idx = fixture.start_address - 1
            r = self.dmx_values[start_idx + 1] if start_idx + 1 < len(self.dmx_values) else 0  # Red channel
            g = self.dmx_values[start_idx + 2] if start_idx + 2 < len(self.dmx_values) else 0  # Green channel
            b = self.dmx_values[start_idx + 3] if start_idx + 3 < len(self.dmx_values) else 0  # Blue channel
            w = self.dmx_values[start_idx + 4] if start_idx + 4 < len(self.dmx_values) else 0  # White channel
            
            # Convert to hex color with proper formatting
            color = f'#{r:02x}{g:02x}{b:02x}'
            
            # Update fixture colors in both layouts
            self.frame_layout.update_fixture_color(i, color, w)
            self.dmx_layout.update_fixture_color(i, color, w)
        
        # Close window
        window.destroy()

    def create_frame_tab(self, frame_name):
        """Create a new tab for a frame"""
        frame = ttk.Frame(self.gui.tab_control)
        self.gui.tab_control.add(frame, text=frame_name)
        self.gui.tab_control.select(frame)  # Select the new tab
        
        # Initialize empty selection set for new frame
        self.frame_selections[frame_name] = set()

    def show_tab_menu(self, event):
        """Show context menu for tab operations"""
        # Get the clicked tab
        clicked_tab = self.gui.tab_control.identify(event.x, event.y)
        if not clicked_tab:
            return
        
        # Get the tab number that was clicked
        try:
            tab_index = self.gui.tab_control.index('@%d,%d' % (event.x, event.y))
            frame_name = self.gui.tab_control.tab(tab_index, "text")
            
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
            return self.gui.tab_control.tab(tab, "text")
        except:
            return None

    def rename_frame(self, frame_name):
        """Rename the current frame"""
        if not frame_name:
            return
            
        new_name = simpledialog.askstring("Rename Frame", "Enter new name:", initialvalue=frame_name)
        if new_name and new_name != frame_name:
            # Update tab name
            for tab in range(self.gui.tab_control.index('end')):
                if self.gui.tab_control.tab(tab, "text") == frame_name:
                    self.gui.tab_control.tab(tab, text=new_name)
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
            for tab in range(self.gui.tab_control.index('end')):
                if self.gui.tab_control.tab(tab, "text") == frame_name:
                    self.gui.tab_control.forget(tab)
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
        for fixture in range(len(self.fixtures)):
            start_channel = self.fixtures[fixture].start_address - 1
            for channel in range(self.fixtures[fixture].num_channels):
                # Update slider values only
                self.gui.channel_values[channel].set(frame_values[start_channel + channel])
        
        # Update frame layout visualization
        self.update_frame_layout(frame_values)
        
        # Only send values to DMX if apply_values is True
        if apply_values:
            # Update DMX values and send to output
            self.dmx_values = frame_values.copy()
            # Queue the updates through the update manager
            for i in range(len(frame_values)):
                self.update_manager.queue_update(self.fixtures[i].start_address + i, frame_values[i])
            # Update DMX layout visualization
            self.update_dmx_layout(self.dmx_values)
            self.dmx_matches_frame = True
        else:
            # Set flag to indicate DMX values don't match frame values
            self.dmx_matches_frame = False

    def update_frame_layout(self, values):
        """Update the frame layout with specified values"""
        for i in range(len(self.fixtures)):
            start_idx = self.fixtures[i].start_address - 1
            # Get values in correct channel order: dimmer, red, green, blue, white
            dimmer = values[start_idx + self.CHANNEL_DIMMER]  # Dimmer channel (Channel 1)
            r = values[start_idx + self.CHANNEL_RED]         # Red channel (Channel 2)
            g = values[start_idx + self.CHANNEL_GREEN]       # Green channel (Channel 3)
            b = values[start_idx + self.CHANNEL_BLUE]        # Blue channel (Channel 4)
            w = values[start_idx + self.CHANNEL_WHITE]       # White channel (Channel 5)
            
            # Apply dimmer to RGB values for visualization only
            dimmer_factor = dimmer / 255.0
            r_vis = int(r * dimmer_factor)
            g_vis = int(g * dimmer_factor)
            b_vis = int(b * dimmer_factor)
            w_vis = int(w * dimmer_factor)
            
            # Convert to hex color with proper formatting
            color = f'#{r_vis:02x}{g_vis:02x}{b_vis:02x}'
            
            # Update frame layout fixture color
            self.gui.frame_layout.update_fixture_color(i, color, w_vis)

    def apply_current_values(self):
        """Apply current frame values to DMX output"""
        selected = {i for i, var in enumerate(self.gui.fixture_vars) if var.get()}
        
        if not selected:
            return
        
        for fixture in selected:
            start_idx = self.fixtures[fixture].start_address - 1
            values = []
            for channel in range(self.fixtures[fixture].num_channels):
                values.append(self.frames[self.current_frame][start_idx + channel])
            
            # Queue the updates through the update manager
            self.update_manager.queue_multi_update(start_idx, values)

    def apply_frame(self, frame_name):
        """Apply the current frame's values to the DMX device, but only for selected fixtures"""
        if frame_name in self.frames:
            # Use the current selection state from the checkboxes
            selected = {i for i, var in enumerate(self.fixture_vars) if var.get()}
            
            if not selected:  # If no fixtures are selected, do nothing
                return
            
            # Only update DMX values for currently selected fixtures
            for fixture in selected:
                start_idx = self.fixtures[fixture].start_address - 1
                values = []
                for channel in range(self.fixtures[fixture].num_channels):
                    # Get value from frame
                    value = self.frames[frame_name][start_idx + channel]
                    # Queue the update through the update manager
                    self.update_manager.queue_update(start_idx + channel, value)
                    # Update our local copy after queueing
                    self.dmx_values[start_idx + channel] = value

    def update_dmx_layout(self, values):
        """Update the DMX output layout with current values"""
        for i in range(len(self.fixtures)):
            start_idx = self.fixtures[i].start_address - 1
            # Get values in correct channel order: dimmer, red, green, blue, white
            dimmer = values[start_idx + self.CHANNEL_DIMMER]  # Dimmer channel (Channel 1)
            r = values[start_idx + self.CHANNEL_RED]         # Red channel (Channel 2)
            g = values[start_idx + self.CHANNEL_GREEN]       # Green channel (Channel 3)
            b = values[start_idx + self.CHANNEL_BLUE]        # Blue channel (Channel 4)
            w = values[start_idx + self.CHANNEL_WHITE]       # White channel (Channel 5)
            
            # Apply dimmer to RGB values for visualization only
            dimmer_factor = dimmer / 255.0
            r_vis = int(r * dimmer_factor)
            g_vis = int(g * dimmer_factor)
            b_vis = int(b * dimmer_factor)
            w_vis = int(w * dimmer_factor)
            
            # Convert to hex color with proper formatting
            color = f'#{r_vis:02x}{g_vis:02x}{b_vis:02x}'
            
            # Update DMX layout fixture color
            self.gui.dmx_layout.update_fixture_color(i, color, w_vis)

    def on_tab_changed(self, event):
        """Handle tab change event"""
        # Save current frame's values and selections
        if self.current_frame in self.frames:
            self.frames[self.current_frame] = self.dmx_values.copy()
            self.frame_selections[self.current_frame] = self.selected_fixtures.copy()
        
        # Get the new frame name
        tab = self.gui.tab_control.select()
        frame_name = self.gui.tab_control.tab(tab, "text")
        
        # Load the new frame's values without sending to DMX
        self.load_frame(frame_name, apply_values=False)
        
        # Restore fixture selections for this frame
        self.restore_frame_selections(frame_name)

    def restore_frame_selections(self, frame_name):
        """Restore the fixture selections for a frame"""
        # Get the saved selections for this frame, or empty set if none
        saved_selections = self.frame_selections.get(frame_name, set())
        
        # Update checkboxes to match saved selections
        for i, var in enumerate(self.gui.fixture_vars):
            var.set(i in saved_selections)
        
        # Update selected fixtures set
        self.selected_fixtures = saved_selections.copy()

    def update_color_indicators(self):
        """Update the color indicators for all fixtures"""
        for i in range(len(self.fixtures)):
            # Get RGB values for this fixture
            start_idx = self.fixtures[i].start_address - 1
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
            start_address = self.fixtures[fixture].start_address
            channel_value = int(self.gui.channel_values[channel].get())
            
            # Update the frame values immediately
            if self.current_frame in self.frames:
                self.frames[self.current_frame][start_address + channel - 1] = channel_value

            # Only queue DMX updates if live tracking is enabled
            if self.gui.live_track.get():
                self.update_manager.queue_update(start_address + channel - 1, channel_value)

            # Update layout fixture colors for any channel change
            start_idx = self.fixtures[fixture].start_address - 1
            # Get values in correct channel order: dimmer, red, green, blue, white
            dimmer = self.frames[self.current_frame][start_idx + self.CHANNEL_DIMMER]  # Channel 1
            r = self.frames[self.current_frame][start_idx + self.CHANNEL_RED]         # Channel 2
            g = self.frames[self.current_frame][start_idx + self.CHANNEL_GREEN]       # Channel 3
            b = self.frames[self.current_frame][start_idx + self.CHANNEL_BLUE]        # Channel 4
            w = self.frames[self.current_frame][start_idx + self.CHANNEL_WHITE]       # Channel 5
            
            # Apply dimmer to RGB values for visualization only
            dimmer_factor = dimmer / 255.0
            r_vis = int(r * dimmer_factor)
            g_vis = int(g * dimmer_factor)
            b_vis = int(b * dimmer_factor)
            w_vis = int(w * dimmer_factor)
            
            # Convert to hex color with proper formatting
            color = f'#{r_vis:02x}{g_vis:02x}{b_vis:02x}'
            
            # Update fixture colors in both layouts
            self.gui.frame_layout.update_fixture_color(fixture, color, w_vis)
            if self.gui.live_track.get():
                self.gui.dmx_layout.update_fixture_color(fixture, color, w_vis)

    def update_rgb_from_wheel(self, r, g, b, dimmer):
        """Update RGB values from color wheel"""
        # Update channel values (using 0-based indices)
        # Map RGB values to channels 2-4 (Red, Green, Blue)
        self.gui.channel_values[self.CHANNEL_RED].set(r)     # Red channel (Channel 2)
        self.gui.channel_values[self.CHANNEL_GREEN].set(g)   # Green channel (Channel 3)
        self.gui.channel_values[self.CHANNEL_BLUE].set(b)    # Blue channel (Channel 4)
        self.gui.channel_values[self.CHANNEL_DIMMER].set(dimmer)  # Dimmer channel (Channel 1)

        # If no fixtures are selected, return
        if not self.selected_fixtures:
            return

        # Update DMX values for all selected fixtures
        for fixture in self.selected_fixtures:
            start_address = self.fixtures[fixture].start_address
            # Map RGB channels correctly (using 0-based indices)
            channel_mapping = {
                self.CHANNEL_DIMMER: dimmer,  # Dimmer channel (Channel 1)
                self.CHANNEL_RED: r,     # Red channel (Channel 2)
                self.CHANNEL_GREEN: g,   # Green channel (Channel 3)
                self.CHANNEL_BLUE: b     # Blue channel (Channel 4)
            }
            
            # Update each channel in the correct order
            for channel, value in channel_mapping.items():
                dmx_channel = start_address + channel - 1  # -1 because DMX is 0-based

                # Update the frame values immediately
                if self.current_frame in self.frames:
                    self.frames[self.current_frame][dmx_channel] = value

                # Only queue DMX updates if live tracking is enabled
                if self.gui.live_track.get():
                    self.update_manager.queue_update(dmx_channel, value)

            # Update fixture colors
            start_idx = self.fixtures[fixture].start_address - 1
            # Get values in correct channel order: dimmer, red, green, blue, white
            dimmer = self.frames[self.current_frame][start_idx + self.CHANNEL_DIMMER]  # Channel 1
            r = self.frames[self.current_frame][start_idx + self.CHANNEL_RED]         # Channel 2
            g = self.frames[self.current_frame][start_idx + self.CHANNEL_GREEN]       # Channel 3
            b = self.frames[self.current_frame][start_idx + self.CHANNEL_BLUE]        # Channel 4
            w = self.frames[self.current_frame][start_idx + self.CHANNEL_WHITE]       # Channel 5
            
            # Apply dimmer to RGB values for visualization only
            dimmer_factor = dimmer / 255.0
            r_vis = int(r * dimmer_factor)
            g_vis = int(g * dimmer_factor)
            b_vis = int(b * dimmer_factor)
            w_vis = int(w * dimmer_factor)
            
            # Convert to hex color with proper formatting
            color = f'#{r_vis:02x}{g_vis:02x}{b_vis:02x}'
            
            # Update fixture colors in both layouts
            self.gui.frame_layout.update_fixture_color(fixture, color, w_vis)
            if self.gui.live_track.get():
                self.gui.dmx_layout.update_fixture_color(fixture, color, w_vis)

    def check_connection(self):
        """Periodically check if the device is still connected"""
        if not self.dmx.device:
            if self.dmx.reconnect():
                # Resend current values after reconnection
                self.resend_all_values()
        
        # Schedule next check
        self.root.after(1000, self.check_connection)
        
    def resend_all_values(self):
        """Resend all current values after reconnection or master dimmer change"""
        # Queue all current values through the update manager
        for i in range(len(self.dmx_values)):
            self.update_manager.queue_update(i, self.dmx_values[i])

    def cleanup(self):
        """Clean up resources when closing the application"""
        if self.dmx:
            self.dmx.cleanup()

    def on_fixture_click(self, fixture_num):
        """Handle fixture click in the stage layout"""
        # Update sliders with the fixture's values
        start_idx = self.fixtures[fixture_num].start_address - 1
        for i in range(self.fixtures[fixture_num].num_channels):
            value = self.dmx_values[start_idx + i]
            self.channel_values[i].set(value)

    def update_selected_fixtures(self):
        """Update the set of selected fixtures based on checkbox states"""
        self.selected_fixtures = {i for i, var in enumerate(self.gui.fixture_vars) if var.get()}
        
        # If no fixtures are selected, clear all channel values
        if not self.selected_fixtures:
            for value in self.gui.channel_values:
                value.set(0)
            return

        # Get the first selected fixture's values to update the sliders
        first_fixture = next(iter(self.selected_fixtures))
        start_idx = self.fixtures[first_fixture].start_address - 1
        
        # Update sliders with the first fixture's values
        for i in range(len(self.gui.channel_values)):
            if start_idx + i < len(self.dmx_values):
                self.gui.channel_values[i].set(self.dmx_values[start_idx + i])

    def on_tab_press(self, event):
        """Handle tab press for reordering"""
        # Get the current tab
        current_tab = self.gui.tab_control.select()
        if current_tab:
            try:
                self.drag_start = event.x
                self.drag_tab = current_tab
                self.drag_tab_index = self.gui.tab_control.index(current_tab)
                self.drag_tab_name = self.gui.tab_control.tab(current_tab, "text")
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
                target_index = self.gui.tab_control.index('@%d,%d' % (event.x, event.y))
                if target_index != self.drag_tab_index and target_index >= 0:
                    # Get the tab widget
                    tab = self.gui.tab_control.select()
                    
                    # Insert the tab at the new position
                    self.gui.tab_control.insert(target_index, tab)
                    
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
        for i in range(len(self.fixtures)):
            if i in self.shared_fixture_positions:
                pos = self.shared_fixture_positions[i]
                angle = self.shared_fixture_angles[i]
                self.frame_layout.update_fixture_position(i, pos[0], pos[1], angle)
                self.dmx_layout.update_fixture_position(i, pos[0], pos[1], angle)

    def update_dmx_output(self):
        """Process DMX updates and handle fade operations"""
        updated, new_values = self.update_manager.process_updates(self.dmx_values)
        if updated and new_values:
            # Update DMX values with the original values (not the dimmed ones)
            self.dmx_values = self.update_manager.original_values.copy()
            
            # Update the DMX layout if not in a fade and callback is set
            fade_in_progress = self._fade_in_progress and self._fade_state is not None
            if not fade_in_progress and self.update_manager.on_frame_sent:
                self.update_manager.on_frame_sent(new_values)

        self.root.after(10, self.update_dmx_output)

    def toggle_select_all(self):
        """Toggle selection state of all fixtures"""
        # Check if all fixtures are currently selected
        all_selected = len(self.selected_fixtures) == len(self.fixtures)
        
        # Toggle selection state
        for i, var in enumerate(self.gui.fixture_vars):
            var.set(not all_selected)
        
        # Update selected fixtures set
        self.update_selected_fixtures()

    def clear_selection(self):
        """Clear all fixture selections"""
        for var in self.gui.fixture_vars:
            var.set(False)
        self.update_selected_fixtures()

    def fade_in_values(self):
        """Fade in the selected fixtures from current to target values"""
        if not self.selected_fixtures:
            return  # No fixtures selected
            
        # Get fade time in seconds
        fade_time = self.gui.fade_time.get()
        
        # Calculate number of steps (10Hz update rate)
        steps = int(fade_time * 10)  # 10 steps per second
        if steps < 1:
            steps = 1
            
        # Store start values (current DMX output) and target values (from current frame)
        start_values = {}
        target_values = {}
        has_changes = False  # Flag to track if there are any changes to fade
        
        for fixture in self.selected_fixtures:
            start_idx = self.fixtures[fixture].start_address - 1
            
            # Get current DMX values from actual DMX output
            start_values[fixture] = self.dmx_values[start_idx:start_idx + self.fixtures[fixture].num_channels].copy()
            
            # Get target values from current frame
            target_values[fixture] = self.frames[self.current_frame][start_idx:start_idx + self.fixtures[fixture].num_channels].copy()
            
            # Check if there are any differences between start and target values
            for i in range(self.fixtures[fixture].num_channels):
                if abs(start_values[fixture][i] - target_values[fixture][i]) > 0:
                    has_changes = True
        
        # If there are no changes to make, just return
        if not has_changes:
            return
            
        # Start the fade
        self.start_fade(start_values, target_values, list(self.selected_fixtures), steps)
        
        # Disable fade button during fade
        self.gui.fade_button.config(state="disabled")

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
            self.gui.fade_button.config(state="normal")
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
            start_idx = self.fixtures[fixture].start_address - 1
            
            # Queue all updates through the update manager first
            self.update_manager.queue_multi_update(start_idx, current_values)
            
            # Then update our local copy
            for j, value in enumerate(current_values):
                self.dmx_values[start_idx + j] = value
            
            # Get RGB values for this fixture for visualization
            r = current_values[1]  # Red channel
            g = current_values[2]  # Green channel
            b = current_values[3]  # Blue channel
            w = current_values[4]  # White channel
            color = f'#{r:02x}{g:02x}{b:02x}'
            
            # Update DMX layout visualization
            try:
                if fixture in self.dmx_layout.fixture_positions:
                    self.dmx_layout.fixture_colors[fixture] = color
                    white_color = f'#{w:02x}{w:02x}{w:02x}'
                    for item in self.dmx_layout.find_withtag(f'fixture_{fixture}'):
                        if self.dmx_layout.type(item) == 'rectangle':
                            self.dmx_layout.itemconfig(item, fill=white_color)
                        elif self.dmx_layout.type(item) == 'polygon':
                            self.dmx_layout.itemconfig(item, fill=color)
            except Exception as e:
                pass
        
        # Force UI update to ensure visualization is updated
        self.root.update()

    def _queue_fade_step(self, step):
        """Legacy method - will be called from update_dmx_output if not using new fade system"""
        # Call the new method instead
        if self._fade_state:
            self._process_fade_step(step)

    def periodic_live_track_update(self):
        """Periodically update DMX values for live tracking"""
        if self.gui.live_track.get():
            for fixture in self.selected_fixtures:
                start_idx = self.fixtures[fixture].start_address - 1
                # Get current values from our local copy
                values = [self.dmx_values[start_idx + ch] for ch in range(self.fixtures[fixture].num_channels)]
                # Queue updates through the update manager
                self.update_manager.queue_multi_update(start_idx, values)
        # Schedule next update
        self.root.after(50, self.periodic_live_track_update)  # 20Hz, safe for UI, DMX throttled to 10Hz

    def on_master_dimmer_change(self, value):
        """Handle master dimmer slider changes"""
        # Update master dimmer value in the update manager
        self.update_manager.set_master_dimmer(value)
        
        # Force a resend of all current values
        for i in range(len(self.dmx_values)):
            self.update_manager.queue_update(i, self.dmx_values[i])

if __name__ == "__main__":
    root = tk.Tk()
    app = DMXController(root)
    root.protocol("WM_DELETE_WINDOW", lambda: (app.cleanup(), root.destroy()))
    root.mainloop() 