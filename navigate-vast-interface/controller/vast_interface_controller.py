# Standard library imports
import tkinter as tk
from tkinter import filedialog

# Third party imports
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

# Local application imports
from navigate.controller.sub_controllers.gui import GUIController

class VastInterfaceController:
    def __init__(self, view, parent_controller=None):
        self.view = view
        self.parent_controller = parent_controller
        
        self.variables = self.view.get_variables()
        self.widgets = self.view.get_widgets()
        self.buttons = self.view.buttons

        # #################################
        # ##### Example Widget Events #####
        # #################################
        self.buttons["vast_storage_dir"].configure(command=self.update_vast_imagefolder)

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

