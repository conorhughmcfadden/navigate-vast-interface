# Standard library imports
import os
from pathlib import Path
import cv2
from glob import glob
import numpy as np
from scipy import stats, signal
from tkinter import filedialog
from copy import deepcopy
import traceback

# Third party imports
from tifffile import tifffile
from skimage.exposure import adjust_gamma
from matplotlib.patches import Circle

# Local application imports
from navigate.controller.sub_controllers.gui import GUIController
from navigate.controller.controller import Controller
from navigate.tools.file_functions import load_yaml_file

from navigate.tools.xml_tools import parse_xml
import xml.etree.ElementTree as ET

VAST_UM_PIX = 718.5/221 # Measured Cap / expt.CapWd

AXIS_MAPPING = ['x', 'y', 'm']

"""
Extended depth of field...
Maybe make into a feature in /develop/ later on.
"""
def extended_depth_of_field(stack : dict, ksize=5, bsize=11, order=2, ref_chan="", ref_z=-1, dark_ref_bg=True):

    # make sure we're in float64
    stack = {chan: np.float64(stack[chan]) for chan in stack}

    bit_depth_ceil = stack[ref_chan].max()
    # switch to dark bg
    if not dark_ref_bg:
        stack[ref_chan] = bit_depth_ceil - stack[ref_chan]

    # func : tmat from "src" to "trg"
    def _tmat(src, trg):
        
        (dx, dy), _ = cv2.phaseCorrelate(src, trg)

        return np.array(
            [[1, 0, dx],
                [0, 1, dy]],
            dtype=np.float64
        )

    # get tmats for all slices in ref_chan
    ref_slice = stack[ref_chan][ref_z]
    tmats = [_tmat(s, ref_slice) for s in stack[ref_chan]]

    # func : register a full stack
    def _reg_stack(x : np.ndarray):
        _, rows, cols = x.shape
        return np.array([
            cv2.warpAffine(x[i], tmats[i], (cols, rows))
            for i in range(len(x))
        ])

    # register all channels
    registered = {chan: _reg_stack(stack[chan]) for chan in stack}

    # get sharp indices based on ref_chan
    inds = np.array(
        [cv2.Sobel(
            z,
            ddepth=cv2.CV_64F,
            dx=order,
            dy=order,
            ksize=ksize,
            borderType=cv2.BORDER_REFLECT)
            for z in registered[ref_chan]]
    ).argmax(0)

    # optional index blurring
    inds = cv2.blur(inds, ksize=[bsize]*2)

    # func : apply sharpness indices to stack
    def _apply_indices(x : np.ndarray):
        z, h, w = x.shape

        temp = x.reshape((z, -1)).transpose()
        temp = temp[np.arange(len(temp)), inds.ravel()]

        return temp.reshape((h, w))

    # apply indices to each (registered) channel
    output = {chan: _apply_indices(registered[chan]) for chan in registered}

    # switch back to light bg (if needed)
    if not dark_ref_bg:
        output[ref_chan] = bit_depth_ceil - output[ref_chan]

    # convert back to np.uint16
    output = {chan: np.uint16(output[chan]) for chan in output}

    return output, inds

class vector(dict):
    """
        Helper dict-like class to do vector operations with labelled axes.
    """
    def __init__(self, d, val=0.):
        if isinstance(d, list):
            d = {k: val for k in d}
        super().__init__(d)
    
    def __sub__(self, other):
        if isinstance(other, (int, float)):
            return vector({k: self[k] - other for k in self})
        else:
            try:
                return vector({k: self[k] - other[k] for k in self})
            except (TypeError, KeyError):
                print(f"Must '-' with numeric scalar or dict with matching keys. Instead got {self} - {other}.")
    
    def __add__(self, other):
        if isinstance(other, (int, float)):
            return vector({k: self[k] + other for k in self})
        else:
            try:
                return vector({k: self[k] + other[k] for k in self})
            except (TypeError, KeyError):
                print(f"Must '+' with numeric scalar or dict with matching keys. Instead got {self} + {other}.")

    def __mul__(self, other):
        if isinstance(other, (int, float)):
            return vector({k: self[k] * other for k in self})
        else:
            try:
                return vector({k: self[k] * other[k] for k in self})
            except (TypeError, KeyError):
                print(f"Must '*', with numeric scalar or dict with matching keys. Instead got {self} * {other}.")

    def __rmul__(self, other):
        self.__mul__(other)

    def __truediv__(self, other):
        if isinstance(other, (int, float)):
            return self.__mul__(1 / other)
        else:
            print("Division only works with scalars...")    

class VastInterfaceController(GUIController):

    def __init__(self, view, parent_controller : Controller = None):
        super().__init__(view, parent_controller)

        try:
            # get plugin name to call events from parent_controller
            config_path = os.path.join(Path(__file__).parent.parent, 'plugin_config.yml')
            plugin_config = load_yaml_file(config_path)
            self.plugin_name = plugin_config['name']

            self.initialize()

            self.vast_experiment['VASTAnnotatorStatus'] = True
        except Exception as e:
            traceback.print_exc()

    def set_global_origin(self):
        # set x-origin to nose_pos
        self.global_origin[AXIS_MAPPING[0]] = self.nose_pos

        # set z-origin to top of capillary
        cap_peaks = self.find_capillary_boundary(view=self.reference_view)
        self.global_origin[AXIS_MAPPING[2]] = cap_peaks.max() # top side

        # set y-origin to in_focus_slice
        self.global_origin[AXIS_MAPPING[1]] = self.in_focus_slice

        # set the config offset to the global origin
        # stage_config = self.parent_controller.model.configuration['configuration']['microscopes'][
        #     self.parent_controller.model.active_microscope_name
        #     ]['stage']
        
        # for ax in AXIS_MAPPING:
        #     stage_config[f"{ax}_offset"] = self.global_origin[ax]

        print(f"Setting origin to: {self.global_origin}")

        # update experiment values
        self.update_experiment_values()

    def initialize(self):
        # try to get the VAST field in Experiment, else create it
        try:
            self.vast_experiment = self.parent_controller.model.configuration['experiment']['VAST']
        except KeyError:
            self.parent_controller.model.configuration['experiment']['VAST'] = {}
            self.initialize()

        self.variables = self.view.get_variables()
        self.widgets = self.view.get_widgets()
        self.buttons = self.view.buttons

        self.fish_widget = self.widgets['fish_widget']
        self.y_scrollbar = self.widgets['y_scrollbar']
        self.theta_scrollbar = self.widgets['theta_scrollbar']
        self.chan_scrollbar = self.widgets['chan_scrollbar']
        
        self.text_var = self.variables['text']
        self.vexp_path_var = self.variables['path']
        self.path_button = self.buttons['path']
        self.reload_button = self.buttons['reload']
        self.load_well_button = self.buttons['load_well']
        self.pull_from_mp_button = self.buttons['pull_from_mp']
        self.set_origin_button = self.buttons['set_origin']
        self.find_nose_button = self.buttons['find_nose']

        # variables
        self.stage_axes = self.parent_controller.configuration_controller.stage_axes
        self.current_position = vector(self.stage_axes, val=0.)
        self.annotated_positions = []
        self.working_dir = None
        self.well = None
        self.in_focus_slice = 0
        self.reference_view = 0
        self.nose_pos = None
        self.setting_nose_pos = False

        # projection stuff
        self.do_projection = self.widgets['project']['variable']
        self.do_projection_check = self.widgets['project']['button']

        def set_axis_and_draw(val, ax):
            self.set_axis(int(val), ax)
            self.draw_fish()
        
        # configure scrollbar commands
        self.y_scrollbar.configure(command=lambda val: set_axis_and_draw(val, 'y'))
        self.theta_scrollbar.configure(command=lambda val: set_axis_and_draw(val, 'theta'))
        self.chan_scrollbar.configure(command=lambda val: set_axis_and_draw(val, 'chan'))

        # mousewheel events
        self.y_scrollbar.bind("<MouseWheel>", lambda event: self.mousewheel_axis(event.widget, event.delta, 'y'))
        self.theta_scrollbar.bind("<MouseWheel>", lambda event: self.mousewheel_axis(event.widget, event.delta, 'theta'))
        self.chan_scrollbar.bind("<MouseWheel>", lambda event: self.mousewheel_axis(event.widget, event.delta, 'chan'))

        # button click events
        self.reload_button.configure(command=self.load_next_fish)
        self.load_well_button.configure(command=self.load_specific_well)        
        self.do_projection_check.configure(command=self.draw_fish)
        self.path_button.configure(command=self.load_vexp)
        self.set_origin_button.configure(command=self.set_global_origin)
        self.find_nose_button.configure(command=self.manual_find_nose_position)        
        self.pull_from_mp_button.configure(command=self.pull_from_mp_table)

        # widget events
        self.fish_widget.fig.canvas.mpl_connect(
            'motion_notify_event',
            self.move_crosshair
        )

        self.fish_widget.fig.canvas.mpl_connect(
            'button_press_event',
            self.on_click
        )
        
        self.fish_widget.fig.canvas.mpl_connect(
            'scroll_event',
            lambda event: self.mousewheel_axis(self.y_scrollbar, event.step, 'y')
        )

        # go ahead and load the first fish
        self.load_next_fish()

    def load_specific_well(self):
        well = filedialog.askdirectory(title="Choose the Well directory:", initialdir=self.working_dir)
        self.load_next_fish(well)

    def pull_from_mp_table(self):

        multi_positions = self.parent_controller.multiposition_tab_controller.get_positions()

        self.annotated_positions = []

        axes = [ax.lower() for ax in multi_positions.pop(0)]
        units = self.units

        for pos in multi_positions:
            new_vector = {}
            for ax, val in zip(axes, pos):
                new_vector[ax] = val/units[ax] if units[ax] else 0.0

            self.annotated_positions.append(vector(new_vector))

        print(self.annotated_positions)

        self.draw_fish()

    def load_next_fish(self, well=None):

        if well != self.well:
            self.well = well
            self.nose_pos = None

        # try to get global_origin from experiment
        try:
            self.global_origin = vector(self.vast_experiment['GlobalOrigin'])
        except KeyError:
            print("KeyError: Failed to load global_origin from experiment! Setting to zero.")
            self.global_origin = vector(self.stage_axes, val=0.)

        # get the vexp
        try:
            self.vexp_path = self.vast_experiment['ExperimentFile']
        except (KeyError, FileNotFoundError):
            print("Could not load VEXP file from Experiment... Load manually.")
            self.load_vexp()
        
        self.vexp_path_var.set(self.vexp_path)
        self.vexp = self.parse_vexp()    

        # working directory
        self.working_dir = Path(self.vexp['AutoStSetup']['_storeLocation']['text']).parent

        # store step sizes from expt
        self.y_stack_step = float(self.vexp['AutoStSetup']['yStack']['_stepLenUm']['text'])
        self.theta_step = float(self.vexp['AutoStSetup']['_degrees']['text'])

        # build vector to keep track of units
        self.units = vector(self.stage_axes)
        self.units[AXIS_MAPPING[0]] = -VAST_UM_PIX       # x (um) (flip)
        self.units[AXIS_MAPPING[1]] = self.y_stack_step # y (um)
        self.units[AXIS_MAPPING[2]] = VAST_UM_PIX       # m (um)
        self.units['theta'] = self.theta_step           # theta (degrees)

        # get channel names and view folders
        try:
            (self.channel_names, self.view_names) = self.parse_well(well)
        except Exception as e:
            print(e)
            traceback.print_exc()
        self.n_views = len(self.view_names)
        self.n_channels = len(self.channel_names)
        self.curr_channel_idx = 0

        # the working dir will be parent of views
        # self.working_dir = Path(self.view_names[0]).parent.resolve()

        # load images: [chan, view, slice]
        self.images = {}
        for chan in self.channel_names:
            self.images[chan] = []
            for view in self.view_names:
                stack = self.load_stack(view, chan)
                self.images[chan].append(stack)

        # store stack dimensions
        self.n_slices, self.l, self.w = self.images[self.channel_names[0]][0].shape

        # set scrollbar ranges
        self.y_scrollbar.configure(from_=0, to=self.n_slices-1)
        self.theta_scrollbar.configure(from_=0, to=self.n_views-1)
        self.chan_scrollbar.configure(from_=0, to=self.n_channels-1)

        # need to pick a view to calculate nose_pos, in_focus
        self.reference_view = 0

        # compute projections and find in_focus_slice
        self.projections = {chan: [] for chan in self.images}
        self.in_focus_slice = 0
        for v in range(self.n_views):
            new_projection, indices = extended_depth_of_field(
                {chan: self.images[chan][v] for chan in self.images},
                ref_chan="",
                ksize=5,
                bsize=11,
                dark_ref_bg=False
            )
            if v == self.reference_view:
                self.in_focus_slice = stats.mode(indices.flatten()).mode[0]
            for chan in self.images:
                self.projections[chan].append(new_projection[chan])

        # automatically calculate nose position (if needed)
        if self.nose_pos is None:
            self.nose_pos = self.find_nose_position()

        # start with scrollbar set to in-focus slice
        self.y_scrollbar.set(self.in_focus_slice)
        self.set_axis(self.in_focus_slice, axis=AXIS_MAPPING[1])

        # first draw
        self.draw_fish()

    def find_capillary_boundary(self, chan="", view=0):
        im = self.projections[chan][view]

        profile = im.sum(axis=1)

        # normalize and invert
        profile -= profile.min()
        profile = 1 - profile/profile.max()

        # find top two peaks
        peaks = signal.find_peaks(profile)[0]
        inds = np.argsort([profile[p] for p in peaks])[::-1][:2]
        peaks = peaks[inds]

        return peaks

    def move_crosshair(self, event):
        # clear crosshairs
        self.fish_widget.canvas.restore_region(self.background)
        
        # x-axis
        x_ = event.xdata
        self.set_axis(x_, AXIS_MAPPING[0])
        x_line = self.fish_widget.lines[0]
        x_line.set_data([x_]*2, [0, self.l])
        self.fish_widget.ax.draw_artist(x_line)

        # z-axis
        if not self.setting_nose_pos:
            z_ = event.ydata
            self.set_axis(z_, AXIS_MAPPING[2])
            z_line = self.fish_widget.lines[1]
            z_line.set_data([0, self.w], [z_]*2)
            self.fish_widget.ax.draw_artist(z_line)        

        # blit onto frame
        self.fish_widget.canvas.blit(self.fish_widget.ax.bbox)
        self.fish_widget.canvas.flush_events()        

        # update text
        self.update_text()

    @staticmethod
    def format_vectors_to_table(vector_list : list[vector]):

        head = [ax.upper() for ax in vector_list[0]]
        body = [list(v.values()) for v in vector_list]

        return [head] + body

    def on_click(self, event):
        if event.button == 1:
            if self.setting_nose_pos:
                self.nose_pos = self.current_position[AXIS_MAPPING[0]]
                self.setting_nose_pos = False
            else:
                # in pixels...
                new_position = self.get_relative_position()
                self.annotated_positions += [new_position]
        elif event.button == 3:
            # remove last
            try:
                self.annotated_positions.pop(-1)
            except IndexError:
                pass

        self.update_positions()
        self.draw_fish()

    def update_positions(self):
        if self.annotated_positions:
            self.update_multiposition_controller(
                self.format_vectors_to_table(
                    [v * self.units for v in self.annotated_positions]
                )
            )
        else:
            self.update_multiposition_controller([])

    def update_multiposition_controller(self, multi_positions):
        self.parent_controller.model.configuration["multi_positions"] = multi_positions
        self.parent_controller.multiposition_tab_controller.set_positions(multi_positions)

    def update_text(self):
        relative_position_um = self.get_relative_position() * self.units
        
        tstr =  f"x: {relative_position_um['x']:.2f} um\t" \
                f"y: {relative_position_um['y']:.2f} um\t" \
                f"m: {relative_position_um['m']:.2f} um\t" \
                f"theta: {relative_position_um['theta']:.2f} deg\t" \
                f"channel: {self.channel_names[self.curr_channel_idx]}"
        
        self.text_var.set(tstr)

    def mousewheel_axis(self, scrollbar, delta, axis):
        # get scrollbar range
        s_min = int(scrollbar.cget('from'))
        s_max = int(scrollbar.cget('to'))

        # clip step
        delta = np.clip(delta, a_min=-1, a_max=1)
        
        # invert scrolling
        delta = -delta

        # update pos within range
        new_pos = np.clip(
            self.get_axis(axis) + delta,
            a_min=s_min,
            a_max=s_max
        )

        # update the scrollbar
        scrollbar.set(new_pos)

        # update axis
        self.set_axis(new_pos, axis)

    def set_axis(self, value, axis):
        if value is None:
            return
        
        if axis == 'chan':
            self.curr_channel_idx = value
        else:
            self.current_position[axis] = value

    def get_axis(self, axis):
        if axis == 'chan':
            return self.curr_channel_idx
        else:
            return self.current_position[axis]

    def get_relative_position(self):
        return self.current_position - self.global_origin

    def draw_fish(self):
        # clear the plot
        ax = self.fish_widget.ax
        ax.clear()

        # index the image to display
        chan = self.channel_names[self.curr_channel_idx]
        v_idx = int(self.current_position['theta'])
        y_idx = int(self.current_position[AXIS_MAPPING[1]])

        do_projection = self.do_projection.get()

        if do_projection:
            image_to_display = self.projections[chan][v_idx]
        else:
            image_to_display = self.images[chan][v_idx][y_idx]

        gamma = [
            1.00,
            0.65,
            0.80
        ]

        image_to_display = np.power(image_to_display, gamma[self.curr_channel_idx])

        ax.imshow(image_to_display, cmap='gray')

        # SET UP AXES:
        # scale axes to VAST
        res = 0.5
        ticks = ax.get_xticks()*VAST_UM_PIX/1000
        n_ticks = int(ticks.max()/res)
        tick_labels = np.linspace(0, res*n_ticks, n_ticks+1)
        ticks = np.uint(tick_labels*1000/VAST_UM_PIX)
        ax.set_xticks(ticks)
        _ = ax.set_xticklabels(tick_labels)

        res = 0.25
        ticks = ax.get_yticks()*VAST_UM_PIX/1000
        n_ticks = int(ticks.max()/res)
        tick_labels = np.linspace(0, res*n_ticks, n_ticks+1)
        ticks = np.uint(tick_labels*1000/VAST_UM_PIX)
        ax.set_yticks(ticks)
        _ = ax.set_yticklabels(tick_labels)

        # title
        ax.set_title(
            self.view_names[int(self.current_position['theta'])]
        )

        # ORIGIN X: draw x-origin
        x_origin = self.global_origin[AXIS_MAPPING[0]]
        ax.vlines(x_origin, ymin=0, ymax=self.l, linestyles='--', color='b')

        # nose_pos: if different from x-origin
        if self.nose_pos != x_origin:
            ax.vlines(self.nose_pos, ymin=0, ymax=self.l, linestyles='--', color='g')

        # ORIGIN M: draw capillary top
        cap_top = self.global_origin[AXIS_MAPPING[2]]
        ax.hlines(cap_top, xmin=0, xmax=self.w, linestyles='--', color='b')

        # ORIGIN Y: draw circle to signify y-pos
        scale = 25
        defocus = (2*scale/self.n_slices) * self.get_relative_position()[AXIS_MAPPING[1]]
        ax.add_patch(
            Circle(
                xy=(x_origin - defocus, cap_top - defocus), 
                radius=abs(defocus) + 5,
                color='b',
                fill=(defocus == 0)
            )
        )
        ax.plot(
            [x_origin-scale, x_origin+scale],
            [cap_top-scale, cap_top+scale],
            color='b',
            ls='--'
        )

        # draw annotations
        for i, pos in enumerate(self.annotated_positions):
            curr = self.get_relative_position()
            if pos['theta'] != curr['theta']:
                continue

            abs_pos = self.global_origin + pos
            x = abs_pos['x']
            y = abs_pos['m']
            
            if pos['y'] == curr['y'] or do_projection:
                color = [0, 1, 0]
                weight = 'bold'
            else:
                color = [0.7, 0.15, 0.15]
                weight = 'normal'              

            ax.scatter(x, y, marker='.', color=color)
            ax.text(x, y, i+1, color=color, fontdict={'weight': weight})

        # label axes
        ax.set_xlabel(f"{AXIS_MAPPING[0].upper()} [mm]")
        ax.set_ylabel(f"{AXIS_MAPPING[2].upper()} [mm]")

        # fix xy limits
        ax.set_xlim(0, self.w)
        ax.set_ylim(0, self.l)

        # FINISH: set up canvas
        self.fish_widget.canvas.draw()
        self.background = self.fish_widget.canvas.copy_from_bbox(
            ax.bbox
        )

        self.update_text()

    def manual_find_nose_position(self):
        if not self.setting_nose_pos:
            self.setting_nose_pos = True

    def find_nose_position(self, chan="", view=0, window=5):

        # do this nicer later...
        # cap_path = r"C:\Vast\dcimg_files_saved\emptyCapillary.bmp"
        cap_path = r"Z:\bioinformatics\Danuser_lab\Fiolka\LabMembers\Conor\VAST\Dagan_ExtraVas_Tc32_0dpi\VAST\empty_cap000_01_YStack\_4.tiff"
        cap_im = cv2.imread(cap_path)[:,:,0]
        print(cap_im.min(), cap_im.max())
        cap_im = np.flip(1. - (cap_im/255), axis=0)

        ax = self.fish_widget.ax

        # im = self.projections[chan][view]
        im = self.images[chan][view][3]
        
        print(im.min(), im.max())

        # scale to prevent buffer overflow
        im = 1. - (im / 65535) # uint16

        # divide out cap
        im = im / (cap_im + 1/255)

        ax.imshow(im, cmap='gray')

        print(im.min(), im.max())

        # if self.cap_image:
        #   im = im / (255 - self.cap_image + 1)

        # project
        p = im.sum(axis=0)
        
        # bg-sub
        p -= np.mean(p)
        p[p < 0.] = 0.

        # probability density
        p = p / p.sum()
        x = np.arange(0, len(p))

        # skewness to determine direction
        x_mean = np.sum(x * p)
        x_med  = np.where(np.cumsum(p) >= 0.5)[0][0]

        sign = 2*int(x_med > x_mean) - 1

        from scipy.signal import medfilt
        p = np.array(
            medfilt(p, kernel_size=15) > 0,
            dtype=float
        )

        ax.plot(x, 100 * (p / p.max()))

        # nose detector
        tracker = 0
        trace = []

        for i in range(x[-1] - window):
            s = p[::sign][i:(i+window)]
            idx = s.argmin()

            if idx == window-1:
                tracker += 1
            else:
                tracker = 0
        
            trace.append(tracker)

        trace = trace[::sign]

        ax.plot(trace)

        nose_pos = np.argmax(trace)

        ax.vlines([nose_pos, x_mean, x_med], ymin=0, ymax=len(im), linestyles='--', color=['g', 'r', 'b'])

        # return the nose position along x: pixels
        return nose_pos

    @staticmethod
    def load_stack(dir, chan):
        """
            Loads a single channel from /dir/

            Output dim: [slice, row, col]
        """
        im_list = glob(os.path.join(dir, f"{chan}_*.tiff"))

        # sort by filename
        def get_idx(f):
            return int(Path(f).stem.split('_')[-1])
        im_list.sort(key=get_idx)

        slices = np.array([tifffile.imread(f) for f in im_list])

        return np.flip(slices, axis=1)

    def update_experiment_values(self):
        try:
            self.vast_experiment['ExperimentFile'] = self.vexp_path
            # for ax in self.global_origin.keys():
            #     self.parent_controller.configuration['experiment']['VAST']['GlobalOrigin'][ax] = float(self.global_origin[ax])
            self.vast_experiment['GlobalOrigin'] = {ax: float(val) for ax, val in self.global_origin.items()}
        except Exception as e:
            print("Error:", e)
            traceback.print_exc()

        # reload the fish after updating
        self.load_next_fish(self.well)

    def load_vexp(self):
        vexp_file = filedialog.askopenfile(master=self.view, defaultextension="vexp", title="Load VAST experiment file...")
        self.vexp_path = vexp_file.name
        self.update_experiment_values()

    def parse_vexp(self):
        tree = ET.parse(self.vexp_path)
        return parse_xml(tree.getroot())        

    def parse_well(self, well=None):
        if not well:
            wells = glob(os.path.join(self.working_dir, "Well_*"))
            well = wells[-1] # most recent

        walk = os.walk(well)

        views = []
        for root, dirs, files in walk:
            if dirs:
                continue
            views.append(root)

        chans = {chan.split('_')[0] for chan in files if ".tif" in chan}

        return sorted(chans), sorted(views)
