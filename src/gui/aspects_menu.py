import logging
from typing import Any, Dict, List, Optional, OrderedDict

from nicegui import ui

from indu_doc.configs import AspectsConfig, LevelConfig, default_configs

logger = logging.getLogger(__name__)
# Load aspects from config.json if present, otherwise use defaults


def load_aspects() -> List[LevelConfig]:
    # Build aspects list from default_configs (AspectsConfig) provided by configs.py
    try:
        # default_configs.levels is an OrderedDict where keys are separators and
        # values are LevelConfig objects in the correct order
        logger.debug(f"Loaded default aspects: {default_configs}")
        return default_configs.to_list()
    except Exception as e:
        # fallback: minimal built-in defaults
        logger.debug(f"Using fallback aspects due to error: {e}")
        aspects = [
            LevelConfig(Separator='=', Aspect='Functional'),
            LevelConfig(Separator='+', Aspect='Location'),
        ]
        return aspects


def create_aspect_row_for_dialog(aspect: LevelConfig, index: int, mutable_aspects: List[LevelConfig], rebuild_callback):
    """Create a single editable row inside the configuration dialog.

    This uses inputs bound to the `aspects` list so edits update the in -memory model.
    Reorder operations will re-open the dialog to reflect the updated order.
    """
    # Responsive row: separator | label
    with ui.row().classes('w-full items-center gap-2'):
        # separator (single char)
        ui.input(value=aspect.Separator, placeholder='sep', on_change=lambda e, i=index: mutable_aspects.__setitem__(
            i, LevelConfig(Separator=e.value, Aspect=mutable_aspects[i].Aspect))).classes('w-16')

        # label edit
        ui.input(value=aspect.Aspect, on_change=lambda e, i=index: mutable_aspects.__setitem__(
            i, LevelConfig(Separator=mutable_aspects[i].Separator, Aspect=e.value))).classes('flex-1 min-w-0')

        # controls column: up/down + delete
        with ui.column().classes('gap-1 items-center'):
            if index != 0:
                ui.button(icon='arrow_drop_up', on_click=lambda _, i=index: do_swap(
                    i, i-1, mutable_aspects, rebuild_callback)).props('flat dense').classes('p-0 m-0')
            ui.button(icon='delete', on_click=lambda _, i=index: remove_aspect(
                i, mutable_aspects, rebuild_callback)).props('flat dense').classes('p-0 m-0 text-red-600')
            if index != len(mutable_aspects) - 1:
                ui.button(icon='arrow_drop_down', on_click=lambda _, i=index: do_swap(
                    i, i+1, mutable_aspects, rebuild_callback)).props('flat dense').classes('p-0 m-0')


def do_swap(a: int, b: int, aspects: List[LevelConfig], rebuild_callback):
    # swap indices if valid, then rebuild the rows in-place
    if 0 <= b < len(aspects):
        aspects[a], aspects[b] = aspects[b], aspects[a]
        try:
            rebuild_callback()
        except Exception:
            pass


def remove_aspect(index: int, aspects: List[LevelConfig], rebuild_callback):
    if 0 <= index < len(aspects):
        aspects.pop(index)
        try:
            rebuild_callback()
        except Exception:
            pass


def open_configuration_dialog(aspects: List[LevelConfig]):
    """Dynamically create and open a dialog that allows editing, reordering, and saving aspects.

    The rows are placed inside a container that can be cleared and rebuilt so reordering/add
    happen in -place without closing the dialog.
    """

    mutable_aspects = aspects.copy()  # work on a copy until saved

    # dialog + responsive card (max width 90vw or 900px) and tall but scrollable content
    with ui.dialog() as config_dialog, ui.card().classes('w-[min(90vw,900px)]'):
        ui.label('Edit Aspects').classes('text-lg font-semibold p-4')

        # editable rows container (responsive height)
        rows_container = ui.column().classes(
            'w-full max-h-[68vh] overflow-auto gap-2 p-4')

        def rebuild_rows():
            # clear and repopulate the rows container
            rows_container.clear()
            for i, aspect in enumerate(mutable_aspects):
                with rows_container:
                    create_aspect_row_for_dialog(
                        aspect, i, mutable_aspects, rebuild_rows)

        # initial build
        rebuild_rows()

        def save_and_close(aspects_to_save: List[LevelConfig], dialog):
            # convert to AspectsConfig and save back to the original list
            aspects.clear()
            aspects.extend(mutable_aspects)
            dialog.close()
            ui.notify('Aspects saved')

        # footer actions (sticky at bottom of card area)
        with ui.row().classes('justify-between items-center gap-2 mt-2'):
            with ui.row().classes('gap-2'):
                ui.button('Discard', on_click=config_dialog.close).props('flat')
                ui.button('Save', on_click=lambda: save_and_close(
                    mutable_aspects, config_dialog)).props('flat primary')
                ui.button('Add', on_click=lambda _: add_aspect_inplace(
                    mutable_aspects, rebuild_rows)).props('flat')

    # open after construction
    config_dialog.open()


def make_config_opener(aspects: List[LevelConfig]):
    """Return a lightweight object with an open() method that opens the live dialog."""
    from types import SimpleNamespace
    return SimpleNamespace(open=lambda: open_configuration_dialog(aspects), close=lambda: None)


def add_aspect_inplace(aspects: List[LevelConfig], rebuild_callback):
    aspects.append(LevelConfig(Separator='', Aspect='New Aspect'))
    try:
        rebuild_callback()
    except Exception:
        pass
