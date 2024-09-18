# Standard library imports
import os
import tkinter as tk
from tkinter import filedialog

# Third party imports
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from tifffile import tifffile

# Local application imports
from navigate.controller.sub_controllers.gui import GUIController

class VastInterfaceController:
    def __init__(self, view, parent_controller=None):
        self.view = view
        self.parent_controller = parent_controller
        
        self.variables = self.view.get_variables()
        self.widgets = self.view.get_widgets()
        self.buttons = self.view.buttons

        self.fish_widget = self.widgets['fish_widget']

        # variables
        self.perspective = 0
        self.coord = [0, 0, 0]
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

        # #################################
        # ##### Example Widget Events #####
        # #################################
        # self.buttons["vast_storage_dir"].configure(command=self.update_vast_imagefolder)

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
            self.images[self.perspective],
            cmap='gray'
        )

        # fix xy limits
        self.fish_widget.ax.set_xlim(0, self.w)
        self.fish_widget.ax.set_ylim(0, self.l)

        # display selected points

        # set up canvas
        self.fish_widget.canvas.draw()
        self.background = self.fish_widget.canvas.copy_from_bbox(
            self.fish_widget.ax.bbox
        )

    def move_crosshair(self, event):
        pass

    def on_click(self, event):
        pass

    def update_vast_imagefolder(self, *args):
        """Update autostore path for the VAST


        Parameters
        ----------
        *args
            Not used


        Examples
        --------
        self.update_vast_imagefolder()
        """
        print(self.widgets["VASTsavedir"].get())
        vast_storage_dir = tk.StringVar()
        vast_storage_dir = filedialog.askdirectory(initialdir=self.widgets["VASTsavedir"].get())
        #self.vast_operator_vals["vast_image_folder"].set(vast_storage_dir)
        self.widgets["VASTsavedir"].set(vast_storage_dir)
        print(self.widgets["VASTsavedir"].get())
    
    def move(self, *args):
        """Example function to move the plugin device
        """

        print("*** Move button is clicked!")
        self.parent_controller.execute("move_plugin_device", self.variables["plugin_name"].get())

