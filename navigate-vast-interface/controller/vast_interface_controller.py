# Standard library imports
import os
from pathlib import Path
import cv2
from glob import glob
import numpy as np
from tkinter import filedialog
from copy import deepcopy

# Third party imports
from tifffile import tifffile
from skimage.exposure import adjust_gamma

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

    return output

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
            return {k: self[k] - other for k in self}
        else:
            try:
                return {k: self[k] - other[k] for k in self}
            except (TypeError, KeyError):
                print("Must '-' with numeric scalar or dict with matching keys.")
    
    def __add__(self, other):
        if isinstance(other, (int, float)):
            return {k: self[k] + other for k in self}
        else:
            try:
                return {k: self[k] + other[k] for k in self}
            except (TypeError, KeyError):
                print("Must '+' with numeric scalar or dict with matching keys.")

    def __mul__(self, other):
        if isinstance(other, (int, float)):
            return {k: self[k] * other for k in self}
        else:
            try:
                return {k: self[k] * other[k] for k in self}
            except (TypeError, KeyError):
                print("Must '*', with numeric scalar or dict with matching keys.")

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

        # get plugin name to call events from parent_controller
        config_path = os.path.join(Path(__file__).parent.parent, 'plugin_config.yml')
        plugin_config = load_yaml_file(config_path)
        self.plugin_name = plugin_config['name']

        self.initialize()

        self.parent_controller.model.configuration['experiment']['VAST']['VASTAnnotatorStatus'] = True

    def initialize(self):
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
        self.done_button = self.buttons['done']
        self.clear_button = self.buttons['clear']
        self.save_pos_button = self.buttons['save_pos']
        
        # variables
        self.stage_axes = self.parent_controller.configuration_controller.stage_axes
        self.current_position = vector(self.stage_axes, val=0.)
        self.global_origin = vector(self.stage_axes, val=0.)
        self.annotated_positions = []
        self.working_dir = None

        # flip stuff

        # projection stuff
        self.do_projection = self.widgets['project']['variable']
        self.do_projection_check = self.widgets['project']['button']

        # focus pos stuff?

        # append nose...

        # get the vexp
        self.vexp_path = self.parent_controller.configuration['experiment']['VAST']['ExperimentFile']
        self.vexp_path_var.set(self.vexp_path)
        self.vexp = self.parse_vexp()        

        # get channel names and view folders
        (self.channel_names, self.view_names) = self.parse_most_recent_well()
        self.n_views = len(self.view_names)
        self.n_channels = len(self.channel_names)
        self.curr_channel_idx = 0

        # the working dir will be parent of views
        self.working_dir = Path(self.view_names[0]).parent.resolve()

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
        self.y_scrollbar.configure(from_=0, to=self.n_slices-1, command=lambda val: self.set_axis(int(val), 'y'))
        self.theta_scrollbar.configure(from_=0, to=self.n_views-1, command=lambda val: self.set_axis(int(val), 'theta'))
        self.chan_scrollbar.configure(from_=0, to=self.n_channels-1, command=lambda val: self.set_axis(int(val), 'chan'))

        # store step sizes from expt
        self.y_stack_step = self.vexp['AutoStSetup']['yStack']['_stepLenUm']
        self.theta_stack_step = self.vexp['AutoStSetup']['_degrees']

        # mousewheel events
        self.y_scrollbar.bind("<MouseWheel>", lambda event: self.mousewheel_axis(event, 'y'))
        self.theta_scrollbar.bind("<MouseWheel>", lambda event: self.mousewheel_axis(event, 'theta'))
        self.chan_scrollbar.bind("<MouseWheel>", lambda event: self.mousewheel_axis(event, 'chan'))

        # button click events
        self.do_projection_check.configure(command=self.draw_fish)

        # compute projections
        self.projections = {chan: [] for chan in self.images}
        for v in range(self.n_views):
            new_projection = extended_depth_of_field(
                {chan: self.images[chan][v] for chan in self.images},
                ref_chan="",
                ksize=5,
                bsize=11,
                dark_ref_bg=False
            )
            for chan in self.images:
                self.projections[chan].append(new_projection[chan])

        self.draw_fish()

        nose_pos = self.find_nose_position()
        print("Nose pos:", nose_pos)

        # widget events
        self.fish_widget.fig.canvas.mpl_connect(
            'motion_notify_event',
            self.move_crosshair
        )

    def move_crosshair(self, event):
        
        # get position
        x_ = event.xdata
        z_ = event.ydata

        # update current_position
        self.current_position['x'] = x_
        self.current_position['z'] = z_
        
        # create lines
        self.fish_widget.lines[0].set_data([x_]*2, [0, self.l])
        self.fish_widget.lines[1].set_data([0, self.w], [z_]*2)        

        # blit onto frame
        self.fish_widget.canvas.restore_region(self.background)
        for l in self.fish_widget.lines:
            self.fish_widget.ax.draw_artist(l)
        self.fish_widget.canvas.blit(self.fish_widget.ax.bbox)
        self.fish_widget.canvas.flush_events()        

        # update text
        self.update_text()

    def update_text(self):

        tstr = f"{self.current_position}"

        self.text_var.set(tstr)

    def mousewheel_axis(self, event, axis):

        # get scrollbar range
        scrollbar = event.widget
        s_min = int(scrollbar.cget('from'))
        s_max = int(scrollbar.cget('to'))

        # get step
        delta = np.clip(event.delta, a_min=-1, a_max=1)
        
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
        if axis == 'chan':
            self.curr_channel_idx = value
        else:
            self.current_position[axis] = value
        self.draw_fish()

    def get_axis(self, axis):
        if axis == 'chan':
            return self.curr_channel_idx
        else:
            return self.current_position[axis]

    def draw_fish(self):

        # clear the plot
        ax = self.fish_widget.ax
        ax.clear()

        # index the image to display
        chan = self.channel_names[self.curr_channel_idx]
        v_idx = int(self.current_position['theta'])
        y_idx = int(self.current_position['y'])

        if self.do_projection.get():
            image_to_display = self.projections[chan][v_idx]
        else:
            image_to_display = self.images[chan][v_idx][y_idx]

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

        # label axes
        ax.set_xlabel("X [mm]")
        ax.set_ylabel("Z [mm]")

        # fix xy limits
        ax.set_xlim(0, self.w)
        ax.set_ylim(0, self.l)

        # FINISH: set up canvas
        self.fish_widget.canvas.draw()
        self.background = self.fish_widget.canvas.copy_from_bbox(
            ax.bbox
        )

    def find_nose_position(self, chan="", view=0, window=5):

        ax = self.fish_widget.ax

        im = self.projections[chan][view]
        # im = self.images[chan][view][3]
        
        # scale to prevent buffer overflow
        im = 1. - (im / 65535) # uint16

        print(
            "Image details",
            [im.min(), im.max(), im.shape, im.dtype]
            )

        ax.imshow(im, cmap='gray')

        # if self.cap_image:
        #     im = im / (255 - self.cap_image + 1)

        # probability density
        p = im.sum(axis=0)
        p = p / p.sum()
        x = np.arange(0, len(p))

        print(p, f"Sum: {p.sum()}")
        print(x)

        # skewness to determine direction
        x_mean = np.sum(x * p)
        x_med  = np.where(np.cumsum(p) >= 0.5)[0][0]

        ax.plot(x, 100 * (p / p.max()))

        sign = 2*int(x_med > x_mean) - 1

        print("mean:", x_mean)
        print("med:", x_med)
        print("Sign:", sign)

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

        ax.vlines(nose_pos, ymin=0, ymax=len(im), linestyles='--', color='g')        

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

    def parse_vexp(self):
        tree = ET.parse(self.vexp_path)
        return parse_xml(tree.getroot())        

    def parse_most_recent_well(self):
        # walk the VAST autostore path
        walk = os.walk(Path(self.vexp['AutoStSetup']['_storeLocation']['text']).parent)

        # get only Well folders containing images
        well_items = []
        for item in walk:
            if 'Well' in item[0]:
                if item[-1]:
                    well_items += [item]

        # get recent channels and views
        recent_chans = []
        recent_views = []
        for item in well_items[::-1][:2]:
            for im in item[-1]:
                chan = im.split('_')[0]
                view = item[0]
                if chan not in recent_chans:
                    recent_chans += [chan]
                if view not in recent_views:
                    recent_views += [view]

        recent_chans.sort()
        recent_views.sort()

        # middle slice index
        # slice = int(len(well_items[-1][-1])/len(recent_chans)/2)

        return recent_chans, recent_views

class Dummy(GUIController):

    def __init__(self, view, parent_controller : Controller = None):
        super().__init__(view, parent_controller)

        # get plugin name to call events from parent_controller
        config_path = os.path.join(Path(__file__).parent.parent, 'plugin_config.yml')
        plugin_config = load_yaml_file(config_path)
        self.plugin_name = plugin_config['name']

        self.initialize()

        self.parent_controller.model.configuration['experiment']['VAST']['VASTAnnotatorStatus'] = True

    def initialize(self):
        self.variables = self.view.get_variables()
        self.widgets = self.view.get_widgets()
        self.buttons = self.view.buttons

        self.fish_widget = self.widgets['fish_widget']
        self.y_scrollbar = self.widgets['y_scrollbar']
        self.text_var = self.variables['text']
        self.vexp_path_var = self.variables['path']
        self.path_button = self.buttons['path']
        self.set_focus_button = self.buttons['set_focus']
        self.done_button = self.buttons['done']
        self.clear_button = self.buttons['clear']
        self.save_pos_button = self.buttons['save_pos']
        self.flip_yz_button = self.buttons['flip_yz']

        # variables
        self.perspective = 0
        self.stage_axes = self.parent_controller.configuration_controller.stage_axes
        self.positions = []
        self.coord = np.zeros_like(self.stage_axes, dtype=int) # (x,y,z,theta,f,m)
        self.relative_positions = [[]]
        self.nose_position = None
        self.x_pos = 0
        self.y_pos = 0
        self.background = None
        self.locked = False
        self.setting_focus = False
        self.working_dir = None

        self.is_stacking = True

        self.ax_i = [(np.array(self.stage_axes) == ax).argmax() for ax in AXIS_MAPPING]

        # flip
        self.flip = self.widgets["flip"]["variable"]
        self.flip_check = self.widgets["flip"]["button"]

        for axis in self.flip_check:
            self.flip_check[axis].configure(command=self.set_flip_experiment)

        self.pull_flip_from_experiment()
        
        # projection
        self.project = self.widgets["project"]["variable"]
        self.project_check = self.widgets["project"]["button"]
        
        # focus pos
        self.z_focus_pos = 0
        try:
            self.z_focus_pos = self.parent_controller.configuration['experiment']['VAST']['ZFocusPos']
        except KeyError:
            self.parent_controller.configuration['experiment']['VAST']['ZFocusPos'] = self.z_focus_pos

        # append nose
        self.append_nose = self.widgets['append_nose']['variable']
        # self.append_nose_button = self.widgets['append_nose']['button']

        # vexp file path
        self.vexp_path = self.parent_controller.configuration['experiment']['VAST']['ExperimentFile']
        self.vexp_path_var.set(self.vexp_path)
        self.vexp = self.parse_vexp()

        # get channel names
        recent_chans, recent_views = self.parse_most_recent_well()

        self.channel_names = recent_chans
        self.view_names = recent_views
        self.curr_channel = 0
        self.n_views = len(recent_views)
        self.gammas = [1.0] * len(self.channel_names)

        # get working dir
        self.working_dir = Path(self.view_names[0]).parent.resolve()

        # load fish images
        self.images = []

        for v in range(self.n_views):
            new_view = {}
            for chan in self.channel_names:
                new_view[chan] = self.load_stack(
                    # dir=self.view_names[self.n_views - v - 1],
                    dir=self.view_names[v],
                    chan=chan,
                )
            self.images += [new_view]

        self.n_slices, self.l, self.w = self.images[0][self.channel_names[0]].shape

        self.slice = int(self.n_slices/2)
        self.y_scrollbar.set(self.slice)

        # yStack step size
        self.y_stack_step = self.vexp['AutoStSetup']['yStack']['_stepLenUm']
        self.y_scrollbar.configure(from_=0, to=self.n_slices-1, command=self.z_on_update)

        # compute extended depth of field
        self.projections = {
            'edof': [extended_depth_of_field(
                        self.images[v], 
                        ref_chan="",
                        ksize=5,
                        bsize=11,
                        dark_ref_bg=False
                    ) for v in range(self.n_views)]
        }

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
        
        self.fish_widget.fig.canvas.mpl_connect(
            'key_press_event',
            self.key_press
        )

        self.fish_widget.fig.canvas.mpl_connect(
            'scroll_event',
            self.mouse_wheel
        )

        self.path_button.configure(command=self.load_vexp)
        self.set_focus_button.configure(command=self.set_focus)
        self.done_button.configure(command=self.close)
        self.clear_button.configure(command=self.initialize)
        self.save_pos_button.configure(command=self.save_positions)
        self.flip_yz_button.configure(command=self.flip_yz)
        self.project_check.configure(command=self.draw_fish)

    def save_positions(self):
        output = np.vstack((
            np.asarray(self.nose_position),
            np.asarray(self.positions)
        ))

        print(f"Saving...\n{output}\n... to {self.working_dir}")

        np.savetxt(
            fname = os.path.join(self.working_dir, f"positions.txt"),
            X = output,
            delimiter = '\t'
        )

    def z_on_update(self, val):
        z_slice = int(val)

        if z_slice != self.slice:
            self.slice = z_slice
            self.draw_fish()

    def flip_yz(self):
        self.images.reverse()
        self.draw_fish()

    def set_focus(self):
        self.setting_focus = True
        self.perspective = 1
        self.locked = False
        self.set_focus_button.state(['disabled'])
        self.draw_fish()

    def set_flip_experiment(self):
        try:
            for axis in self.flip:
                self.parent_controller.configuration['experiment']['VAST']['Flip'][axis] = self.flip[axis].get()
        except KeyError:
            self.parent_controller.configuration['experiment']['VAST']['Flip'] = {}
            self.set_flip_experiment()
        
        self.update_experiment_values()

    def pull_flip_from_experiment(self):
        for axis in self.flip:
            try:
                self.flip[axis].set(self.parent_controller.configuration['experiment']['VAST']['Flip'][axis])
            except KeyError:
                self.flip[axis].set(False)

    def parse_most_recent_well(self):
        # walk the VAST autostore path
        walk = os.walk(Path(self.vexp['AutoStSetup']['_storeLocation']['text']).parent)

        # get only Well folders containing images
        well_items = []
        for item in walk:
            if 'Well' in item[0]:
                if item[-1]:
                    well_items += [item]

        # get recent channels and views
        recent_chans = []
        recent_views = []
        for item in well_items[::-1][:2]:
            for im in item[-1]:
                chan = im.split('_')[0]
                view = item[0]
                if chan not in recent_chans:
                    recent_chans += [chan]
                if view not in recent_views:
                    recent_views += [view]

        recent_chans.sort()
        recent_views.sort()

        # middle slice index
        # slice = int(len(well_items[-1][-1])/len(recent_chans)/2)

        return recent_chans, recent_views

    def load_vexp(self):
        vexp_file = filedialog.askopenfile(master=self.view, defaultextension="vexp", title="Load VAST experiment file...")
        self.vexp_path = vexp_file.name
        self.update_experiment_values()
        self.initialize()

    def parse_vexp(self):
        tree = ET.parse(self.vexp_path)
        return parse_xml(tree.getroot())

    def close(self):
        self.parent_controller.model.configuration['experiment']['VAST']['VASTAnnotatorStatus'] = False

    def update_experiment_values(self):
        # if np.size(self.relative_positions):
        #     # self.parent_controller.model.configuration['experiment']['MultiPositions'] = self.relative_positions
        #     self.parent_controller.model.configuration["multi_positions"] = self.relative_positions
        #     self.parent_controller.model.configuration["experiment"]["MicroscopeState"][
        #         "multiposition_count"
        #     ] = len(self.relative_positions)
        
        if self.vexp_path:
            self.parent_controller.configuration['experiment']['VAST']['ExperimentFile'] = self.vexp_path

        if self.z_focus_pos:
            self.parent_controller.configuration['experiment']['VAST']['ZFocusPos'] = self.z_focus_pos

    def load_stack(self, dir, chan=""):
        im_list = glob(os.path.join(dir, f"{chan}_*.tiff"))
        im_list.sort()

        slices = np.array([tifffile.imread(f) for f in im_list])

        return np.flip(slices, axis=1)

    def load_image(self, dir, chan="", slice=3):
        im_path = os.path.join(
            dir,
            f"{chan}_{slice}.tiff"
        )

        im = tifffile.imread(im_path)
        return np.flip(im, axis=0)

    def draw_fish(self):
        ax = self.fish_widget.ax

        # clear axes
        ax.clear()

        # initialize plot
        chan = self.channel_names[self.curr_channel]
        
        if self.project.get():
            image_to_display = self.projections['edof'][self.perspective][chan]
        else:
            image_to_display = self.images[self.perspective][chan][self.slice]

        ax.imshow(
            adjust_gamma(image_to_display, self.gammas[self.curr_channel]),
            cmap='gray'
        )

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

        # label axes
        ax.set_xlabel("X [mm]")
        if self.perspective == 0:
            ax.set_ylabel("Y [mm]")
        else:
            ax.set_ylabel("Z [mm]")

        # fix xy limits
        ax.set_xlim(0, self.w)
        ax.set_ylim(0, self.l)

        # set title to current well/view
        title = self.view_names[self.perspective].split('\\')[-1]
        ax.set_title(title)

        # display selected points
        if self.nose_position is not None:
            ax.scatter(self.nose_position[0], self.nose_position[self.perspective+1], marker='x', color=[0,0,1])
        if len(self.positions) > 0:
            c = np.array(self.positions)
            ax.scatter(c[:,0], c[:,self.perspective+1], marker='+', color=[0,1,0])

        # display focus origin, if it exists
        if self.z_focus_pos and self.perspective == 1:
            ax.hlines(self.z_focus_pos, 0, self.w, colors=[0,1,0], linestyles='--')

        # set up canvas
        self.fish_widget.canvas.draw()
        self.background = self.fish_widget.canvas.copy_from_bbox(
            ax.bbox
        )

    @staticmethod
    def coord2str(c):
        c = np.asarray(c) * VAST_UM_PIX
        return f"({c[0]:.2f}, {c[1]:.2f}, {c[2]:.2f})\t"

    def update_text(self):
        tstr = f"channel: {self.channel_names[self.curr_channel]}"

        tstr += "\tnose_position: "
        p0 = 0
        if self.nose_position is not None:
            tstr += self.coord2str(self.nose_position)
            p0 = self.nose_position[:3]
            tstr += "current: "
        
        try:
            if self.perspective == 0:
                pos = np.asarray([self.x_pos, self.y_pos, np.nan])
            else:
                pos = np.asarray([self.coord[0], self.coord[1], self.y_pos])
            tstr += self.coord2str(pos - p0)     
        except TypeError:
            pass

        self.text_var.set(tstr)

    def move_crosshair(self, event):
        if not self.locked:
            # create the new data    
            if self.perspective == 0:
                self.x_pos = event.xdata
            self.y_pos = event.ydata
            if not self.setting_focus:
                self.fish_widget.lines[0].set_data([self.x_pos]*2, [0, self.l])
            self.fish_widget.lines[1].set_data([0, self.w], [self.y_pos]*2)

            # blit new data into old frame
            self.fish_widget.canvas.restore_region(self.background)
            for l in self.fish_widget.lines:
                self.fish_widget.ax.draw_artist(l)
            self.fish_widget.canvas.blit(self.fish_widget.ax.bbox)
            self.fish_widget.canvas.flush_events()

            self.update_text()

    def update_positions(self):
        new_position = deepcopy(self.coord)
        
        if self.nose_position is not None:
            self.positions += [new_position]
            
            do_flip = np.ones(3)
            for i, axis in enumerate(self.flip):
                if self.flip[axis].get():
                    do_flip[i] = -1

            self.relative_positions = np.zeros(np.shape(self.positions))
            for i, p in enumerate(self.positions):
                self.relative_positions[i,self.ax_i[0]] = do_flip[0] * (p[0] - self.nose_position[0]) * VAST_UM_PIX
                self.relative_positions[i,self.ax_i[1]] = do_flip[1] * (p[1] - self.nose_position[1]) * VAST_UM_PIX
                self.relative_positions[i,self.ax_i[2]] = do_flip[2] * (p[2] - self.z_focus_pos)      * VAST_UM_PIX

            # append nose positions to start
            if self.append_nose.get():
                self.relative_positions = np.vstack((
                    np.zeros_like(self.stage_axes, dtype=int),
                    self.relative_positions
                ))

            # send multipositions to controller with stage_axes as the header
            self.update_multiposition_controller(
                [[ax.upper() for ax in self.stage_axes]] + self.relative_positions.tolist()
            )
            
            self.update_experiment_values()
        else:
            self.nose_position = new_position

    def key_press(self, event):
        # if event.key == 'down':
        #     self.slice = np.min([self.n_slices - 1, self.slice + 1])
        #     self.y_scrollbar.set(self.slice)
        #     self.draw_fish()
        # elif event.key == 'up':
        #     self.slice = np.max([0, self.slice - 1])
        #     self.y_scrollbar.set(self.slice)
        #     self.draw_fish()
        
        try:
            key_num = int(event.key)
        except ValueError:
            return

        for c, _ in enumerate(self.channel_names):
            if key_num == (c+1):
                self.curr_channel = c
                self.draw_fish()

    def mouse_wheel(self, event):
        # self.gammas[self.curr_channel] += event.step * 0.02
        # self.gammas[self.curr_channel] = np.clip(self.gammas[self.curr_channel], 0.02, 1.0)
        
        self.slice = np.clip(
            self.slice - int(np.clip(event.step, a_min=-1, a_max=1)), 
            a_min=0, 
            a_max=self.n_slices-1
            )
        
        self.y_scrollbar.set(self.slice)
        self.draw_fish()

    def on_click(self, event):
        if event.button == 1:
            if not self.locked:          
                if self.setting_focus:
                    self.z_focus_pos = self.y_pos
                    self.setting_focus = False
                    self.locked = True
                    self.set_focus_button.state(['!disabled'])
                    self.update_experiment_values()
                elif self.perspective == 0:
                    self.coord[0] = self.x_pos # x
                    self.coord[1] = self.y_pos # y
                    self.perspective = 1
                elif self.perspective == 1:
                    self.coord[2] = self.y_pos # z
                    self.update_positions()
                    self.perspective = 0
        elif event.button == 3:
            if self.perspective < self.n_views-1:
                self.perspective += 1
            else:
                self.perspective = 0
            
            self.locked = self.perspective > 0

        self.draw_fish()

    def update_multiposition_controller(self, multi_positions):
        self.parent_controller.model.configuration["multi_positions"] = multi_positions
        self.parent_controller.multiposition_tab_controller.set_positions(multi_positions)

    def build_vast_popup(self, event):
        print(f"Event = {event}")
        # try:
        #     self.parent_controller.plugin_controller.popup_funcs[self.plugin_name]()
        # except Exception as e:
        #     print(e)

        # reinitialize
        self.__init__(self.view, self.parent_controller)

    @property
    def custom_events(self):
        """Custom events for the controller"""
        return {
            "build_vast_popup": self.build_vast_popup,
            "close": self.close
        }