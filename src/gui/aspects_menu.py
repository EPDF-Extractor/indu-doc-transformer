import logging
from typing import Any, Dict, List, Optional, OrderedDict

from nicegui import ui

from indu_doc.configs import AspectsConfig, LevelConfig, default_configs

logger = logging.getLogger(__name__)
# Load aspects from config.json if present, otherwise use defaults


def load_default_aspects() -> List[LevelConfig]:
    # Build aspects list from default_configs (AspectsConfig) provided by configs.py
    try:
        logger.debug(f"Trying to load default aspects: {default_configs}")
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
    """Create a single editable row inside the configuration dialog."""
    with ui.row().classes('w-full items-center gap-2'):
        # separator (single char)
        ui.input(value=aspect.Separator, placeholder='sep', on_change=lambda e, i=index: mutable_aspects.__setitem__(
            i, LevelConfig(Separator=e.value, Aspect=mutable_aspects[i].Aspect))).classes('w-16').props('dark outlined')

        # label edit
        ui.input(value=aspect.Aspect, on_change=lambda e, i=index: mutable_aspects.__setitem__(
            i, LevelConfig(Separator=mutable_aspects[i].Separator, Aspect=e.value))).classes('flex-1 min-w-0').props('dark outlined')

        # controls column: up/down + delete
        with ui.column().classes('gap-1 items-center'):
            if index != 0:
                ui.button(icon='arrow_drop_up', on_click=lambda _, i=index: do_swap(
                    i, i-1, mutable_aspects, rebuild_callback)).props('flat dense color=blue-5').classes('p-0 m-0')
            ui.button(icon='delete', on_click=lambda _, i=index: remove_aspect(
                i, mutable_aspects, rebuild_callback)).props('flat dense color=red-5').classes('p-0 m-0')
            if index != len(mutable_aspects) - 1:
                ui.button(icon='arrow_drop_down', on_click=lambda _, i=index: do_swap(
                    i, i+1, mutable_aspects, rebuild_callback)).props('flat dense color=blue-5').classes('p-0 m-0')


def do_swap(a: int, b: int, mutable_aspects: List[LevelConfig], rebuild_callback):
    # swap indices if valid, then rebuild the rows in-place
    if 0 <= b < len(mutable_aspects):
        mutable_aspects[a], mutable_aspects[b] = mutable_aspects[b], mutable_aspects[a]
        try:
            rebuild_callback()
        except Exception:
            pass


def remove_aspect(index: int, mutable_aspects: List[LevelConfig], rebuild_callback):
    if 0 <= index < len(mutable_aspects):
        mutable_aspects.pop(index)
        try:
            rebuild_callback()
        except Exception:
            pass


def add_aspect_inplace(mutable_aspects: List[LevelConfig], rebuild_callback):
    """Add a new empty aspect and rebuild the dialog rows."""
    mutable_aspects.append(LevelConfig(Separator='', Aspect=''))
    try:
        rebuild_callback()
    except Exception:
        pass


def open_configuration_dialog(aspects: List[LevelConfig]):
    """Dynamically create and open a dialog that allows editing, reordering, and saving aspects."""

    mutable_aspects = aspects.copy()

    # dialog + responsive card (max width 90vw or 900px) and tall but scrollable content
    with ui.dialog() as config_dialog, ui.card().classes('w-[min(90vw,900px)] bg-gray-800 border-2 border-gray-600'):
        ui.label('Edit Aspects').classes('text-xl font-bold p-4 text-white')

        # editable rows container (responsive height)
        rows_container = ui.column().classes(
            'w-full max-h-[68vh] overflow-auto gap-2 p-4 bg-gray-900 rounded-lg')

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
            # validate that no separators are empty and unique, aspect names non-empty
            separators = [a.Separator for a in aspects_to_save]
            aspect_names = [a.Aspect for a in aspects_to_save]
            if not all(separators) or len(separators) != len(set(separators)):
                ui.notify(
                    'Invalid separators (ensure non-empty and unique)', color='negative')
                return
            if not all(aspect_names):
                ui.notify('Invalid aspect names (ensure non-empty)',
                          color='negative')
                return
            aspects.clear()
            aspects.extend(mutable_aspects)
            dialog.close()
            ui.notify('Aspects saved')

        # footer actions (sticky at bottom of card area)
        with ui.row().classes('justify-between items-center gap-2 mt-2 p-4 bg-gray-800'):
            ui.button('Add', on_click=lambda _: add_aspect_inplace(
                mutable_aspects, rebuild_rows)).props('flat color=green-5').classes('font-semibold')

            with ui.row().classes('gap-2'):
                ui.button('Discard', on_click=config_dialog.close).props(
                    'flat color=grey-5').classes('font-semibold')
                ui.button('Save', on_click=lambda: save_and_close(
                    mutable_aspects, config_dialog)).props('color=blue-6').classes('font-semibold')

    # open after construction
    config_dialog.open()


def make_config_opener(aspects: List[LevelConfig]):
    """Return a lightweight object with an open() method that opens the live dialog."""
    from types import SimpleNamespace
    return SimpleNamespace(open=lambda: open_configuration_dialog(aspects), close=lambda: None)
