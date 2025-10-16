from indu_doc.common_page_utils import PageType, detect_page_type
from indu_doc.table_extractor import extract_tables
from indu_doc.page_settings import PageSetup, TableSetup, PageSettings

from typing import Any
from pathlib import Path
import pandas as pd
import pymupdf  # type: ignore
import copy
import traceback
import re

from page_setup_wizard.interactive_roi_setup import InteractiveROISetup

# Default table setup
# Syntax for names: lowercase. Start with '_' to indicate a hidden field
INITIAL_SETUP: dict[PageType, PageSetup] = {
    PageType.CONNECTION_LIST : PageSetup(tables={
        "main": TableSetup(
            key_columns={
                "name": "connection name",
                "src_pin_tag": "source tag with connection point",
                "dst_pin_tag": "destination tag with connection point"
            }
        )
    }),
    PageType.DEVICE_TAG_LIST : PageSetup(tables={
        "main": TableSetup(
            key_columns={
                "tag": "device tag",
            }
        )
    }),
    PageType.CABLE_OVERVIEW : PageSetup(tables={
        "main": TableSetup(
            key_columns={
                "cable_tag": "cable designation",
                "src_tag": "source tag",
                "dst_tag": "destination tag", 
            }
        )
    }),
    PageType.CABLE_DIAGRAM : PageSetup(tables={
        "main": TableSetup(
            key_columns={
                "src_tag": "source tag",
                "src_pin": "source connection point",
                "dst_tag": "destination tag",
                "dst_pin": "destination connection point",
                "cable_tag": "", # not sure I need it here
            }
        )
    }),
    PageType.CABLE_PLAN : PageSetup(tables={
        "area_cable_name": TableSetup(
            description="cable tag (only)",
            key_columns={}
        ),
        "table_left": TableSetup(
            key_columns={
                "src_pin_tag": "source tag with connection point",
            }
        ),
        "table_right": TableSetup(
            key_columns={
                "dst_pin_tag": "destination tag with connection point",
            }
        ),
        "table_typ": TableSetup(
            key_columns={}
        )
    }),
    PageType.TOPOLOGY : PageSetup(tables={
        "main": TableSetup(
            key_columns={
                "designation": "designation tag (cable tag)",
                "src_tags": "source tag(s)",
                "dst_tags": "destination tag(s)",
                "route": "routing track",
            }
        )
    }),
    PageType.TERMINAL_DIAGRAM : PageSetup(tables={
        "l_cables": TableSetup(
            description="left side cable list",
            key_columns={
                "cable_tag": "cable tag"
            }
        ),
        "l_conn": TableSetup(
            description="left side cable assignment",
            key_columns={}
        ),
        "r_cables": TableSetup(
            description="right side cable list",
            key_columns={
                "cable_tag": "cable tag"
            }
        ),
        "r_conn": TableSetup(
            description="right side cable assignment",
            key_columns={}
        ),
        "strip_name": TableSetup(
            description="area with strip name text (only)",
            text_only=True
        ),
        "main": TableSetup(
            description="central table with all main info",
            key_columns={
                "cable_pin": "cable connection point",
                "src_tag": "source tag",
                "src_pin": "source connection point",
                "dst_tag": "destination tag",
                "dst_pin": "destination connection point",
                # TODO jumpers?
            }
        )
    }),
    PageType.WIRES_PART_LIST : PageSetup(tables={
        "main": TableSetup(
            key_columns={
                "src_pin_tag": "source tag with connection point",
                "dst_pin_tag": "destination tag with connection point",
                "route": "routing track",
            }
        )
    }),
    PageType.STRUCTURE_IDENTIFIER_OVERVIEW : PageSetup(tables={
        "main": TableSetup(
            key_columns={
                "tag": "designation tag (separator&name)",
            }
        )
    }),
    PageType.PLC_DIAGRAM : PageSetup(tables={
        "main": TableSetup(
            key_columns={
                "tag": "PLC device tag",
                "plc_addr": "PLC address (%)",
            }
        )
    }),
}

import click

def do_main_loop(pdf: pymupdf.Document, settings: PageSettings):

    while True:
        # Select page for setup
        types = list(PageType)
        click.echo("Select page type for setup (0 to finish): ")
        for i, type in enumerate(types, 1):
            ready = type in settings
            click.echo(f"  {i}) {type.value} {"(ready)" if ready else ""}")
        choice = click.prompt("Enter number", type=int)
        if not (1 <= choice <= len(types)):
            click.echo("Invalid choice, exiting")
            return
        selected_type = types[choice - 1] 

        # determine if its already exists
        do_setup = True
        if selected_type in settings:
            choice = click.prompt(f"Settings for type '{selected_type.value}' are already set. Do you want to 't'est or 'o'verwrite them?", type=str)
            if choice.lower() == "o":
                setup = INITIAL_SETUP[selected_type]
            else:
                do_setup = False
                setup = settings[selected_type]
        else:
            setup = INITIAL_SETUP[selected_type]
            
        # make deep copy so invalid changes are not saved
        setup = copy.deepcopy(setup)
        # get example page num
        page_num = click.prompt("Enter example page number", type=int)
        #
        try:
            page = pdf[page_num - 1]
            if do_setup: 
                do_page_setup(page, selected_type, setup) # edits inplace
            do_extraction_test(page, type, setup)
        except:
            click.echo(f"One or more fatal errors occured:")
            traceback.print_exc()
            click.echo("Skipped\n")
            continue

        settings[selected_type] = setup
        settings.save()
        click.echo(f"Saved\n")


def do_extraction_test(page: pymupdf.Page, type: PageType, page_setup: PageSetup):
    click.echo("Doing extraction test...")
    # validate search name
    detected_type = detect_page_type(page, {type: page_setup.search_name})
    if detected_type != type:
        raise ValueError(f"Detected page type does not match required: expected {type}, got {detected_type}")
    #
    dfs, errors = extract_tables(page, page_setup) # can throw
    click.echo(f"Test success - no fatal errors")
    for e in errors:
        click.echo(f"{e.error_type}: {e.message}")
    for name, df in dfs.items():
        click.echo(f"Table {name} extraction result: ")
        print(df)


def do_table_setup(page: pymupdf.Page, table_setup: TableSetup, tables: list[Any]):
    ''' Edits table_setup inplace '''
    # if = 0 tables, exit with error
    if len(tables) == 0:
        raise ValueError("Selected ROI has no tables inside")
    #
    table_setup.expected_num_tables = len(tables)
    # if > 1 table, ask how to merge
    if len(tables) > 1:
        click.echo(f"Detected multiple ({len(tables)}) tables inside ROI")
        join = click.confirm("Do you intend to merge them?")
        if not join:
            raise ValueError("Selected ROI has multiple tables inside")
        no_header = not click.confirm("Do all tables have header row?")
        #
        table_setup.on_many_join = join
        table_setup.on_many_no_header = no_header
    
    #
    click.echo(f"Do NOT add overlap detection everywhere as it is very demanding operation!")
    has_overlaps = click.confirm("Has table text overlaps?")
    if has_overlaps:
        tool = InteractiveROISetup(page, "Select area larger than the table itself so text out of table bound can be detected. Select area where is no vertical text", dpi=150)
        roi, *_ = tool.run()
        table_setup.overlap_test_roi = roi

    # convert table[0] to df
    df = tables[0].to_pandas()

    # print table[0] header and ask if
    row_offset = 0 
    header = df.columns
    while True:
        if row_offset == 0:
            header = df.columns
        elif row_offset > 0:
            header = df.iloc[row_offset - 1].values
        else:
            header = [""] * len(df.columns) 
        click.echo(f"Detected {len(df.columns)} column header: {header}")
        choice = click.prompt("Is table header detected correctly? If no, enter 'u' to select upper row as a header, 'd' to select lower row as a header [y/u/d]", type=str)
        if choice.lower() == "u":
            row_offset-= 1
        elif choice.lower() == "d":
            row_offset+= 1
        else: # if choice.lower() == "y"
            break

    table_setup.row_offset = row_offset

    # ask to indicate key columns
    header_map = {idx+1: h for idx, h in enumerate(header)}
    new_map: dict[int, dict[str, Any]] = {}

    click.echo("Detected column names & indexes: ")
    for i, title in header_map.items():
        click.echo(f"  {i}) {title}")

    for name, descr in table_setup.key_columns.items():
        choice = click.prompt(f"Select column number which has {descr}", type=int)
        while choice in new_map:
            click.prompt(f"This column is already taken, try again:", type=int)
        while choice not in header_map:
            click.prompt(f"Invalid, try again", type=int)
        new_map[choice] = { "name": name }

    # out of the left out column names ask to select attributes (and enter names) (store idx)
    click.echo("Edit attribute columns: ")
    click.echo("\t<name> to change attribute name")
    click.echo("\tempty to keep attribute name")
    click.echo("\t/i to ignore attribute")
    click.echo("\t/f<X> <name> to change attribute name & do forward fill by string X")
    attr_map = {k: v for k, v in header_map.items() if k not in new_map}
    for i, title in attr_map.items():
        click.echo(f"Edit attribute (column #{i}) '{title}':")
        name = click.prompt(f"Enter new attribute name", type=str, default="", show_default=False)
        ignore = False
        ffill = None
        if not name:
            name = title
        elif name.lower() == "/i":
            name = f"Ignored{i}"
            ignore = True
        elif name.startswith("/f"):
            match = re.match(r"^/f(\S*)\s+(\S+)$", name)
            if not match:
                raise ValueError("Invalid forward fill command")
            ffill = match.group(1)  # may be empty
            name = match.group(2)

        new_map[i] = {
            "name": name,
            "ignore": ignore
        }
        if ffill:
            new_map[i]["ffill"] = ffill
    
    # print new header map
    new_map = dict(sorted(new_map.items()))
    click.echo(f"New column names: {[v["name"] for v in new_map.values()]}")

    # save (TODO very very nasty format)
    for v in new_map.values():
        if "ffill" in v:
            table_setup.columns[v["name"]] = (not v.get("ignore", False), v["ffill"])
        else:
            table_setup.columns[v["name"]] = (not v.get("ignore", False))
    print(table_setup.columns)


def do_text_setup(page: pymupdf.Page, table_setup: TableSetup, texts: list[Any]):
    ''' Edits table_setup inplace '''
    # if = 0 tables, exit with error
    if len(texts) == 0:
        raise ValueError("Selected ROI has no tables inside")
    #
    table_setup.expected_num_tables = len(texts)
    #
    if len(texts) > 1:
        click.echo(f"Detected multiple ({len(texts)}) texts inside ROI")
        join = click.confirm("Do you intend to merge them?")
        if not join:
            raise ValueError("Selected ROI has multiple tables inside")
        
    # just accept it (later may be allow columns setup by multiple texts detection)


def do_page_setup(page: pymupdf.Page, type: PageType, page_setup: PageSetup) -> PageSetup:
    ''' Edits page_setup inplace '''
    # For each table:
    click.echo("\n=== Page Setup Wizard ===")
    click.echo(f"Hint: {page_setup.description}\n")
    # prompt page name
    search_name = click.prompt("Insert page name (hint: you can find it in bold at the top of the page)", type=str)
    if not search_name:
        raise ValueError("Selected empty search name")
    
    # Validate search_name
    page_setup.search_name = search_name
    detected_type = detect_page_type(page, {type: search_name})
    if detected_type != type:
        raise ValueError(f"Detected page type does not match required: expected {type}, got {detected_type}")

    click.echo(f"You must locate {len(page_setup.tables)} table(s) on this page")
    for key, table_setup in page_setup.tables.items():
        # ask for roi
        click.echo(
            f"Working with {'text area' if table_setup.text_only else 'table'} '{key}' containing '{table_setup.description}'. \n"
            "Controls INSIDE ROI editor: \n"
            "\tPress 't' to test ROI.\n"
            "\tPress 'c' to add column divider at mouse pos.\n"
            "\tPress 'r' to reset selection.\n"
            "\tPress 'Enter' to finalize selection.")
        input(f"Press any key to open ROI editor")
        #
        tool = InteractiveROISetup(
            page, 
            f"Select area where {page_setup.description}. Select a bit bigger than the table itself", 
            dpi=150, 
            text_mode=table_setup.text_only
        )
        roi, lines, tables, texts = tool.run()
        table_setup.lines = lines
        table_setup.roi = roi
        if table_setup.text_only:
            do_text_setup(page, table_setup, texts)
        else:
            do_table_setup(page, table_setup, tables)
        
   
    click.echo("Finished setup")
    return page_setup