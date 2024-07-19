# Standard Imports
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog

#Third-party Imports
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

#Local Imports
from navigate.view.custom_widgets.hover import Hover, HoverButton
from navigate.view.custom_widgets.validation import ValidatedSpinbox, ValidatedCombobox
from navigate.view.custom_widgets.LabelInputWidgetFactory import LabelInput


class VastInterfaceFrame(ttk.Frame):
    """VAST Operator Frame

    This frame contains the widgets for operating the VAST Fluoroimager and LP Sampler.
    """

    def __init__(self, root, *args, **kwargs):
        """Initilization of the Confocal Projection Frame

        Parameters
        ----------
        root : tkinter.ttk.Frame
            The frame that this frame will be placed in.
        *args
            Variable length argument list.
        **kwargs
            Arbitrary keyword arguments.
        """
        # Init Frame
        ttk.Frame.__init__(self, root, *args, **kwargs)

        # Formatting
        tk.Grid.columnconfigure(self, "all", weight=1)
        tk.Grid.rowconfigure(self, "all", weight=1)

        # Dictionary for widgets and buttons
        #: dict: Dictionary of the widgets in the frame
        self.inputs = {}
        self.buttons = {}
        self.variables = []

        # Frames for widgets
        #: tkinter.Frame: The frame that holds the position settings
        self.interop_frame = ttk.LabelFrame(self, text="Interop Frame")
        #: tkinter.Frame: holds pre- and post-analysis images
        self.image_frame = ttk.LabelFrame(self, text = "Image Frame")
        #: frame that displays extraneous information
        self.data_frame = ttk.LabelFrame(self, text = "Data Frame")
        self.canvas_frame = tk.Frame(self, height=256, width=512)
        self.DorsalImage = tk.Canvas(self.canvas_frame,
        height = 200,
        width = 2048,
        bd = 10,
        highlightthickness = 10,
        relief = "ridge")
        self.DorsalImage.create_oval(-50,50,-50,50)
        self.DorsalImage.place(x = 0, y = 0)
        # self.LateralImage = tk.Canvas(self.canvas_frame,
        # height = 1100,
        # width = 2200,
        # bd = 10,
        # highlightthickness = 0,
        # relief = "ridge")
        # self.LateralImage.place(x = 0, y = 0)

        #  #: int: The width of the canvas.
        # #: int: The height of the canvas.
        # self.canvas_width, self.canvas_height = 512, 512

        # #: tk.Canvas: The canvas that will hold the camera image.
        # self.canvas = tk.Canvas(
        #     width=self.canvas_width, height=self.canvas_height
        # )
        # self.canvas.grid(row=0, column=0, sticky=tk.NSEW, padx=5, pady=5)

        # #: matplotlib.figure.Figure: The figure that will hold the camera image.
        # self.matplotlib_figure = Figure(figsize=[6, 6], tight_layout=True)

        # #: matplotlib.backends.backend_tkagg.FigureCanvasTkAgg: The canvas that will
        # # hold the camera image.
        # self.matplotlib_canvas = FigureCanvasTkAgg(self.matplotlib_figure, self.canvas)




        # Grid Each Holder Frame
        self.interop_frame.grid(row=0, column=0, sticky=tk.NSEW)
        self.image_frame.grid(row=1, column=0, sticky=tk.NSEW)
        self.data_frame.grid(row=0, column=1, sticky=tk.NSEW)
        self.canvas_frame.grid(row=1,column=1,sticky=tk.NSEW)
        
        #Image path selection
        # self.variables["storage_dir"] = ""
        self.buttons["vast_storage_dir"] = HoverButton(
            self.interop_frame, text="Select Image Save Folder "
        )
        self.buttons["vast_storage_dir"].grid(row=3, column=1, sticky="N", pady=2, padx=(6, 0))
        #Button for Initialization   
        self.buttons["move_VAST"] = HoverButton(
            self.interop_frame, text="Initialize LPS+VAST"
        )
        self.buttons["move_VAST"].grid(row=4, column=1, sticky="N", pady=2, padx=(6, 0))
        
        self.VASTsavedir_label = ttk.Label(self.data_frame, text="VAST Imaging Directory")
        self.VASTsavedir_label.grid(row=0, column=0, sticky="S")
        self.inputs["VASTsavedir"] = LabelInput(
            parent=self.data_frame,
            input_class=ttk.Entry,
            input_var=tk.StringVar()
        )
        self.inputs["VASTsavedir"].grid(row=0, column=1, sticky="N", padx=6)
        self.inputs["VASTsavedir"].label.grid(sticky="N")


        self.buttons["DsplayFluorChannel"] = tk.Radiobutton(self.image_frame)

        

    # Getters
    def get_variables(self):
        """Returns a dictionary of the variables for the widgets in this frame.

        The key is the widget name, value is the variable associated.

        Returns
        -------
        variables : dict
            Dictionary of the variables for the widgets in this frame.
        """
        variables = {}
        for key, widget in self.inputs.items():
            variables[key] = widget.get_variable()
        return variables

    def get_widgets(self):
        """Returns a dictionary of the widgets in this frame.

        The key is the widget name, value is the LabelInput class that has all the data.

        Returns
        -------
        self.inputs : dict
            Dictionary of the widgets in this frame.
        """
        return self.inputs
