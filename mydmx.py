#%%

#%%
from __future__ import annotations

import tkinter as tk

from engine import EngineController
from fixture import Fixture
from gui import MainApplication
from storage import ShowRepository

try:
    from communication import DMXUpdateManager, UDMX
except Exception as exc:  # pragma: no cover - environment dependent import
    DMXUpdateManager = None
    UDMX = None
    COMMUNICATION_ERROR = exc
else:
    COMMUNICATION_ERROR = None


def create_default_fixtures() -> list[Fixture]:
    fixtures: list[Fixture] = []
    for index in range(12):
        row = index // 6
        column = index % 6
        fixtures.append(
            Fixture(
                fixture_id=index + 1,
                start_address=index * 16 + 1,
                num_channels=5,
                position=(90 + column * 100, 100 + row * 160),
                angle=0,
            )
        )
    return fixtures


def create_update_manager() -> tuple[object | None, Exception | None]:
    if DMXUpdateManager is None or UDMX is None:
        return None, COMMUNICATION_ERROR
    try:
        return DMXUpdateManager(UDMX()), None
    except Exception as exc:  # pragma: no cover - hardware dependent
        return None, exc

#%%
def main() -> None:
    update_manager, transport_error = create_update_manager()
    controller = EngineController(create_default_fixtures(), update_manager)
    repository = ShowRepository()

    root = tk.Tk()
    root.title("MyDMX")
    root.geometry("1400x860")

    app = MainApplication(root, controller, repository, transport_error=transport_error)

    def handle_close() -> None:
        if update_manager is not None and getattr(update_manager, "dmx", None) is not None:
            update_manager.dmx.cleanup()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", handle_close)
    root.mainloop()


if __name__ == "__main__":
    main()