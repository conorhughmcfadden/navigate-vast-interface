
# Standard Imports
import tkinter as tk
from tkinter import ttk

#Third-party Imports
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

#Local Imports
from navigate.view.custom_widgets.hover import Hover, HoverButton
from navigate.view.custom_widgets.validation import ValidatedSpinbox, ValidatedCombobox
from navigate.view.custom_widgets.LabelInputWidgetFactory import LabelInput


class FishWidget:

    def __init__(self, master):

        self.fig = Figure(figsize=(10,4))
        self.ax = self.fig.add_subplot()
        self.lines = self.ax.plot([], [], 'r', [], [], 'r', linewidth=1.0)
        self.canvas = FigureCanvasTkAgg(figure=self.fig, master=master)

class VastInterfaceFrame(ttk.Frame):
    """Plugin Frame: Just an example

    This frame contains the widgets for the plugin.
    """

    def __init__(self, root, *args, **kwargs):
        """Initilization of the  Frame

        Parameters
        ----------
        root : tkinter.ttk.Frame
            The frame that this frame will be placed in.
        *args
            Variable length argument list.
        **kwargs
            Arbitrary keyword arguments.
        """
        ttk.Frame.__init__(self, root, *args, **kwargs)

        # Formatting
        tk.Grid.columnconfigure(self, "all", weight=1)
        tk.Grid.rowconfigure(self, "all", weight=1)

        # Dictionary for widgets and buttons
        #: dict: Dictionary of the widgets in the frame
        self.inputs = {}
        self.buttons = {}
        self.variables = {}

        # #################################
        # ######## Example Widgets ########
        # ##### add your widgets here #####
        # #################################
        self.variables['text'] = tk.StringVar()
        self.text_label = ttk.Label(self, textvariable=self.variables['text'])
        self.text_label.pack()

        self.fish_widget = FishWidget(self)
        self.fish_widget.canvas.get_tk_widget().pack()
        
        self.inputs['fish_widget'] = self.fish_widget

        load_expt_frame = ttk.Frame(self)

        path_button = ttk.Button(load_expt_frame, text="Load Experiment")
        path_button.grid(row=0, column=0, sticky=tk.NW)
        self.buttons['path'] = path_button

        self.variables['path'] = tk.StringVar()
        path_label = ttk.Label(load_expt_frame, textvariable=self.variables['path'])
        path_label.grid(row=0, column=1, sticky=tk.NW)

        load_expt_frame.pack()

        axis_tools_frame = ttk.Frame(self)

        # flip checks
        flip_var = {
            "x": tk.BooleanVar(),
            "y": tk.BooleanVar(),
            "z": tk.BooleanVar()
        }
        flip_check = {
            "x": ttk.Checkbutton(axis_tools_frame, variable=flip_var["x"]),
            "y": ttk.Checkbutton(axis_tools_frame, variable=flip_var["y"]),
            "z": ttk.Checkbutton(axis_tools_frame, variable=flip_var["z"]),
        }
        self.inputs["flip"] = {
            "button": flip_check,
            "variable": flip_var
        }
        for i, axis in enumerate(flip_check):
            flip_check[axis].grid(row=0, column=2*i)
            ttk.Label(axis_tools_frame, text=f"Flip {axis.upper()}").grid(row=0, column=2*i+1)
        
        # set z-focus origin button
        set_focus_button = ttk.Button(axis_tools_frame, text="Set Z-Stage Origin")
        set_focus_button.grid(row=0, column=6, sticky=tk.NW)
        self.buttons['set_focus'] = set_focus_button

        axis_tools_frame.pack()

        # label = ttk.Label(self, text="VAST Interface")
        # label.grid(row=0, column=0, sticky=tk.NW)

        # self.variables["plugin_name"] = tk.StringVar(self)
        # self.inputs["plugin_name"] = ttk.Entry(
        #     self, textvariable=self.variables["plugin_name"]
        # )
        # self.inputs["plugin_name"].grid(
        #     row=0, column=1, sticky="N", padx=5, pady=(0, 5)
        # )

        # self.buttons["move"] = ttk.Button(self, text="MOVE1")
        # self.buttons["move"].grid(row=1, column=1, sticky="N", padx=6)
        
        
        # self.inputs["VASTsavedir"] = LabelInput(
        #     self,
        #     input_class=ttk.Entry,
        #     input_var=tk.StringVar()
        # )


        
        #Image path selection
        # self.buttons["vast_storage_dir"] = HoverButton(
        #     self, text="Select Image Save Folder "
        # )
        # self.buttons["vast_storage_dir"].grid(row=3, column=1, sticky="N", pady=2, padx=(6, 0))
        
    # Getters
    def get_variables(self):
        """Returns a dictionary of the variables for the widgets in this frame.

        The key is the widget name, value is the variable associated.

        Returns
        -------
        variables : dict
            Dictionary of the variables for the widgets in this frame.
        """
        return self.variables

    def get_widgets(self):
        """Returns a dictionary of the widgets in this frame.

        The key is the widget name, value is the LabelInput class that has all the data.

        Returns
        -------
        self.inputs : dict
            Dictionary of the widgets in this frame.
        """
        return self.inputs


# # class VastInterfaceFrame(ttk.Frame):
# #     """VAST Operator Frame

# #     This frame contains the widgets for operating the VAST Fluoroimager and LP Sampler.
# #     """

# #     def __init__(self, root, *args, **kwargs):
# #         """Initilization of the Vast Operator Frame

# #         Parameters
# #         ----------
# #         root : tkinter.ttk.Frame
# #             The frame that this frame will be placed in.
# #         *args
# #             Variable length argument list.
# #         **kwargs
# #             Arbitrary keyword arguments.
# #         """
# #         # Init Frame
# #         ttk.Frame.__init__(self, root, *args, **kwargs)

# #         self.inputs = {}
# #         self.buttons = {}
# #         self.variables = {}

# #         label = ttk.Label(self, text="Plugin Name:")
# #         label.grid(row=0, column=0, sticky=tk.NW)

# #          # #################################
# #         # ######## Example Widgets ########
# #         # ##### add your widgets here #####
# #         # ###############################



# #         # Formatting
# #         # tk.Grid.columnconfigure(self, "all", weight=1)
# #         # tk.Grid.rowconfigure(self, "all", weight=1)

# #         # # Dictionary for widgets and buttons
# #         # #: dict: Dictionary of the widgets in the frame
# #         # # Frames for widgets
# #         # #: tkinter.Frame: The frame that holds the position settings
# #         # self.interop_frame = ttk.LabelFrame(self, text="Interop Frame")
# #         # #: tkinter.Frame: holds pre- and post-analysis images
# #         # self.image_frame = ttk.LabelFrame(self, text = "Image Frame")
# #         # #: frame that displays extraneous information
# #         # self.data_frame = ttk.LabelFrame(self, text = "Data Frame")
# #         # self.canvas_frame = tk.Frame(self, height=256, width=512)
# #         # self.DorsalImage = tk.Canvas(self.canvas_frame,
# #         # height = 200,
# #         # width = 2048,
# #         # bd = 10,
# #         # highlightthickness = 10,
# #         # relief = "ridge")
# #         # self.DorsalImage.create_oval(-50,50,-50,50)
# #         # self.DorsalImage.place(x = 0, y = 0)
# #         # # self.LateralImage = tk.Canvas(self.canvas_frame,
# #         # # height = 1100,
# #         # # width = 2200,
# #         # # bd = 10,
# #         # # highlightthickness = 0,
# #         # # relief = "ridge")
# #         # # self.LateralImage.place(x = 0, y = 0)

# #         # #  #: int: The width of the canvas.
# #         # # #: int: The height of the canvas.
# #         # # self.canvas_width, self.canvas_height = 512, 512

# #         # # #: tk.Canvas: The canvas that will hold the camera image.
# #         # # self.canvas = tk.Canvas(
# #         # #     width=self.canvas_width, height=self.canvas_height
# #         # # )
# #         # # self.canvas.grid(row=0, column=0, sticky=tk.NSEW, padx=5, pady=5)

# #         # # #: matplotlib.figure.Figure: The figure that will hold the camera image.
# #         # # self.matplotlib_figure = Figure(figsize=[6, 6], tight_layout=True)

# #         # # #: matplotlib.backends.backend_tkagg.FigureCanvasTkAgg: The canvas that will
# #         # # # hold the camera image.
# #         # # self.matplotlib_canvas = FigureCanvasTkAgg(self.matplotlib_figure, self.canvas)




# #         # # Grid Each Holder Frame
# #         # self.interop_frame.grid(row=0, column=0, sticky=tk.NSEW)
# #         # self.image_frame.grid(row=1, column=0, sticky=tk.NSEW)
# #         # self.data_frame.grid(row=0, column=1, sticky=tk.NSEW)
# #         # self.canvas_frame.grid(row=1,column=1,sticky=tk.NSEW)
        
# #         # #Image path selection
# #         # # self.variables["storage_dir"] = ""
# #         # self.buttons["vast_storage_dir"] = HoverButton(
# #         #     self.interop_frame, text="Select Image Save Folder "
# #         # )
# #         # self.buttons["vast_storage_dir"].grid(row=3, column=1, sticky="N", pady=2, padx=(6, 0))
# #         # #Button for Initialization   
# #         # self.buttons["move_VAST"] = HoverButton(
# #         #     self.interop_frame, text="Initialize LPS+VAST"
# #         # )
# #         # self.buttons["move_VAST"].grid(row=4, column=1, sticky="N", pady=2, padx=(6, 0))
        
# #         # self.VASTsavedir_label = ttk.Label(self.data_frame, text="VAST Imaging Directory")
# #         # self.VASTsavedir_label.grid(row=0, column=0, sticky="S")
# #         # self.inputs["VASTsavedir"] = LabelInput(
# #         #     parent=self.data_frame,
# #         #     input_class=ttk.Entry,
# #         #     input_var=tk.StringVar()
# #         # )
# #         # self.inputs["VASTsavedir"].grid(row=0, column=1, sticky="N", padx=6)
# #         # self.inputs["VASTsavedir"].label.grid(sticky="N")


# #         # self.buttons["DsplayFluorChannel"] = tk.Radiobutton(self.image_frame)

        

# #     # Getters
# #     def get_variables(self):
# #         """Returns a dictionary of the variables for the widgets in this frame.

# #         The key is the widget name, value is the variable associated.

# #         Returns
# #         -------
# #         variables : dict
# #             Dictionary of the variables for the widgets in this frame.
# #         """
# #         return self.variables

# #     def get_widgets(self):
# #         """Returns a dictionary of the widgets in this frame.

# #         The key is the widget name, value is the LabelInput class that has all the data.

# #         Returns
# #         -------
# #         self.inputs : dict
# #             Dictionary of the widgets in this frame.
# #         """
# #         return self.inputs
