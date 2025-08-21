
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

        self.fig = Figure(figsize=(12,4))
        self.ax = self.fig.add_subplot()
        self.lines = self.ax.plot([], [], 'r', [], [], 'r', linewidth=1.0)
        self.fig.tight_layout()
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

        # Text box
        self.variables['text'] = tk.StringVar()
        self.text_label = ttk.Label(self, textvariable=self.variables['text'])
        self.text_label.pack()

        self.fish_frame = ttk.Frame(self)
        self.fish_frame.pack()

        self.fish_widget = FishWidget(self.fish_frame)
        self.fish_widget.canvas.get_tk_widget().pack(side=tk.LEFT)

        # Scrollbars
        for scrollable in ["Y", "Theta", "Chan"]:
            scrollbar = tk.Scale(
                self.fish_frame, 
                orient=tk.VERTICAL,
                tickinterval=1,
                label=scrollable
                )
            scrollbar.pack(
                fill=tk.Y, 
                side=tk.RIGHT, 
                expand=tk.TRUE
                )
            self.inputs[f'{scrollable.lower()}_scrollbar'] = scrollbar

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

        # append nose
        append_nose_var = tk.BooleanVar()
        append_nose_check = ttk.Checkbutton(axis_tools_frame, variable=append_nose_var)
        append_nose_check.grid(row=0, column=6, sticky=tk.NW)
        ttk.Label(axis_tools_frame, text="Append Nose Pos").grid(row=0, column=7)
        self.inputs["append_nose"] = {
            "button": append_nose_check,
            "variable": append_nose_var
        }
        
        # set z-focus origin button
        set_focus_button = ttk.Button(axis_tools_frame, text="Set Z-Stage Origin")
        set_focus_button.grid(row=0, column=8, sticky=tk.NW)
        self.buttons["set_focus"] = set_focus_button

        # set z-focus origin button
        done_button = ttk.Button(axis_tools_frame, text="DONE")
        done_button.grid(row=0, column=9, sticky=tk.NW)
        self.buttons["done"] = done_button

        # set z-focus origin button
        clear_button = ttk.Button(axis_tools_frame, text="Clear All")
        clear_button.grid(row=0, column=10, sticky=tk.NW)
        self.buttons["clear"] = clear_button

        # set z-focus origin button
        save_pos_button = ttk.Button(axis_tools_frame, text="Save Positions")
        save_pos_button.grid(row=0, column=11, sticky=tk.NW)
        self.buttons["save_pos"] = save_pos_button

        # set z-focus origin button
        flip_yz_button = ttk.Button(axis_tools_frame, text="Flip YZ")
        flip_yz_button.grid(row=0, column=12, sticky=tk.NW)
        self.buttons["flip_yz"] = flip_yz_button

        # do projection
        project_var = tk.BooleanVar(value=False)
        project_check = ttk.Checkbutton(axis_tools_frame, variable=project_var)
        self.inputs["project"] = {
            'button': project_check,
            'variable': project_var
        }
        project_check.grid(row=0, column=13, sticky=tk.NW)
        ttk.Label(axis_tools_frame, text="Projection").grid(
            row=0, column=14, sticky=tk.NW
        )

        axis_tools_frame.pack()

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