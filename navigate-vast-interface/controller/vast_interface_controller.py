# Standard library imports
import os
import numpy as np
import tkinter as tk
from tkinter import filedialog
from copy import deepcopy

# Third party imports
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from tifffile import tifffile
from skimage.exposure import adjust_gamma

# Local application imports
from navigate.controller.sub_controllers.gui import GUIController

# print(os.path.split(__file__)[-1].split('.')[0])

class VastInterfaceController(GUIController):

    def __init__(self, view, parent_controller=None):
        super().__init__(view, parent_controller)

        self.initialize()

    def initialize(self):
        self.variables = self.view.get_variables()
        self.widgets = self.view.get_widgets()
        self.buttons = self.view.buttons

        self.fish_widget = self.widgets['fish_widget']

        # variables
        self.perspective = 0
        self.coord = [0, 0, 0, 0, 0] # (x,y,z,theta,f)
        self.coords_list = []
        self.x_pos = 0
        self.y_pos = 0
        self.background = None

        # load fish images
        self.images = [
            self.load_image(view=2),
            self.load_image(view=1)
        ]
        self.l, self.w = self.images[0].shape

        # draw the fish widget
        self.draw_fish()

        # widget events
        self.fish_widget.fig.canvas.mpl_connect(
            'motion_notify_event',
            self.move_crosshair
        )

        self.fish_widget.fig.canvas.mpl_connect(
            'button_press_event',
            self.on_click
        )

    def load_image(self, dir="C:/Users/vastopmv3/Documents/Python/Fish/Well_A04/", chan="Yl-led615", view=1, slice=5):
        im_path = os.path.join(
            dir,
            f"test001_W_A04_0{view}_YStack",
            f"{chan}_{slice}.tiff"
        )

        return tifffile.imread(im_path)

    def draw_fish(self):
        # clear axes
        self.fish_widget.ax.clear()

        # initialize plot
        self.fish_widget.ax.imshow(
            adjust_gamma(self.images[self.perspective], 0.5),
            cmap='gray'
        )

        # fix xy limits
        self.fish_widget.ax.set_xlim(0, self.w)
        self.fish_widget.ax.set_ylim(0, self.l)

        # display selected points
        if len(self.coords_list) > 0:
            c = np.array(self.coords_list)
            self.fish_widget.ax.scatter(c[:,0], c[:,self.perspective+1], marker='+', color=[0,1,0])

        # set up canvas
        self.fish_widget.canvas.draw()
        self.background = self.fish_widget.canvas.copy_from_bbox(
            self.fish_widget.ax.bbox
        )

    def move_crosshair(self, event):
        # create the new data    
        if self.perspective == 0:
            self.x_pos = event.xdata
        self.y_pos = event.ydata
        self.fish_widget.lines[0].set_data([self.x_pos]*2, [0, self.l])
        self.fish_widget.lines[1].set_data([0, self.w], [self.y_pos]*2)

        # blit new data into old frame
        self.fish_widget.canvas.restore_region(self.background)
        for l in self.fish_widget.lines:
            self.fish_widget.ax.draw_artist(l)
        self.fish_widget.canvas.blit(self.fish_widget.ax.bbox)
        self.fish_widget.canvas.flush_events()

    def on_click(self, event):
        if event.button == 1:          
            if self.perspective == 0:
                self.coord[0] = self.x_pos
                self.coord[1] = self.y_pos
                self.perspective = 1
            elif self.perspective == 1:
                self.coord[2] = self.y_pos
                self.coords_list += [deepcopy(self.coord)]
                self.perspective = 0
                self.update_multiposition_controller(self.coords_list)

            self.draw_fish()

    def update_multiposition_controller(self, positions=[[]]):
        self.parent_controller.multiposition_tab_controller.set_positions(positions)

    @property
    def custom_events(self):
        """Custom events for the controller"""
        return {}