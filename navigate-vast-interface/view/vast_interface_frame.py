
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
        self.text_label = ttk.Label(self, 
                                    textvariable=self.variables['text'], 
                                    font=("Arial", 16, "bold")
                                    )
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

        load_frame = ttk.Frame(self)

        vexp_path_button = ttk.Button(load_frame, text="Load VEXP")
        vexp_path_button.grid(row=0, column=0, sticky=tk.NW)
        self.buttons['vexp_path'] = vexp_path_button

        self.variables['vexp_path'] = tk.StringVar()
        vexp_path_label = ttk.Label(load_frame, textvariable=self.variables['vexp_path'])
        vexp_path_label.grid(row=0, column=1, sticky=tk.NW)

        job_path_button = ttk.Button(load_frame, text="Load JOB")
        job_path_button.grid(row=1, column=0, sticky=tk.NW)
        self.buttons['job_path'] = job_path_button

        self.variables['job_path'] = tk.StringVar()
        job_path_label = ttk.Label(load_frame, textvariable=self.variables['job_path'])
        job_path_label.grid(row=1, column=1, sticky=tk.NW)

        load_frame.pack()

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

        # manually find nose button
        find_nose_button = ttk.Button(axis_tools_frame, text="FIND NOSE")
        find_nose_button.grid(row=0, column=8, sticky=tk.NW)
        self.buttons["find_nose"] = find_nose_button

        # set global origin button
        set_origin_button = ttk.Button(axis_tools_frame, text="SET ORIGIN")
        set_origin_button.grid(row=0, column=9, sticky=tk.NW)
        self.buttons["set_origin"] = set_origin_button

        # # set z-focus origin button
        # done_button = ttk.Button(axis_tools_frame, text="DONE")
        # done_button.grid(row=0, column=9, sticky=tk.NW)
        # self.buttons["done"] = done_button

        # reload next fish
        reload_button = ttk.Button(axis_tools_frame, text="LOAD RECENT")
        reload_button.grid(row=0, column=10, sticky=tk.NW)
        self.buttons["reload"] = reload_button

        # load specific well
        load_well_button = ttk.Button(axis_tools_frame, text="LOAD WELL")
        load_well_button.grid(row=0, column=11, sticky=tk.NW)
        self.buttons["load_well"] = load_well_button

        # set z-focus origin button
        pull_from_mp_button = ttk.Button(axis_tools_frame, text="Pull From MP Table")
        pull_from_mp_button.grid(row=0, column=12, sticky=tk.NW)
        self.buttons["pull_from_mp"] = pull_from_mp_button

        # set z-focus origin button
        flip_yz_button = ttk.Button(axis_tools_frame, text="Flip YZ")
        flip_yz_button.grid(row=0, column=13, sticky=tk.NW)
        self.buttons["flip_yz"] = flip_yz_button

        # do projection
        project_var = tk.BooleanVar(value=False)
        project_check = ttk.Checkbutton(axis_tools_frame, variable=project_var)
        self.inputs["project"] = {
            'button': project_check,
            'variable': project_var
        }
        project_check.grid(row=0, column=14, sticky=tk.NW)
        ttk.Label(axis_tools_frame, text="Projection").grid(
            row=0, column=15, sticky=tk.NW
        )

        # do color
        color_var = tk.BooleanVar(value=False)
        color_check = ttk.Checkbutton(axis_tools_frame, variable=color_var)
        self.inputs["color"] = {
            'button': color_check,
            'variable': color_var
        }
        color_check.grid(row=0, column=16, sticky=tk.NW)
        ttk.Label(axis_tools_frame, text="Color").grid(
            row=0, column=17, sticky=tk.NW
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