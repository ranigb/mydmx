from __future__ import annotations

import math
import time
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from engine import EngineController, FixtureState, TriggerMode
from fixture import Fixture
from storage import ShowRepository


STAGE_REFERENCE_WIDTH = 620
STAGE_REFERENCE_HEIGHT = 360
RHYTHM_MIN_BPM = 40
RHYTHM_MAX_BPM = 240
RHYTHM_TAP_RESET_SECONDS = 2.0


class ColorWheel(tk.Canvas):
    def __init__(self, parent, *, callback=None, size: int = 180, **kwargs):
        super().__init__(parent, width=size, height=size, highlightthickness=0, **kwargs)
        self.size = size
        self.center = size // 2
        self.radius = (size // 2) - 10
        self.callback = callback
        self._marker = None
        self._draw_wheel()
        self.bind("<Button-1>", self._handle_pick)
        self.bind("<B1-Motion>", self._handle_pick)

    def _draw_wheel(self) -> None:
        self.delete("all")
        self.create_oval(0, 0, self.size, self.size, fill="#0d141b", outline="")
        for angle in range(360):
            red, green, blue = self._hsv_to_rgb(angle / 360.0, 1.0, 1.0)
            color = f"#{red:02x}{green:02x}{blue:02x}"
            self.create_arc(
                self.center - self.radius,
                self.center - self.radius,
                self.center + self.radius,
                self.center + self.radius,
                start=angle,
                extent=1.5,
                style=tk.PIESLICE,
                outline=color,
                fill=color,
            )
        inner_radius = int(self.radius * 0.45)
        self.create_oval(
            self.center - inner_radius,
            self.center - inner_radius,
            self.center + inner_radius,
            self.center + inner_radius,
            fill="#101820",
            outline="#d6dee8",
            width=2,
        )

    def _handle_pick(self, event) -> None:
        dx = event.x - self.center
        dy = event.y - self.center
        distance = (dx ** 2 + dy ** 2) ** 0.5
        if distance > self.radius:
            return
        if distance < self.radius * 0.1:
            red = green = blue = 255
        else:
            # Canvas arc angles are measured from the right and increase counterclockwise.
            # Screen Y grows downward, so negate dy to map pointer position back to the same hue.
            hue = math.degrees(math.atan2(-dy, dx)) % 360
            saturation = min(1.0, max(0.0, distance / self.radius))
            red, green, blue = self._hsv_to_rgb(hue / 360.0, saturation, 1.0)

        self._set_marker(event.x, event.y)
        if self.callback is not None:
            self.callback(red, green, blue)

    def _set_marker(self, x: int, y: int) -> None:
        if self._marker is not None:
            self.delete(self._marker)
        self._marker = self.create_oval(x - 6, y - 6, x + 6, y + 6, outline="#ffffff", width=2)

    def _hsv_to_rgb(self, hue: float, saturation: float, value: float) -> tuple[int, int, int]:
        if saturation == 0.0:
            gray = int(value * 255)
            return gray, gray, gray

        hue *= 6.0
        index = int(hue)
        fraction = hue - index
        p_value = value * (1.0 - saturation)
        q_value = value * (1.0 - saturation * fraction)
        t_value = value * (1.0 - saturation * (1.0 - fraction))

        if index == 0:
            red, green, blue = value, t_value, p_value
        elif index == 1:
            red, green, blue = q_value, value, p_value
        elif index == 2:
            red, green, blue = p_value, value, t_value
        elif index == 3:
            red, green, blue = p_value, q_value, value
        elif index == 4:
            red, green, blue = t_value, p_value, value
        else:
            red, green, blue = value, p_value, q_value

        return int(red * 255), int(green * 255), int(blue * 255)


class StagePlot(tk.Canvas):
    def __init__(self, parent, *, on_select=None, on_move=None, reference_size: tuple[int, int] | None = None, marker_scale: float = 1.0, show_address: bool = True, show_fixture_id: bool = True, normalize_positions: bool = False, draggable: bool = False, **kwargs):
        super().__init__(parent, highlightthickness=0, **kwargs)
        self._fixtures: list[Fixture] = []
        self._states: dict[int, FixtureState] = {}
        self._selected_ids: set[int] = set()
        self._on_select = on_select
        self._on_move = on_move
        self._reference_size = reference_size
        self._marker_scale = marker_scale
        self._show_address = show_address
        self._show_fixture_id = show_fixture_id
        self._normalize_positions = normalize_positions
        self._draggable = draggable
        self._drag_fixture_id: int | None = None
        self._fixture_positions: dict[int, tuple[int, int]] = {}
        self.bind("<Button-1>", self._handle_click)
        self.bind("<B1-Motion>", self._handle_drag)
        self.bind("<ButtonRelease-1>", self._handle_release)
        self.bind("<Configure>", self._on_resize)

    def set_content(
        self,
        fixtures: list[Fixture],
        states: dict[int, FixtureState],
        selected_ids: set[int] | None = None,
    ) -> None:
        self._fixtures = fixtures
        self._states = states
        self._selected_ids = selected_ids or set()
        self.redraw()

    def redraw(self) -> None:
        self.delete("all")
        width = self.winfo_width()
        height = self.winfo_height()
        if width <= 1:
            width = int(self.cget("width"))
        if height <= 1:
            height = int(self.cget("height"))
        outer_radius = max(4, round(18 * self._marker_scale))
        inner_radius = max(2, round(10 * self._marker_scale))
        outline_width = max(1, round(3 * self._marker_scale))
        fixture_font_size = max(5, round(10 * self._marker_scale))
        address_font_size = max(6, round(8 * self._marker_scale))
        address_offset = max(14, round(28 * self._marker_scale))
        self._fixture_positions = {}
        self.create_rectangle(0, 0, width, height, fill="#111821", outline="#1a2430")
        for x in range(40, width, 40):
            self.create_line(x, 0, x, height, fill="#18232f")
        for y in range(40, height, 40):
            self.create_line(0, y, width, y, fill="#18232f")

        normalized_bounds = None
        if self._normalize_positions:
            positioned_fixtures = [fixture for fixture in self._fixtures if fixture.position != (0, 0)]
            if positioned_fixtures:
                x_values = [fixture.position[0] for fixture in positioned_fixtures]
                y_values = [fixture.position[1] for fixture in positioned_fixtures]
                normalized_bounds = (min(x_values), max(x_values), min(y_values), max(y_values))

        for index, fixture in enumerate(self._fixtures):
            x, y = self._display_position(index, fixture, width, height, outer_radius, normalized_bounds)
            self._fixture_positions[fixture.fixture_id] = (x, y)
            state = self._states.get(fixture.fixture_id, FixtureState(fixture_id=fixture.fixture_id))
            outer_fill, inner_fill = self._fixture_colors(state)
            outline = "#ffb703" if fixture.fixture_id in self._selected_ids else "#bfc7d5"
            self.create_oval(x - outer_radius, y - outer_radius, x + outer_radius, y + outer_radius, fill=outer_fill, outline=outline, width=outline_width, tags=(f"fixture-{fixture.fixture_id}", "fixture"))
            self.create_oval(x - inner_radius, y - inner_radius, x + inner_radius, y + inner_radius, fill=inner_fill, outline="", tags=(f"fixture-{fixture.fixture_id}", "fixture"))
            if self._show_fixture_id:
                self.create_text(x, y, text=str(fixture.fixture_id), fill="#0b1118", font=("Segoe UI", fixture_font_size, "bold"), tags=(f"fixture-{fixture.fixture_id}", "fixture"))
            if self._show_address:
                self.create_text(x, y + address_offset, text=f"A{fixture.start_address}", fill="#dde7f2", font=("Segoe UI", address_font_size), tags=(f"fixture-{fixture.fixture_id}", "fixture"))

    def _display_position(
        self,
        index: int,
        fixture: Fixture,
        width: int,
        height: int,
        outer_radius: int,
        normalized_bounds: tuple[int, int, int, int] | None,
    ) -> tuple[int, int]:
        if fixture.position != (0, 0):
            margin = outer_radius + 6
            if self._normalize_positions and normalized_bounds is not None:
                min_x, max_x, min_y, max_y = normalized_bounds
                usable_width = max(1, width - (2 * margin))
                usable_height = max(1, height - (2 * margin))

                if max_x == min_x:
                    scaled_x = width // 2
                else:
                    scaled_x = margin + round((fixture.position[0] - min_x) * usable_width / (max_x - min_x))

                if max_y == min_y:
                    scaled_y = height // 2
                else:
                    scaled_y = margin + round((fixture.position[1] - min_y) * usable_height / (max_y - min_y))
            elif self._reference_size is not None:
                reference_width, reference_height = self._reference_size
                scaled_x = round(fixture.position[0] * width / max(1, reference_width))
                scaled_y = round(fixture.position[1] * height / max(1, reference_height))
            else:
                scaled_x = fixture.position[0]
                scaled_y = fixture.position[1]

            x = max(margin, min(width - margin, scaled_x))
            y = max(margin, min(height - margin, scaled_y))
            return x, y

        columns = max(1, min(4, len(self._fixtures)))
        row = index // columns
        column = index % columns
        usable_width = max(1, width - 80)
        usable_height = max(1, height - 80)
        x = 40 + int((column + 0.5) * usable_width / columns)
        rows = max(1, (len(self._fixtures) + columns - 1) // columns)
        y = 40 + int((row + 0.5) * usable_height / rows)
        return x, y

    def _fixture_colors(self, state: FixtureState) -> tuple[str, str]:
        dimmer = state.intensity / 255 if state.intensity else 0
        red = int(state.red * dimmer)
        green = int(state.green * dimmer)
        blue = int(state.blue * dimmer)
        white = int(state.white * dimmer)

        outer_fill = "#52606d"
        if white > 0:
            outer_fill = f"#{white:02x}{white:02x}{white:02x}"

        if red == green == blue == 0:
            inner_fill = "#1f2933" if white > 0 else "#52606d"
        else:
            inner_fill = f"#{red:02x}{green:02x}{blue:02x}"

        return outer_fill, inner_fill

    def _handle_click(self, event) -> None:
        fixture_id = self._fixture_id_at(event.x, event.y)
        if fixture_id is None:
            self._drag_fixture_id = None
            return
        self._drag_fixture_id = fixture_id if self._draggable else None
        if self._on_select is not None:
            self._on_select(fixture_id)

    def _handle_drag(self, event) -> None:
        if self._drag_fixture_id is None or self._on_move is None:
            return
        width = self.winfo_width()
        height = self.winfo_height()
        if width <= 1:
            width = int(self.cget("width"))
        if height <= 1:
            height = int(self.cget("height"))
        outer_radius = max(4, round(18 * self._marker_scale))
        clamped_x, clamped_y = self._clamp_display_position(event.x, event.y, width, height, outer_radius)
        position = self._display_to_position(clamped_x, clamped_y, width, height)
        self._on_move(self._drag_fixture_id, position)

    def _handle_release(self, _event=None) -> None:
        self._drag_fixture_id = None

    def _fixture_id_at(self, x: int, y: int) -> int | None:
        overlapping = self.find_overlapping(x - 1, y - 1, x + 1, y + 1)
        for item_id in reversed(overlapping):
            fixture_id = self._fixture_id_from_tags(self.gettags(item_id))
            if fixture_id is not None:
                return fixture_id

        closest = self.find_closest(x, y)
        if not closest:
            return None
        return self._fixture_id_from_tags(self.gettags(closest[0]))

    def _fixture_id_from_tags(self, tags: tuple[str, ...]) -> int | None:
        for tag in tags:
            if tag.startswith("fixture-"):
                return int(tag.split("-", 1)[1])
        return None

    def _clamp_display_position(self, x: int, y: int, width: int, height: int, outer_radius: int) -> tuple[int, int]:
        margin = outer_radius + 6
        return (
            max(margin, min(width - margin, x)),
            max(margin, min(height - margin, y)),
        )

    def _display_to_position(self, x: int, y: int, width: int, height: int) -> tuple[int, int]:
        if self._reference_size is None:
            return x, y
        reference_width, reference_height = self._reference_size
        return (
            round(x * reference_width / max(1, width)),
            round(y * reference_height / max(1, height)),
        )

    def _on_resize(self, _event=None) -> None:
        self.redraw()


class MainApplication(ttk.Frame):
    def __init__(self, parent, controller: EngineController, repository: ShowRepository, *, transport_error: Exception | None = None):
        super().__init__(parent, padding=12)
        self.root = parent
        self.controller = controller
        self.repository = repository
        self.transport_error = transport_error
        self.show_file_path: str | None = None
        self.scene_selected_fixture_ids: set[int] = set()
        self.show_selected_fixture_ids: set[int] = set()
        self.setup_selected_fixture_id: int | None = None
        self.selected_scene_id: str | None = None
        self.selected_sequence_id: str | None = None
        self.sequence_paused = False
        self._rhythm_tap_times: list[float] = []
        self.scene_order: list[str] = []
        self.sequence_order: list[str] = []
        self.cue_order: list[str] = []

        self.output_status_var = tk.StringVar()
        self.current_scene_var = tk.StringVar()
        self.dirty_var = tk.StringVar()
        self.loaded_sequence_var = tk.StringVar()
        self.current_cue_var = tk.StringVar()
        self.next_cue_var = tk.StringVar()
        self.transport_status_var = tk.StringVar()
        self.override_status_var = tk.StringVar()
        self.sequence_cyclic_var = tk.BooleanVar(value=False)
        self.scene_auto_apply_var = tk.BooleanVar(value=False)
        self.override_auto_apply_var = tk.BooleanVar(value=False)
        self.rhythm_bpm_var = tk.IntVar(value=int(round(self.controller.rhythm_bpm)))
        self._suspend_editor_callbacks = False

        self.scene_editor_vars = self._create_level_vars()
        self.override_editor_vars = self._create_level_vars()
        self._bind_level_var_traces(self.scene_editor_vars, "scene")
        self._bind_level_var_traces(self.override_editor_vars, "override")

        self._bootstrap_defaults()
        self._build_ui()
        self._refresh_lists()
        self._refresh_views()
        self._schedule_tick()

    def _bootstrap_defaults(self) -> None:
        if not self.controller.state.scenes:
            scene = self.controller.create_scene("Scene 1")
            self.selected_scene_id = scene.id
        else:
            self.selected_scene_id = next(iter(self.controller.state.scenes))

        if not self.controller.state.sequences:
            sequence = self.controller.create_sequence("Main Sequence")
            self.selected_sequence_id = sequence.id
            self.controller.load_sequence(sequence.id)
        else:
            self.selected_sequence_id = next(iter(self.controller.state.sequences))
            self.controller.load_sequence(self.selected_sequence_id)

    def _build_ui(self) -> None:
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")

        self.grid(sticky="nsew")
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.main_area = ttk.Frame(self)
        self.main_area.grid(row=0, column=0, sticky="nsew")
        self.main_area.grid_rowconfigure(0, weight=1)
        self.main_area.grid_columnconfigure(0, weight=1, minsize=320)
        self.main_area.grid_columnconfigure(1, weight=3)

        self.left_panel = ttk.Frame(self.main_area)
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        self.left_panel.grid_rowconfigure(1, weight=1)
        self.left_panel.grid_columnconfigure(0, weight=1)

        self._build_top_bar(self.left_panel)
        self._build_live_status_panel(self.left_panel)

        self.notebook = ttk.Notebook(self.main_area)
        self.notebook.grid(row=0, column=1, sticky="nsew")

        self.setup_tab = ttk.Frame(self.notebook, padding=10)
        self.scene_tab = ttk.Frame(self.notebook, padding=10)
        self.sequence_tab = ttk.Frame(self.notebook, padding=10)
        self.show_tab = ttk.Frame(self.notebook, padding=10)

        self.notebook.add(self.setup_tab, text="Setup")
        self.notebook.add(self.scene_tab, text="Scene Editor")
        self.notebook.add(self.sequence_tab, text="Sequences")
        self.notebook.add(self.show_tab, text="Show Mode")

        self._build_setup_tab()
        self._build_scene_tab()
        self._build_sequence_tab()
        self._build_show_tab()

    def _build_top_bar(self, parent) -> None:
        panel = ttk.LabelFrame(parent, text="Show Control", padding=10)
        panel.grid(row=0, column=0, sticky="new", pady=(0, 12))
        panel.grid_columnconfigure(1, weight=1)

        info_rows = [
            ("Output", self.output_status_var),
            ("Current Scene", self.current_scene_var),
            ("Loaded Sequence", self.loaded_sequence_var),
            ("Cue", self.current_cue_var),
            ("Next", self.next_cue_var),
            ("Transport", self.transport_status_var),
            ("Override", self.override_status_var),
            ("State", self.dirty_var),
        ]
        for row_index, (label, value) in enumerate(info_rows):
            ttk.Label(panel, text=label).grid(row=row_index, column=0, sticky="w", pady=(0, 4), padx=(0, 8))
            ttk.Label(panel, textvariable=value).grid(row=row_index, column=1, sticky="w", pady=(0, 4))

        ttk.Label(panel, text="Master").grid(row=len(info_rows), column=0, sticky="w", pady=(8, 4), padx=(0, 8))
        self.master_var = tk.DoubleVar(value=self.controller.state.master_dimmer)
        master = ttk.Scale(panel, from_=0.0, to=1.0, orient="horizontal", variable=self.master_var, command=self._on_master_changed)
        master.grid(row=len(info_rows), column=1, sticky="ew", pady=(8, 4))

        buttons = ttk.Frame(panel)
        buttons.grid(row=len(info_rows) + 1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        buttons.grid_columnconfigure(0, weight=1)
        buttons.grid_columnconfigure(1, weight=1)
        buttons.grid_columnconfigure(2, weight=1)
        ttk.Button(buttons, text="Blackout", command=self._toggle_blackout).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(buttons, text="Load Show", command=self._load_show).grid(row=0, column=1, sticky="ew", padx=(0, 6))
        ttk.Button(buttons, text="Save Show", command=self._save_show).grid(row=0, column=2, sticky="ew")

    def _build_live_status_panel(self, parent) -> None:
        panel = ttk.LabelFrame(parent, text="Current Displayed Lights", padding=10)
        panel.grid(row=1, column=0, sticky="nsew")
        panel.grid_rowconfigure(0, weight=1)
        panel.grid_columnconfigure(0, weight=1)

        self.live_fixture_stage_host = ttk.Frame(panel)
        self.live_fixture_stage_host.grid(row=0, column=0, sticky="nsew")
        self.live_fixture_stage_host.bind("<Configure>", self._resize_live_fixture_stage)

        self.live_fixture_stage = StagePlot(
            self.live_fixture_stage_host,
            width=STAGE_REFERENCE_WIDTH,
            height=STAGE_REFERENCE_HEIGHT,
            reference_size=(STAGE_REFERENCE_WIDTH, STAGE_REFERENCE_HEIGHT),
            marker_scale=0.4,
            show_address=False,
            show_fixture_id=False,
            normalize_positions=True,
        )
        self.live_fixture_stage.place(x=0, y=0, width=STAGE_REFERENCE_WIDTH, height=STAGE_REFERENCE_HEIGHT)

    def _build_setup_tab(self) -> None:
        self.setup_tab.grid_columnconfigure(1, weight=1)
        self.setup_tab.grid_rowconfigure(0, weight=1)

        left = ttk.Frame(self.setup_tab)
        left.grid(row=0, column=0, sticky="nsw", padx=(0, 12))
        right = ttk.Frame(self.setup_tab)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_rowconfigure(0, weight=1)
        right.grid_columnconfigure(0, weight=1)

        ttk.Label(left, text="Fixtures", font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky="w")
        self.fixture_tree = ttk.Treeview(left, columns=("address", "channels", "position"), show="headings", height=10)
        self.fixture_tree.heading("address", text="Address")
        self.fixture_tree.heading("channels", text="Channels")
        self.fixture_tree.heading("position", text="Position")
        self.fixture_tree.column("address", width=72, anchor="center")
        self.fixture_tree.column("channels", width=72, anchor="center")
        self.fixture_tree.column("position", width=110, anchor="center")
        self.fixture_tree.grid(row=1, column=0, sticky="nsew", pady=(8, 8))
        self.fixture_tree.bind("<<TreeviewSelect>>", self._on_fixture_tree_selected)

        buttons = ttk.Frame(left)
        buttons.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        ttk.Button(buttons, text="Add Fixture", command=self._add_fixture).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(buttons, text="Save Fixture", command=self._save_fixture_patch).grid(row=0, column=1)

        form = ttk.LabelFrame(left, text="Patch")
        form.grid(row=3, column=0, sticky="ew")
        self.fixture_address_var = tk.IntVar(value=1)
        self.fixture_channels_var = tk.IntVar(value=5)
        self.fixture_x_var = tk.IntVar(value=0)
        self.fixture_y_var = tk.IntVar(value=0)
        self.fixture_angle_var = tk.IntVar(value=0)
        self._add_labeled_entry(form, 0, "Start Address", self.fixture_address_var)
        self._add_labeled_entry(form, 1, "Channels", self.fixture_channels_var)
        self.fixture_x_entry = self._add_labeled_entry(form, 2, "Position X", self.fixture_x_var)
        self.fixture_y_entry = self._add_labeled_entry(form, 3, "Position Y", self.fixture_y_var)
        self._add_labeled_entry(form, 4, "Angle", self.fixture_angle_var)
        for entry in (self.fixture_x_entry, self.fixture_y_entry):
            entry.bind("<Return>", self._commit_setup_position_from_editor)
            entry.bind("<FocusOut>", self._commit_setup_position_from_editor)

        self.setup_stage = StagePlot(
            right,
            width=620,
            height=360,
            on_select=self._select_setup_fixture,
            on_move=self._drag_setup_fixture,
            reference_size=(STAGE_REFERENCE_WIDTH, STAGE_REFERENCE_HEIGHT),
            draggable=True,
        )
        self.setup_stage.grid(row=0, column=0, sticky="nsew")

    def _build_scene_tab(self) -> None:
        self.scene_tab.grid_columnconfigure(1, weight=1)
        self.scene_tab.grid_rowconfigure(0, weight=1)

        left = ttk.Frame(self.scene_tab)
        left.grid(row=0, column=0, sticky="nsw", padx=(0, 12))
        center = ttk.Frame(self.scene_tab)
        center.grid(row=0, column=1, sticky="nsew", padx=(0, 12))
        right = ttk.Frame(self.scene_tab)
        right.grid(row=0, column=2, sticky="nse")
        center.grid_rowconfigure(0, weight=1)
        center.grid_columnconfigure(0, weight=1)

        ttk.Label(left, text="Scenes", font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky="w")
        self.scene_listbox = tk.Listbox(left, height=12, exportselection=False)
        self.scene_listbox.grid(row=1, column=0, sticky="nsew", pady=(8, 8))
        self.scene_listbox.bind("<<ListboxSelect>>", self._on_scene_selected)

        scene_buttons = ttk.Frame(left)
        scene_buttons.grid(row=2, column=0, sticky="ew")
        ttk.Button(scene_buttons, text="New", command=self._create_scene).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(scene_buttons, text="Duplicate", command=self._duplicate_scene).grid(row=0, column=1, padx=(0, 6))
        ttk.Button(scene_buttons, text="Rename", command=self._rename_scene).grid(row=0, column=2, padx=(0, 6))
        ttk.Button(scene_buttons, text="Delete", command=self._delete_scene).grid(row=0, column=3)

        self.scene_stage = StagePlot(center, width=620, height=360, on_select=self._toggle_scene_fixture)
        self.scene_stage.grid(row=0, column=0, sticky="nsew")

        inspector = ttk.LabelFrame(right, text="Fixture Levels")
        inspector.grid(row=0, column=0, sticky="ne")
        self._build_level_editor(inspector, self.scene_editor_vars)

        scene_color_frame = ttk.LabelFrame(right, text="Color Wheel")
        scene_color_frame.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        self.scene_color_wheel = ColorWheel(scene_color_frame, callback=self._on_scene_color_picked, bg="#111821")
        self.scene_color_wheel.grid(row=0, column=0, padx=8, pady=8)

        controls = ttk.Frame(right)
        controls.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        ttk.Label(controls, text="Fade (ms)").grid(row=0, column=0, sticky="w")
        self.scene_fade_var = tk.IntVar(value=1500)
        ttk.Entry(controls, textvariable=self.scene_fade_var, width=10).grid(row=1, column=0, sticky="w")
        ttk.Checkbutton(controls, text="Auto-apply editor", variable=self.scene_auto_apply_var, command=self._on_scene_auto_apply_toggled).grid(row=2, column=0, sticky="w", pady=(8, 4))
        ttk.Button(controls, text="Update Scene", command=self._apply_scene_editor_to_scene).grid(row=3, column=0, sticky="ew", pady=(4, 4))
        ttk.Button(controls, text="Capture Live", command=self._capture_live_to_scene).grid(row=4, column=0, sticky="ew", pady=(0, 4))
        ttk.Button(controls, text="Apply Live", command=self._apply_selected_scene).grid(row=5, column=0, sticky="ew")

    def _build_sequence_tab(self) -> None:
        self.sequence_tab.grid_columnconfigure(1, weight=1)
        self.sequence_tab.grid_rowconfigure(0, weight=1)

        left = ttk.Frame(self.sequence_tab)
        left.grid(row=0, column=0, sticky="nsw", padx=(0, 12))
        center = ttk.Frame(self.sequence_tab)
        center.grid(row=0, column=1, sticky="nsew", padx=(0, 12))
        right = ttk.Frame(self.sequence_tab)
        right.grid(row=0, column=2, sticky="nse")

        ttk.Label(left, text="Sequences", font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky="w")
        self.sequence_listbox = tk.Listbox(left, height=10, exportselection=False)
        self.sequence_listbox.grid(row=1, column=0, pady=(8, 8), sticky="nsew")
        self.sequence_listbox.bind("<<ListboxSelect>>", self._on_sequence_selected)
        seq_buttons = ttk.Frame(left)
        seq_buttons.grid(row=2, column=0, sticky="ew")
        ttk.Button(seq_buttons, text="New", command=self._create_sequence).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(seq_buttons, text="Load To Show", command=self._load_selected_sequence).grid(row=0, column=1)

        ttk.Label(center, text="Cue Stack", font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky="w")
        self.cue_listbox = tk.Listbox(center, height=16, exportselection=False)
        self.cue_listbox.grid(row=1, column=0, sticky="nsew", pady=(8, 0))

        form = ttk.LabelFrame(right, text="Cue")
        form.grid(row=0, column=0, sticky="ne")
        form.grid_columnconfigure(0, weight=1)
        self.sequence_scene_var = tk.StringVar()
        self.sequence_fade_ms_var = tk.IntVar(value=1500)
        self.sequence_hold_ms_var = tk.IntVar(value=2000)
        self.sequence_trigger_var = tk.StringVar(value=TriggerMode.MANUAL.value)
        ttk.Checkbutton(form, text="Cyclic sequence", variable=self.sequence_cyclic_var, command=self._toggle_selected_sequence_cyclic).grid(row=0, column=0, sticky="w", padx=8, pady=(8, 6))
        ttk.Label(form, text="Scene").grid(row=1, column=0, sticky="w")
        self.sequence_scene_combo = ttk.Combobox(form, textvariable=self.sequence_scene_var, state="readonly", width=22)
        self.sequence_scene_combo.grid(row=2, column=0, sticky="ew", pady=(0, 6), padx=8)
        self._add_labeled_entry(form, 2, "Fade In (ms)", self.sequence_fade_ms_var)
        self._add_labeled_entry(form, 4, "Hold (ms)", self.sequence_hold_ms_var)
        ttk.Label(form, text="Trigger").grid(row=6, column=0, sticky="w", padx=8)
        trigger = ttk.Combobox(form, textvariable=self.sequence_trigger_var, values=[TriggerMode.MANUAL.value, TriggerMode.AUTO.value], state="readonly", width=22)
        trigger.grid(row=7, column=0, sticky="ew", pady=(0, 6), padx=8)
        ttk.Button(form, text="Add Cue", command=self._add_cue_to_sequence).grid(row=8, column=0, sticky="ew", pady=(8, 4), padx=8)
        ttk.Button(form, text="Remove Cue", command=self._remove_selected_cue).grid(row=9, column=0, sticky="ew", padx=8, pady=(0, 8))

    def _build_show_tab(self) -> None:
        self.show_tab.grid_columnconfigure(0, weight=1)
        self.show_tab.grid_rowconfigure(1, weight=1)

        header = ttk.Frame(self.show_tab)
        header.grid(row=0, column=0, sticky="ew")
        ttk.Label(header, text="Loaded Sequence").grid(row=0, column=0, padx=(0, 6))
        ttk.Label(header, textvariable=self.loaded_sequence_var).grid(row=0, column=1, padx=(0, 16))
        ttk.Label(header, text="Next Cue").grid(row=0, column=2, padx=(0, 6))
        ttk.Label(header, textvariable=self.next_cue_var).grid(row=0, column=3)

        content = ttk.Frame(self.show_tab)
        content.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(0, weight=1)

        self.show_stage = StagePlot(content, width=720, height=380, on_select=self._toggle_show_fixture)
        self.show_stage.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        sidebar = ttk.Frame(content)
        sidebar.grid(row=0, column=1, sticky="ns")
        transport = ttk.LabelFrame(sidebar, text="Transport")
        transport.grid(row=0, column=0, sticky="ew")
        ttk.Button(transport, text="Go", command=self._go_next_cue).grid(row=0, column=0, sticky="ew", pady=(0, 6))
        ttk.Button(transport, text="Back", command=self._go_previous_cue).grid(row=1, column=0, sticky="ew", pady=(0, 6))
        self.pause_button = ttk.Button(transport, text="Pause", command=self._toggle_sequence_pause)
        self.pause_button.grid(row=2, column=0, sticky="ew", pady=(0, 6))
        ttk.Button(transport, text="Release Override", command=self._release_override).grid(row=3, column=0, sticky="ew", pady=(0, 6))
        ttk.Button(transport, text="Record Override", command=self._record_override).grid(row=4, column=0, sticky="ew")

        rhythm = ttk.LabelFrame(sidebar, text="Rhythm Play")
        rhythm.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        rhythm.grid_columnconfigure(0, weight=1)
        ttk.Label(rhythm, text="Pace (BPM)").grid(row=0, column=0, sticky="w", padx=8, pady=(8, 2))
        rhythm_entry = ttk.Entry(rhythm, textvariable=self.rhythm_bpm_var, width=8)
        rhythm_entry.grid(row=1, column=0, sticky="ew", padx=8)
        rhythm_entry.bind("<Return>", self._commit_rhythm_bpm)
        rhythm_entry.bind("<FocusOut>", self._commit_rhythm_bpm)
        ttk.Scale(
            rhythm,
            from_=RHYTHM_MIN_BPM,
            to=RHYTHM_MAX_BPM,
            orient="horizontal",
            variable=self.rhythm_bpm_var,
            command=self._on_rhythm_slider_changed,
        ).grid(row=2, column=0, sticky="ew", padx=8, pady=(8, 6))
        ttk.Button(rhythm, text="Tap Tempo", command=self._tap_rhythm_tempo).grid(row=3, column=0, sticky="ew", padx=8, pady=(0, 6))
        self.rhythm_button = ttk.Button(rhythm, text="Start Rhythm", command=self._toggle_rhythm_play)
        self.rhythm_button.grid(row=4, column=0, sticky="ew", padx=8, pady=(0, 8))

        override = ttk.LabelFrame(sidebar, text="Live Override")
        override.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        self._build_level_editor(override, self.override_editor_vars)
        ttk.Checkbutton(override, text="Auto-apply editor", variable=self.override_auto_apply_var, command=self._on_override_auto_apply_toggled).grid(row=5, column=0, sticky="w", padx=8, pady=(8, 4))
        ttk.Button(override, text="Apply Override", command=self._apply_show_override).grid(row=6, column=0, sticky="ew", pady=(4, 0))

        override_color_frame = ttk.LabelFrame(sidebar, text="Color Wheel")
        override_color_frame.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        self.override_color_wheel = ColorWheel(override_color_frame, callback=self._on_override_color_picked, bg="#111821")
        self.override_color_wheel.grid(row=0, column=0, padx=8, pady=8)

    def _build_level_editor(self, parent, variables: dict[str, tk.IntVar]) -> None:
        for row_index, label in enumerate(["Intensity", "Red", "Green", "Blue", "White"]):
            key = label.lower()
            row = ttk.Frame(parent)
            row.grid(row=row_index, column=0, sticky="ew", padx=8, pady=4)
            row.grid_columnconfigure(1, weight=1)
            ttk.Label(row, text=label, width=10).grid(row=0, column=0, sticky="w")
            value_label = ttk.Label(row, textvariable=variables[key], width=4)
            value_label.grid(row=0, column=2, sticky="e")
            slider = ttk.Scale(row, from_=0, to=255, orient="horizontal", variable=variables[key])
            slider.grid(row=0, column=1, sticky="ew", padx=(6, 6))

    def _create_level_vars(self) -> dict[str, tk.IntVar]:
        return {
            "intensity": tk.IntVar(value=0),
            "red": tk.IntVar(value=0),
            "green": tk.IntVar(value=0),
            "blue": tk.IntVar(value=0),
            "white": tk.IntVar(value=0),
        }

    def _add_labeled_entry(self, parent, row: int, label: str, variable):
        grid_row = row * 2
        ttk.Label(parent, text=label).grid(row=grid_row, column=0, sticky="w", padx=8, pady=(8, 2))
        entry = ttk.Entry(parent, textvariable=variable, width=14)
        entry.grid(row=grid_row + 1, column=0, sticky="ew", padx=8, pady=(0, 6))
        return entry

    def _schedule_tick(self) -> None:
        self.controller.tick()
        self._refresh_views()
        self.root.after(50, self._schedule_tick)

    def _refresh_views(self) -> None:
        self.output_status_var.set(self._output_status_text())
        current_scene = self.controller.state.scenes.get(self.controller.state.current_scene_id) if self.controller.state.current_scene_id else None
        self.current_scene_var.set(current_scene.name if current_scene is not None else "None")
        self.dirty_var.set("Modified" if self.controller.state.dirty else "Clean")

        loaded_sequence = self.controller.loaded_sequence
        self.loaded_sequence_var.set(loaded_sequence.name if loaded_sequence is not None else "None")

        current_cue = self.controller.current_cue
        current_cue_number = self.controller.current_cue_number
        if current_cue is None:
            self.current_cue_var.set("Standby")
        else:
            current_cue_scene = self.controller.state.scenes.get(current_cue.scene_id)
            current_cue_name = current_cue_scene.name if current_cue_scene is not None else current_cue.scene_id
            self.current_cue_var.set(f"{current_cue_number}. {current_cue_name}")

        next_cue = self.controller.next_cue
        if next_cue is None:
            self.next_cue_var.set("End")
        else:
            next_scene = self.controller.state.scenes.get(next_cue.scene_id)
            self.next_cue_var.set(next_scene.name if next_scene is not None else next_cue.scene_id)

        self.transport_status_var.set(self._transport_status_text())
        self.override_status_var.set("Active" if self.controller.state.live_override.active else "None")
        self.pause_button.configure(text="Resume" if self.controller.is_sequence_paused else "Pause")
        self.rhythm_button.configure(text="Stop Rhythm" if self.controller.is_rhythm_playing else "Start Rhythm")

        live_states = self._live_fixture_display_states()
        self.live_fixture_stage.set_content(self.controller.fixtures, live_states, set())

        scene_states = self._scene_preview_states()
        show_states = self._show_preview_states()
        self.scene_stage.set_content(self.controller.fixtures, scene_states, self.scene_selected_fixture_ids)
        self.show_stage.set_content(self.controller.fixtures, show_states, self.show_selected_fixture_ids)
        setup_selected_ids = {self.setup_selected_fixture_id} if self.setup_selected_fixture_id is not None else set()
        self.setup_stage.set_content(self.controller.fixtures, live_states, setup_selected_ids)

    def _refresh_lists(self) -> None:
        self._refresh_fixture_tree()
        self._refresh_scene_list()
        self._refresh_sequence_list()
        self._refresh_scene_combo()

    def _refresh_fixture_tree(self) -> None:
        for item in self.fixture_tree.get_children():
            self.fixture_tree.delete(item)
        for fixture in self.controller.fixtures:
            values = (
                fixture.start_address,
                fixture.num_channels,
                f"{fixture.position[0]}, {fixture.position[1]}",
            )
            self.fixture_tree.insert("", "end", iid=str(fixture.fixture_id), values=values, text=str(fixture.fixture_id))
        if self.setup_selected_fixture_id is not None:
            fixture_item = str(self.setup_selected_fixture_id)
            if self.fixture_tree.exists(fixture_item):
                self.fixture_tree.selection_set(fixture_item)
                self.fixture_tree.focus(fixture_item)

    def _refresh_scene_list(self) -> None:
        self.scene_listbox.delete(0, tk.END)
        scenes = sorted(self.controller.state.scenes.values(), key=lambda scene: scene.name.lower())
        self.scene_order = [scene.id for scene in scenes]
        for scene in scenes:
            self.scene_listbox.insert(tk.END, scene.name)
        if self.selected_scene_id in self.scene_order:
            self.scene_listbox.selection_set(self.scene_order.index(self.selected_scene_id))
        elif self.scene_order:
            self.selected_scene_id = self.scene_order[0]
            self.scene_listbox.selection_set(0)

    def _refresh_sequence_list(self) -> None:
        self.sequence_listbox.delete(0, tk.END)
        sequences = sorted(self.controller.state.sequences.values(), key=lambda sequence: sequence.name.lower())
        self.sequence_order = [sequence.id for sequence in sequences]
        for sequence in sequences:
            label = f"{sequence.name} (cyclic)" if sequence.cyclic else sequence.name
            self.sequence_listbox.insert(tk.END, label)
        if self.selected_sequence_id in self.sequence_order:
            self.sequence_listbox.selection_set(self.sequence_order.index(self.selected_sequence_id))
        elif self.sequence_order:
            self.selected_sequence_id = self.sequence_order[0]
            self.sequence_listbox.selection_set(0)
        self._refresh_cue_list()

    def _refresh_cue_list(self) -> None:
        self.cue_listbox.delete(0, tk.END)
        self.cue_order = []
        if self.selected_sequence_id is None or self.selected_sequence_id not in self.controller.state.sequences:
            self.sequence_cyclic_var.set(False)
            return
        sequence = self.controller.state.sequences[self.selected_sequence_id]
        self.sequence_cyclic_var.set(sequence.cyclic)
        for index, cue in enumerate(sequence.cues, start=1):
            scene = self.controller.state.scenes.get(cue.scene_id)
            trigger = cue.trigger_mode.value.upper()
            line = f"{index}. {(scene.name if scene is not None else cue.scene_id)} | {cue.transition.fade_in_ms}ms | {trigger}"
            self.cue_listbox.insert(tk.END, line)
            self.cue_order.append(cue.id)

    def _refresh_scene_combo(self) -> None:
        scenes = sorted(self.controller.state.scenes.values(), key=lambda scene: scene.name.lower())
        self.scene_name_to_id = {scene.name: scene.id for scene in scenes}
        self.sequence_scene_combo.configure(values=[scene.name for scene in scenes])
        if scenes and not self.sequence_scene_var.get():
            self.sequence_scene_var.set(scenes[0].name)

    def _selected_scene_states(self) -> dict[int, FixtureState]:
        if self.selected_scene_id and self.selected_scene_id in self.controller.state.scenes:
            return self.controller.state.scenes[self.selected_scene_id].fixture_states
        return self.controller.get_live_output_states()

    def _on_fixture_tree_selected(self, _event=None) -> None:
        selection = self.fixture_tree.selection()
        if not selection:
            return
        self._select_setup_fixture(int(selection[0]), update_tree=False)

    def _select_setup_fixture(self, fixture_id: int, *, update_tree: bool = True) -> None:
        self.setup_selected_fixture_id = fixture_id
        fixture = self._fixture_by_id(fixture_id)
        self.fixture_address_var.set(fixture.start_address)
        self.fixture_channels_var.set(fixture.num_channels)
        self.fixture_x_var.set(fixture.position[0])
        self.fixture_y_var.set(fixture.position[1])
        self.fixture_angle_var.set(fixture.angle)
        if update_tree:
            self.fixture_tree.selection_set(str(fixture_id))
            self.fixture_tree.focus(str(fixture_id))
        self._refresh_views()

    def _drag_setup_fixture(self, fixture_id: int, position: tuple[int, int]) -> None:
        fixture = self._fixture_by_id(fixture_id)
        if fixture.position == position:
            return
        self.controller.update_fixture_patch(fixture_id, position=position)
        if self.setup_selected_fixture_id != fixture_id:
            self._select_setup_fixture(fixture_id)
            return
        self.fixture_x_var.set(position[0])
        self.fixture_y_var.set(position[1])
        self._refresh_lists()
        self._refresh_views()

    def _commit_setup_position_from_editor(self, _event=None):
        if self.setup_selected_fixture_id is None:
            return None
        try:
            position = (self.fixture_x_var.get(), self.fixture_y_var.get())
        except tk.TclError:
            return None
        fixture = self._fixture_by_id(self.setup_selected_fixture_id)
        if fixture.position == position:
            return None
        self.controller.update_fixture_patch(self.setup_selected_fixture_id, position=position)
        self._refresh_lists()
        self._refresh_views()
        return None

    def _save_fixture_patch(self) -> None:
        if self.setup_selected_fixture_id is None:
            return
        if not self._validate_fixture_patch(self.setup_selected_fixture_id, self.fixture_address_var.get(), self.fixture_channels_var.get()):
            return
        self.controller.update_fixture_patch(
            self.setup_selected_fixture_id,
            start_address=self.fixture_address_var.get(),
            num_channels=self.fixture_channels_var.get(),
            position=(self.fixture_x_var.get(), self.fixture_y_var.get()),
            angle=self.fixture_angle_var.get(),
        )
        self._refresh_lists()
        self._refresh_views()

    def _add_fixture(self) -> None:
        start_address = simpledialog.askinteger("Add Fixture", "Start address", initialvalue=max((fixture.start_address + fixture.num_channels for fixture in self.controller.fixtures), default=1))
        if start_address is None:
            return
        num_channels = simpledialog.askinteger("Add Fixture", "Number of channels", initialvalue=5, minvalue=1, maxvalue=32)
        if num_channels is None:
            return
        if not self._validate_fixture_patch(None, start_address, num_channels):
            return
        position = (60 + (len(self.controller.fixtures) % 4) * 130, 70 + (len(self.controller.fixtures) // 4) * 90)
        fixture = self.controller.add_fixture(start_address=start_address, num_channels=num_channels, position=position)
        self.setup_selected_fixture_id = fixture.fixture_id
        self._refresh_lists()
        self.fixture_tree.selection_set(str(fixture.fixture_id))
        self._on_fixture_tree_selected()

    def _validate_fixture_patch(self, fixture_id: int | None, start_address: int, num_channels: int) -> bool:
        if start_address < 1 or start_address > 512:
            messagebox.showerror("Fixture Error", "Start address must be between 1 and 512.")
            return False
        if num_channels < 1 or start_address + num_channels - 1 > 512:
            messagebox.showerror("Fixture Error", "Fixture exceeds the 512-channel DMX universe.")
            return False
        end_address = start_address + num_channels - 1
        for fixture in self.controller.fixtures:
            if fixture_id is not None and fixture.fixture_id == fixture_id:
                continue
            existing_end = fixture.start_address + fixture.num_channels - 1
            if start_address <= existing_end and end_address >= fixture.start_address:
                messagebox.showerror("Fixture Error", f"Fixture overlaps fixture {fixture.fixture_id}.")
                return False
        return True

    def _on_scene_selected(self, _event=None) -> None:
        selection = self.scene_listbox.curselection()
        if not selection:
            return
        self.selected_scene_id = self.scene_order[selection[0]]
        self.scene_selected_fixture_ids = set(self._selected_scene_states())
        self._populate_editor_from_states(self.scene_editor_vars, self._selected_scene_states(), self.scene_selected_fixture_ids)
        self._refresh_views()

    def _create_scene(self) -> None:
        name = simpledialog.askstring("New Scene", "Scene name", initialvalue=f"Scene {len(self.controller.state.scenes) + 1}")
        if not name:
            return
        scene = self.controller.create_scene(
            name,
            from_live_output=True,
            fixture_ids=self.scene_selected_fixture_ids,
        )
        self.selected_scene_id = scene.id
        self.scene_selected_fixture_ids = set(scene.fixture_states)
        self._refresh_lists()

    def _rename_scene(self) -> None:
        if self.selected_scene_id is None:
            return
        scene = self.controller.state.scenes[self.selected_scene_id]
        name = simpledialog.askstring("Rename Scene", "Scene name", initialvalue=scene.name)
        if name is None:
            return
        trimmed_name = name.strip()
        if not trimmed_name or trimmed_name == scene.name:
            return
        self.controller.rename_scene(self.selected_scene_id, trimmed_name)
        self._refresh_lists()

    def _duplicate_scene(self) -> None:
        if self.selected_scene_id is None:
            return
        source = self.controller.state.scenes[self.selected_scene_id]
        duplicate = self.controller.duplicate_scene(self.selected_scene_id, f"{source.name} Copy")
        self.selected_scene_id = duplicate.id
        self.scene_selected_fixture_ids = set(duplicate.fixture_states)
        self._refresh_lists()

    def _delete_scene(self) -> None:
        if self.selected_scene_id is None:
            return
        if len(self.controller.state.scenes) <= 1:
            messagebox.showwarning("Scene Error", "Keep at least one scene in the show file.")
            return
        self.controller.delete_scene(self.selected_scene_id)
        self.selected_scene_id = next(iter(self.controller.state.scenes), None)
        self.scene_selected_fixture_ids.clear()
        self._refresh_lists()

    def _apply_selected_scene(self) -> None:
        if self.selected_scene_id is None:
            return
        self.controller.apply_scene(self.selected_scene_id, fade_ms=max(0, self.scene_fade_var.get()))

    def _capture_live_to_scene(self) -> None:
        if self.selected_scene_id is None:
            return
        if not self.scene_selected_fixture_ids:
            messagebox.showwarning("Scene Update", "Select one or more fixtures before capturing a scene.")
            return
        live_states = self.controller.get_live_output_states()
        states = [live_states[fixture_id] for fixture_id in self.scene_selected_fixture_ids if fixture_id in live_states]
        self.controller.update_scene_states(self.selected_scene_id, states)
        self._refresh_views()

    def _apply_scene_editor_to_scene(self) -> None:
        if self.selected_scene_id is None:
            return
        if not self.scene_selected_fixture_ids:
            messagebox.showwarning("Scene Update", "Select one or more fixtures before updating a scene.")
            return
        states = self._build_states_from_editor(self.scene_editor_vars, self.scene_selected_fixture_ids)
        self.controller.update_scene_states(self.selected_scene_id, states)
        self._refresh_views()

    def _toggle_scene_fixture(self, fixture_id: int) -> None:
        if fixture_id in self.scene_selected_fixture_ids:
            self.scene_selected_fixture_ids.remove(fixture_id)
        else:
            self.scene_selected_fixture_ids.add(fixture_id)
        self._populate_editor_from_states(self.scene_editor_vars, self._selected_scene_states(), self.scene_selected_fixture_ids)
        self._refresh_views()

    def _toggle_show_fixture(self, fixture_id: int) -> None:
        if fixture_id in self.show_selected_fixture_ids:
            self.show_selected_fixture_ids.remove(fixture_id)
        else:
            self.show_selected_fixture_ids.add(fixture_id)
        self._populate_editor_from_states(self.override_editor_vars, self.controller.get_live_output_states(), self.show_selected_fixture_ids)
        self._refresh_views()

    def _on_scene_color_picked(self, red: int, green: int, blue: int) -> None:
        self.scene_editor_vars["red"].set(red)
        self.scene_editor_vars["green"].set(green)
        self.scene_editor_vars["blue"].set(blue)
        if self.scene_editor_vars["intensity"].get() == 0:
            self.scene_editor_vars["intensity"].set(255)

    def _on_override_color_picked(self, red: int, green: int, blue: int) -> None:
        self.override_editor_vars["red"].set(red)
        self.override_editor_vars["green"].set(green)
        self.override_editor_vars["blue"].set(blue)
        if self.override_editor_vars["intensity"].get() == 0:
            self.override_editor_vars["intensity"].set(255)

    def _create_sequence(self) -> None:
        name = simpledialog.askstring("New Sequence", "Sequence name", initialvalue=f"Sequence {len(self.controller.state.sequences) + 1}")
        if not name:
            return
        sequence = self.controller.create_sequence(name)
        self.selected_sequence_id = sequence.id
        self._refresh_lists()

    def _on_sequence_selected(self, _event=None) -> None:
        selection = self.sequence_listbox.curselection()
        if not selection:
            return
        self.selected_sequence_id = self.sequence_order[selection[0]]
        self._refresh_cue_list()

    def _load_selected_sequence(self) -> None:
        if self.selected_sequence_id is None:
            return
        self.controller.load_sequence(self.selected_sequence_id)
        self.sequence_paused = False
        self._rhythm_tap_times.clear()
        self.pause_button.configure(text="Pause")

    def _toggle_selected_sequence_cyclic(self) -> None:
        if self.selected_sequence_id is None:
            self.sequence_cyclic_var.set(False)
            return
        self.controller.set_sequence_cyclic(self.selected_sequence_id, self.sequence_cyclic_var.get())
        self._refresh_sequence_list()

    def _add_cue_to_sequence(self) -> None:
        if self.selected_sequence_id is None:
            return
        scene_name = self.sequence_scene_var.get()
        scene_id = self.scene_name_to_id.get(scene_name)
        if scene_id is None:
            return
        self.controller.add_cue_to_sequence(
            self.selected_sequence_id,
            scene_id,
            fade_in_ms=max(0, self.sequence_fade_ms_var.get()),
            hold_ms=max(0, self.sequence_hold_ms_var.get()),
            trigger_mode=TriggerMode(self.sequence_trigger_var.get()),
        )
        self._refresh_cue_list()

    def _remove_selected_cue(self) -> None:
        if self.selected_sequence_id is None:
            return
        selection = self.cue_listbox.curselection()
        if not selection:
            return
        cue_id = self.cue_order[selection[0]]
        self.controller.remove_cue_from_sequence(self.selected_sequence_id, cue_id)
        self._refresh_cue_list()

    def _go_next_cue(self) -> None:
        self.controller.go_next_cue()

    def _go_previous_cue(self) -> None:
        self.controller.go_previous_cue()

    def _toggle_sequence_pause(self) -> None:
        self.sequence_paused = not self.sequence_paused
        if self.sequence_paused:
            self.controller.pause_sequence()
            self.pause_button.configure(text="Resume")
        else:
            self.controller.resume_sequence()
            self.pause_button.configure(text="Pause")

    def _set_rhythm_bpm(self, bpm: float) -> int:
        clamped_bpm = max(RHYTHM_MIN_BPM, min(RHYTHM_MAX_BPM, int(round(float(bpm)))))
        try:
            current_value = self.rhythm_bpm_var.get()
        except tk.TclError:
            current_value = None
        if current_value != clamped_bpm:
            self.rhythm_bpm_var.set(clamped_bpm)
        self.controller.set_rhythm_bpm(clamped_bpm)
        return clamped_bpm

    def _commit_rhythm_bpm(self, _event=None):
        try:
            bpm = self.rhythm_bpm_var.get()
        except tk.TclError:
            self.rhythm_bpm_var.set(int(round(self.controller.rhythm_bpm)))
            return None
        self._set_rhythm_bpm(bpm)
        return None

    def _on_rhythm_slider_changed(self, value: str) -> None:
        self._set_rhythm_bpm(float(value))

    def _tap_rhythm_tempo(self) -> None:
        now = time.monotonic()
        if self._rhythm_tap_times and now - self._rhythm_tap_times[-1] > RHYTHM_TAP_RESET_SECONDS:
            self._rhythm_tap_times.clear()
        self._rhythm_tap_times.append(now)
        self._rhythm_tap_times = self._rhythm_tap_times[-5:]
        if len(self._rhythm_tap_times) < 2:
            return
        intervals = [
            current - previous
            for previous, current in zip(self._rhythm_tap_times, self._rhythm_tap_times[1:])
            if current > previous
        ]
        if not intervals:
            return
        average_interval = sum(intervals) / len(intervals)
        if average_interval <= 0:
            return
        self._set_rhythm_bpm(60.0 / average_interval)

    def _toggle_rhythm_play(self) -> None:
        loaded_sequence = self.controller.loaded_sequence
        if loaded_sequence is None:
            messagebox.showwarning("Rhythm Play", "Load a sequence into show mode before starting rhythm play.")
            return
        if not loaded_sequence.cues:
            messagebox.showwarning("Rhythm Play", "Add at least one cue to the loaded sequence before starting rhythm play.")
            return
        if self.controller.is_rhythm_playing:
            self.controller.stop_rhythm_play()
            self._refresh_views()
            return
        self._commit_rhythm_bpm()
        if self.controller.is_sequence_paused:
            self.sequence_paused = False
            self.controller.resume_sequence()
        cue = self.controller.start_rhythm_play()
        if cue is None:
            messagebox.showwarning("Rhythm Play", "The loaded sequence could not be started.")
            self.controller.stop_rhythm_play()
        self._refresh_views()

    def _apply_show_override(self) -> None:
        selected_ids = self.show_selected_fixture_ids or ({self.controller.fixtures[0].fixture_id} if self.controller.fixtures else set())
        states = self._build_states_from_editor(self.override_editor_vars, selected_ids)
        self.controller.apply_override(states)

    def _on_scene_auto_apply_toggled(self) -> None:
        if self.scene_auto_apply_var.get():
            self._auto_apply_scene_editor()

    def _on_override_auto_apply_toggled(self) -> None:
        if self.override_auto_apply_var.get():
            self._auto_apply_show_override()

    def _auto_apply_scene_editor(self) -> None:
        if not self.scene_auto_apply_var.get() or self.selected_scene_id is None or not self.scene_selected_fixture_ids:
            return
        states = self._build_states_from_editor(self.scene_editor_vars, self.scene_selected_fixture_ids)
        self.controller.update_scene_states(self.selected_scene_id, states)
        self.controller.apply_scene(self.selected_scene_id, fade_ms=0)

    def _auto_apply_show_override(self) -> None:
        if not self.override_auto_apply_var.get() or not self.show_selected_fixture_ids:
            return
        states = self._build_states_from_editor(self.override_editor_vars, self.show_selected_fixture_ids)
        self.controller.apply_override(states)

    def _release_override(self) -> None:
        self.controller.clear_override()

    def _record_override(self) -> None:
        self.controller.record_override_to_current_scene()
        self._refresh_lists()

    def _build_states_from_editor(self, variables: dict[str, tk.IntVar], fixture_ids: set[int]) -> list[FixtureState]:
        return [
            FixtureState(
                fixture_id=fixture_id,
                intensity=variables["intensity"].get(),
                red=variables["red"].get(),
                green=variables["green"].get(),
                blue=variables["blue"].get(),
                white=variables["white"].get(),
            )
            for fixture_id in fixture_ids
        ]

    def _scene_preview_states(self) -> dict[int, FixtureState]:
        base_states = dict(self._selected_scene_states())
        if not self.scene_selected_fixture_ids:
            return base_states
        for state in self._build_states_from_editor(self.scene_editor_vars, self.scene_selected_fixture_ids):
            base_states[state.fixture_id] = state
        return base_states

    def _show_preview_states(self) -> dict[int, FixtureState]:
        base_states = dict(self.controller.get_live_output_states())
        if not self.show_selected_fixture_ids:
            return base_states
        for state in self._build_states_from_editor(self.override_editor_vars, self.show_selected_fixture_ids):
            base_states[state.fixture_id] = state
        return base_states

    def _bind_level_var_traces(self, variables: dict[str, tk.IntVar], editor_name: str) -> None:
        for variable in variables.values():
            variable.trace_add("write", lambda *_args, name=editor_name: self._on_level_preview_changed(name))

    def _on_level_preview_changed(self, editor_name: str) -> None:
        if self._suspend_editor_callbacks:
            return
        if editor_name == "scene":
            self._auto_apply_scene_editor()
        else:
            self._auto_apply_show_override()
        if hasattr(self, "scene_stage"):
            self._refresh_views()

    def _populate_editor_from_states(
        self,
        variables: dict[str, tk.IntVar],
        states: dict[int, FixtureState],
        selected_ids: set[int],
    ) -> None:
        self._suspend_editor_callbacks = True
        try:
            fixture_id = next(iter(selected_ids), None)
            if fixture_id is None or fixture_id not in states:
                for variable in variables.values():
                    variable.set(0)
                return
            state = states[fixture_id]
            variables["intensity"].set(state.intensity)
            variables["red"].set(state.red)
            variables["green"].set(state.green)
            variables["blue"].set(state.blue)
            variables["white"].set(state.white)
        finally:
            self._suspend_editor_callbacks = False

    def _load_show(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Show Files", "*.json"), ("JSON Files", "*.json")])
        if not path:
            return
        try:
            show_file = self.repository.load(path)
            self.controller.load_show_file(show_file)
        except Exception as exc:
            messagebox.showerror("Load Error", str(exc))
            return
        self.show_file_path = path
        self.selected_scene_id = next(iter(self.controller.state.scenes), None)
        self.selected_sequence_id = next(iter(self.controller.state.sequences), None)
        if self.selected_sequence_id is not None:
            self.controller.load_sequence(self.selected_sequence_id)
        self._refresh_lists()
        self._refresh_views()

    def _save_show(self) -> None:
        path = self.show_file_path or filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("Show Files", "*.json"), ("JSON Files", "*.json")])
        if not path:
            return
        try:
            self.repository.save(path, self.controller.build_show_file())
        except Exception as exc:
            messagebox.showerror("Save Error", str(exc))
            return
        self.show_file_path = path

    def _output_status_text(self) -> str:
        if self.controller.is_output_enabled:
            return "Live DMX"
        if self.transport_error is not None:
            return f"Simulation ({self.transport_error})"
        return "Simulation"

    def _transport_status_text(self) -> str:
        if self.controller.state.blackout:
            return "Blackout"
        if self.controller.is_fading:
            return "Fading"
        if self.controller.current_cue is not None and self.controller.is_sequence_paused:
            return "Paused"
        if self.controller.is_rhythm_playing:
            return f"Rhythm {int(round(self.controller.rhythm_bpm))} BPM"
        if self.controller.current_cue is not None:
            return "Running"
        if self.controller.loaded_sequence is not None:
            return "Ready"
        return "Idle"

    def _live_fixture_display_states(self) -> dict[int, FixtureState]:
        if self.controller.state.blackout:
            return {
                fixture.fixture_id: FixtureState(fixture_id=fixture.fixture_id)
                for fixture in self.controller.fixtures
            }

        live_states = self.controller.get_live_output_states()
        return {
            fixture.fixture_id: self._apply_master_dimmer_to_state(
                live_states.get(fixture.fixture_id, FixtureState(fixture_id=fixture.fixture_id))
            )
            for fixture in self.controller.fixtures
        }

    def _apply_master_dimmer_to_state(self, state: FixtureState) -> FixtureState:
        master_dimmer = self.controller.state.master_dimmer
        if master_dimmer >= 1.0:
            return state

        return FixtureState(
            fixture_id=state.fixture_id,
            intensity=int(state.intensity * master_dimmer),
            red=int(state.red * master_dimmer),
            green=int(state.green * master_dimmer),
            blue=int(state.blue * master_dimmer),
            white=int(state.white * master_dimmer),
        ).normalized()

    def _resize_live_fixture_stage(self, _event=None) -> None:
        if not hasattr(self, "live_fixture_stage_host"):
            return

        available_width = self.live_fixture_stage_host.winfo_width()
        available_height = self.live_fixture_stage_host.winfo_height()
        if available_width <= 1 or available_height <= 1:
            return

        self.live_fixture_stage.place(x=0, y=0, width=available_width, height=available_height)
        self.live_fixture_stage.redraw()

    def _toggle_blackout(self) -> None:
        self.controller.set_blackout(not self.controller.state.blackout)

    def _on_master_changed(self, value: str) -> None:
        self.controller.set_master_dimmer(float(value))

    def _fixture_by_id(self, fixture_id: int) -> Fixture:
        for fixture in self.controller.fixtures:
            if fixture.fixture_id == fixture_id:
                return fixture
        raise KeyError(fixture_id)