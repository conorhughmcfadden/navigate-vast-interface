
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
        self.inputs['fish_widget'] = self.fish_widget
        
        self.control_notebook = ttk.Notebook(self.fish_frame)
        self.control_notebook.pack(side=tk.RIGHT, fill=tk.Y, expand=True)

        # | ----------- AXES TAB ----------- |

        axes_tab = ttk.Frame(self.control_notebook)
        self.control_notebook.add(axes_tab, text="AXES")

        scroll_frame = ttk.Frame(axes_tab)
        scroll_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Scrollbars
        for scrollable in ["Y", "Theta", "Chan"]:
            scrollbar = tk.Scale(
                scroll_frame, 
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

        flip_frame = ttk.Frame(axes_tab)
        flip_frame.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=False)

        # flip checks
        flip_var = {
            "x": tk.BooleanVar(),
            "y": tk.BooleanVar(),
            "z": tk.BooleanVar()
        }
        flip_check = {
            "x": ttk.Checkbutton(flip_frame, variable=flip_var["x"]),
            "y": ttk.Checkbutton(flip_frame, variable=flip_var["y"]),
            "z": ttk.Checkbutton(flip_frame, variable=flip_var["z"]),
        }
        self.inputs["flip"] = {
            "button": flip_check,
            "variable": flip_var
        }
        for axis in flip_check:
            flip_check[axis].pack(side=tk.LEFT)
            ttk.Label(flip_frame, text=f"Flip {axis.upper()}").pack(side=tk.LEFT)

        # | ----------- CALIBRATION TAB ----------- |

        calib_tab = ttk.Frame(self.control_notebook)
        self.control_notebook.add(calib_tab, text="CALIBRATION")

        pixel_size_frame = ttk.Frame(calib_tab, borderwidth=2, relief='ridge')
        pixel_size_frame.pack(side=tk.TOP, fill=tk.X, expand=False)

        loc_frames = {}

        loc_outer_frame = ttk.Frame(pixel_size_frame, border=2)
        loc_outer_frame.pack(side=tk.TOP)

        for i in range(2):        
            loc_frames[i] = ttk.Frame(loc_outer_frame, borderwidth=2, relief='sunken')
            loc_frames[i].pack(side=tk.LEFT)

            for ax in ['x', 'm']:
                for u in ['um', 'pix']:
                    self.variables[f"{ax}{i}_{u}"] = tk.DoubleVar(value=0.0)
                    self.inputs[f"{ax}{i}_{u}"] = LabelInput(
                        loc_frames[i],
                        label=f"{ax}{i} [{u}]:\t",
                        label_pos="left",
                        input_args={"width": 8},
                        input_var=self.variables[f"{ax}{i}_{u}"]
                    )
                    self.inputs[f"{ax}{i}_{u}"].pack(side=tk.TOP)

                self.buttons[f"set_{ax}{i}"] = ttk.Button(loc_frames[i], text="SET")
                self.buttons[f"set_{ax}{i}"].pack(side=tk.TOP, fill=tk.X, expand=True)

        # pixel size
        self.variables["dx_um_pix"] = tk.StringVar(value="1.000")
        self.variables["dm_um_pix"] = tk.StringVar(value="1.000")

        dx_dm_frame = tk.Frame(pixel_size_frame)
        dx_dm_frame.pack(side=tk.BOTTOM)
        ttk.Label(dx_dm_frame, text="dx [um/pix]:\t").pack(side=tk.LEFT)
        ttk.Label(dx_dm_frame, textvariable=self.variables["dx_um_pix"]).pack(side=tk.LEFT)
        ttk.Label(dx_dm_frame, text="dm [um/pix]:\t").pack(side=tk.LEFT)
        ttk.Label(dx_dm_frame, textvariable=self.variables["dm_um_pix"]).pack(side=tk.LEFT)

        # y-step calibration            
        y_step_frame = ttk.Frame(calib_tab, borderwidth=2, relief='ridge')
        y_step_frame.pack(side=tk.TOP, fill=tk.X, expand=False)

        self.variables["dy_um_step"] = tk.DoubleVar(value=1.0)
        self.inputs["dy_um_step"] = LabelInput(
            y_step_frame,
            label=f"dy [um/step]:\t",
            label_pos="left",
            input_args={"width": 8},
            input_var=self.variables["dy_um_step"]
        )
        self.inputs["dy_um_step"].pack(side=tk.LEFT)  

        self.variables["y0_step"] = tk.IntVar(value=0)
        self.inputs["y0_step"] = LabelInput(
            y_step_frame,
            label=f"y0 [step]:\t",
            label_pos="left",
            input_args={"width": 8},
            input_var=self.variables["y0_step"]
        )
        self.inputs["y0_step"].pack(side=tk.LEFT)           

        self.buttons["set_y0"] = tk.Button(y_step_frame, text="SET")
        self.buttons["set_y0"].pack(side=tk.LEFT, expand=True)

        # theta-rotation calibration            
        theta_step_frame = ttk.Frame(calib_tab, borderwidth=2, relief='ridge')
        theta_step_frame.pack(side=tk.TOP, fill=tk.X, expand=False)

        self.variables["dtheta_deg_step"] = tk.DoubleVar(value=1.0)
        self.inputs["dtheta_deg_step"] = LabelInput(
            theta_step_frame,
            label=f"d\u03B8 [deg/step]:\t",
            label_pos="left",
            input_args={"width": 8},
            input_var=self.variables["dtheta_deg_step"]
        )
        self.inputs["dtheta_deg_step"].pack(side=tk.LEFT)  

        self.variables["theta0_step"] = tk.IntVar(value=0)
        self.inputs["theta0_step"] = LabelInput(
            theta_step_frame,
            label=f"\u03B80 [step]:\t",
            label_pos="left",
            input_args={"width": 8},
            input_var=self.variables["theta0_step"]
        )
        self.inputs["theta0_step"].pack(side=tk.LEFT)           

        self.buttons["set_theta0"] = tk.Button(theta_step_frame, text="SET")
        self.buttons["set_theta0"].pack(side=tk.LEFT, expand=True)

        # self.inputs["x0_pix"] = LabelInput(
        #     head_loc_frame,
        #     label="x0 [pix]:",
        #     label_pos="left",
        #     input_args={"width": 10}
        # )
        # self.inputs["x0_pix"].pack(side=tk.TOP)

        # ttk.Label(pixel_size_frame, text="x0 [um]: ").pack(side=tk.LEFT)
        # self.variables["x_um"] = tk.StringVar(value="0.0")
        # ttk.Label(pixel_size_frame, textvariable=self.variables["x_um"]).pack(side=tk.LEFT)


        axis_tools_frame = ttk.Frame(self)

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

        # manually find nose button
        find_focus_button = ttk.Button(axis_tools_frame, text="FIND FOCUS")
        find_focus_button.grid(row=0, column=9, sticky=tk.NW)
        self.buttons["find_focus"] = find_focus_button

        # set global origin button
        set_origin_button = ttk.Button(axis_tools_frame, text="SET ORIGIN")
        set_origin_button.grid(row=0, column=10, sticky=tk.NW)
        self.buttons["set_origin"] = set_origin_button

        # # set z-focus origin button
        # done_button = ttk.Button(axis_tools_frame, text="DONE")
        # done_button.grid(row=0, column=9, sticky=tk.NW)
        # self.buttons["done"] = done_button

        # reload next fish
        reload_button = ttk.Button(axis_tools_frame, text="LOAD RECENT")
        reload_button.grid(row=0, column=11, sticky=tk.NW)
        self.buttons["reload"] = reload_button

        # load specific well
        load_well_button = ttk.Button(axis_tools_frame, text="LOAD WELL")
        load_well_button.grid(row=0, column=12, sticky=tk.NW)
        self.buttons["load_well"] = load_well_button

        # set z-focus origin button
        pull_from_mp_button = ttk.Button(axis_tools_frame, text="Pull From MP Table")
        pull_from_mp_button.grid(row=0, column=13, sticky=tk.NW)
        self.buttons["pull_from_mp"] = pull_from_mp_button

        # set z-focus origin button
        flip_yz_button = ttk.Button(axis_tools_frame, text="Flip YZ")
        flip_yz_button.grid(row=0, column=14, sticky=tk.NW)
        self.buttons["flip_yz"] = flip_yz_button

        # do projection
        project_var = tk.BooleanVar(value=False)
        project_check = ttk.Checkbutton(axis_tools_frame, variable=project_var)
        self.inputs["project"] = {
            'button': project_check,
            'variable': project_var
        }
        project_check.grid(row=0, column=15, sticky=tk.NW)
        ttk.Label(axis_tools_frame, text="Projection").grid(
            row=0, column=16, sticky=tk.NW
        )

        # do color
        color_var = tk.BooleanVar(value=False)
        color_check = ttk.Checkbutton(axis_tools_frame, variable=color_var)
        self.inputs["color"] = {
            'button': color_check,
            'variable': color_var
        }
        color_check.grid(row=0, column=17, sticky=tk.NW)
        ttk.Label(axis_tools_frame, text="Color").grid(
            row=0, column=18, sticky=tk.NW
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