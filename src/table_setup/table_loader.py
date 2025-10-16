from indu_doc.common_page_utils import PageType, detect_page_type
from indu_doc.table_extractor import extract_tables
from indu_doc.page_settings import rect, PageSetup, TableSetup, PageSettings

from typing import Any
from pathlib import Path
import pandas as pd
import pymupdf  # type: ignore
import copy
import traceback

from table_setup.interactive_roi_setup import InteractiveROISetup

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
                "src_cable_tag": "cable tag"
            }
        ),
        "l_conn": TableSetup(
            description="left side cable assignment",
            key_columns={}
        ),
        "r_cables": TableSetup(
            description="right side cable list",
            key_columns={
                "dst_cable_tag": "cable tag"
            }
        ),
        "r_conn": TableSetup(
            description="right side cable assignment",
            key_columns={}
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
        ),
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

import matplotlib.pyplot as plt
from matplotlib.widgets import RectangleSelector
import numpy as np

def render_page_preview(page, roi=None, DPI=300):
    pix = page.get_pixmap(dpi=DPI)
    img = np.ndarray([pix.h, pix.w, 3], dtype=np.uint8, buffer=pix.samples_mv)
    lines = []
    drawn_lines = []

    def bbox_to_plt_rect(bbox):
        tx0, ty0, tx1, ty1 = bbox
        return (tx0, ty0), tx1-tx0, ty1-ty0

    def onselect(eclick, erelease):
        x0, y0 = eclick.xdata, eclick.ydata
        x1, y1 = erelease.xdata, erelease.ydata
        nonlocal roi 
        roi = (x0, y0, x1, y1)
        
        # Clear previous rectangles
        ax.images[0].axes.patches.clear()
        
        # Draw selected region
        rect = plt.Rectangle((x0, y0), x1-x0, y1-y0, edgecolor='red', facecolor='none', linewidth=2)
        ax.add_patch(rect)
        
        fig.canvas.draw_idle()

    def toggle_selector(event):
        nonlocal selector
        nonlocal roi 
        if event.key == 't':
            print("test pressed")
            tables = list(page.find_tables(clip=roi, add_lines=lines))
            # draw
            for i, tbl in enumerate(tables):  # iterate over all tables
                for cell in tbl.header.cells:
                    if cell is not None:
                        ax.add_patch(
                            plt.Rectangle(*bbox_to_plt_rect(cell), edgecolor='green', facecolor='none', linewidth=2)
                        )
                for r, row in enumerate(tbl.rows):
                    for c, cell in enumerate(row.cells):
                        if cell is not None:
                            ax.add_patch(
                                plt.Rectangle(*bbox_to_plt_rect(cell), edgecolor='blue', facecolor='none', linewidth=1)
                            )
                ax.add_patch(
                    plt.Rectangle(*bbox_to_plt_rect(tbl.bbox), edgecolor='purple', facecolor='none', linewidth=2)
                )
            fig.canvas.draw_idle()
        elif event.key == 'r':
            # restart
            for patch in ax.patches:
                patch.remove()
            for line in drawn_lines:
                line.remove()
            drawn_lines.clear()
            
            # roi = None
            lines.clear()
            fig.canvas.draw_idle()
        elif event.key == 'c' and roi:
            # Add vertical line at current mouse x
            x = event.xdata
            if x is not None:
                print(f"Added vertical line at x = {x} y0 {roi[1]} y1 {roi[3]}")
                lines.append([(x, roi[1]), (x, roi[3])])
                drawn_lines.append(ax.vlines(x, roi[1], roi[3], color='blue', linestyle='--'))
            fig.canvas.draw_idle()
        elif event.key == 'enter' and roi:
            print("submit")
            plt.close(fig)


    # --- Plot image with RectangleSelector ---
    fig, ax = plt.subplots()
    ax.imshow(img, extent=(0, pix.w * 72 / DPI, pix.h * 72 / DPI, 0))
    ax.set_axis_off()
    ax.set_title("Editing")

    selector  = RectangleSelector(
        ax, onselect, useblit=True,
        button=[1], minspanx=5, minspany=5, spancoords='pixels',
        interactive=True)
    fig.canvas.mpl_connect('key_press_event', toggle_selector)

    plt.show()

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
    #
    dfs, errors = extract_tables(page, page_setup) # can throw
    click.echo(f"Test success - no fatal errors")
    for e in errors:
        click.echo(f"{e.error_type}: {e.message}")
    for name, df in dfs.items():
        click.echo(f"Table {name} extraction result: ")
        print(df)


def do_page_setup(page: pymupdf.Page, type: PageType, page_setup: PageSetup) -> PageSetup:
    # For each table:
    click.echo("\n=== Page Setup Wizard ===")
    click.echo(f"Hint: {page_setup.description}\n")
    # prompt page name
    search_name = click.prompt("Insert page name (hint: you can find it in bold at the top of the page)", type=str)
    if not search_name:
        raise ValueError("Selected empty search name")
    
    # Validate search_name
    page_setup.search_name = search_name
    detected_type = detect_page_type(page, {type: search_name}) # TODO
    if detected_type != type:
        raise ValueError(f"Detected page type does not match required: expected {type}, got {detected_type}")

    click.echo(f"You must locate {len(page_setup.tables)} table(s) on this page")
    for key, table_setup in page_setup.tables.items():
        # ask for roi
        click.echo(
            f"Working with table '{key}' containing '{table_setup.description}'. \n"
            "Controls INSIDE ROI editor: \n"
            "\tPress 't' to test ROI.\n"
            "\tPress 'c' to add column divider at mouse pos.\n"
            "\tPress 'r' to reset selection.\n"
            "\tPress 'Enter' to finalize selection.")
        input(f"Press any key to open ROI editor")
        #
        tool = InteractiveROISetup(page, f"Select area where {page_setup.description}. Select a bit bigger than the table itself", dpi=150)
        roi, lines, tables = tool.run()
        # if = 0 tables, exit with error
        if len(tables) == 0:
            raise ValueError("Selected ROI has no tables inside")
        #
        table_setup.lines = lines
        table_setup.roi = roi
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
            roi, _, _ = tool.run()
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
        click.echo("\tempty to keep attribute name")
        click.echo("\t/i to ignore attribute")
        attr_map = {k: v for k, v in header_map.items() if k not in new_map}
        for i, title in attr_map.items():
            click.echo(f"Edit attribute (column #{i}) '{title}':")
            name = click.prompt(f"Enter new attribute name", type=str, default="", show_default=False)
            ignore = False
            if not name:
                name = title
            elif name.lower() == "/i":
                name = f"Ignored{i}"
                ignore = True
            new_map[i] = {
                "name": name,
                "ignore": ignore
            }
        
        # print new header map
        new_map = dict(sorted(new_map.items()))
        click.echo(f"New column names: {[v["name"] for v in new_map.values()]}")

        # save
        for v in new_map.values():
            table_setup.columns[v["name"]] = not v.get("ignore", False) 
        print(table_setup.columns)
   
    click.echo("Finished setup")
    return page_setup