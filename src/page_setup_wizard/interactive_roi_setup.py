import matplotlib.pyplot as plt
from matplotlib.widgets import RectangleSelector
import numpy as np

import click

def bbox_to_plt_rect(bbox):
    tx0, ty0, tx1, ty1 = bbox
    return (tx0, ty0), tx1-tx0, ty1-ty0

class InteractiveROISetup:
    """
    Interactive table setup tool for a single PDF page.
    - Draw table ROI
    - Add vertical column separators
    - Restart selection
    - Finalize selection
    """

    def __init__(self, page, hint: str, roi=None, dpi=150, text_mode: bool = False):
        self.text_mode = text_mode
        self.page = page
        self.dpi = dpi
        self.roi = roi       # Bounding box of table (x0, y0, x1, y1)
        self.vlines: list[tuple[tuple[float, float], tuple[float, float]]] = []      # Vertical lines (for add_lines)
        self.drawn_lines = []   # type: ignore
        self.tables = []        # type: ignore
        self.texts = []         # type: ignore

        # Render page as image
        pix = self.page.get_pixmap(dpi=dpi)
        self.img = np.ndarray([pix.h, pix.w, 3], dtype=np.uint8, buffer=pix.samples_mv)

        # Create figure
        self.fig, self.ax = plt.subplots(dpi=dpi)
        self.ax.imshow(self.img, extent=(0, pix.w * 72 / self.dpi, pix.h * 72 / self.dpi, 0))
        self.ax.set_axis_off()
        self.ax.set_title(
            "Interactive ROI editor\n"
            f"{hint}"
        )

        # Rectangle selector for ROI
        self.selector = RectangleSelector(
            self.ax, self.onselect, useblit=True,
            button=[1], minspanx=5, minspany=5, spancoords='pixels',
            interactive=True
        )

        # Connect key press events
        self.fig.canvas.mpl_connect('key_press_event', self.on_key)

    def onselect(self, eclick, erelease):
        """Callback when ROI rectangle is drawn."""
        x0, y0 = eclick.xdata, eclick.ydata
        x1, y1 = erelease.xdata, erelease.ydata
        self.roi = (x0, y0, x1, y1)

    def on_key(self, event):
        """Keyboard controls for column lines, reset, finalize."""
        if event.key == 't' and self.roi:
            # clear prev selection
            self._clear_canvas()
            #
            if self.text_mode:
                texts = list(self.page.get_text("blocks", clip=self.roi))
                self.texts = texts
                # draw
                for x0, y0, x1, y1, *_ in texts:  # iterate over all tables
                    self.ax.add_patch(
                        plt.Rectangle(*bbox_to_plt_rect((x0, y0, x1, y1)), edgecolor='purple', facecolor='none', linewidth=2)
                    )
            else:
                tables = list(self.page.find_tables(clip=self.roi, add_lines=self.vlines))
                self.tables = tables
                # draw
                for i, tbl in enumerate(tables):  # iterate over all tables
                    for cell in tbl.header.cells:
                        if cell is not None:
                            self.ax.add_patch(
                                plt.Rectangle(*bbox_to_plt_rect(cell), edgecolor='green', facecolor='none', linewidth=2)
                            )
                    for r, row in enumerate(tbl.rows):
                        for c, cell in enumerate(row.cells):
                            if cell is not None:
                                self.ax.add_patch(
                                    plt.Rectangle(*bbox_to_plt_rect(cell), edgecolor='blue', facecolor='none', linewidth=1)
                                )
                    self.ax.add_patch(
                        plt.Rectangle(*bbox_to_plt_rect(tbl.bbox), edgecolor='purple', facecolor='none', linewidth=2)
                    )
            self.fig.canvas.draw_idle()
            
        elif event.key == 'enter' and self.roi:
            # Finalize selection
            click.echo("Selection finalized:")
            click.echo(f"\tROI:\t\t{self.roi}")
            click.echo(f"\tColumn separators:\t{self.vlines}")
            click.echo(f"\tTables #:\t{len(self.tables)}")
            click.echo(f"\tTexts #:\t{len(self.texts)}")
            plt.close(self.fig)

        elif event.key == 'c' and self.roi:
            # Add vertical line at current mouse x
            x = event.xdata
            if x is not None:
                # print(f"Added vertical line at x = {x} y0 {self.roi[1]} y1 {self.roi[3]}")
                self.vlines.append([(x, self.roi[1]), (x, self.roi[3])])
                self.drawn_lines.append(self.ax.vlines(x, self.roi[1], self.roi[3], color='blue', linestyle='--'))
            self.fig.canvas.draw_idle()

        elif event.key == 'r':
            # Reset ROI and lines
            # self.roi = None
            self.vlines.clear()
            self._clear_canvas()
            self.fig.canvas.draw_idle()

    def _clear_canvas(self):
        # Remove previous graphics
        for patch in self.ax.patches:
            patch.remove()
        for line in self.drawn_lines:
            line.remove()
        self.drawn_lines.clear()

    def run(self):
        """Run interactive tool and return ROI and vertical lines."""
        plt.show()
        return self.roi, self.vlines, self.tables, self.texts