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
from matplotlib.patches import Circle

# Local application imports
from navigate.controller.sub_controllers.gui import GUIController
from navigate.controller.controller import Controller
from navigate.tools.file_functions import load_yaml_file, save_yaml_file

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
    def __init__(self, d, val=None):
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

    def __bool__(self):
        return all(val != None for val in self.values()) and self.keys()

class VastInterfaceController(GUIController):

    def __init__(self, view, parent_controller : Controller = None):
        super().__init__(view, parent_controller)

        try:
            # get plugin name to call events from parent_controller
            config_path = os.path.join(Path(__file__).parent.parent, 'plugin_config.yml')
            plugin_config = load_yaml_file(config_path)
            self.plugin_name = plugin_config['name']

            self.initialize()

            # self.vast_experiment['VASTAnnotatorStatus'] = True
        except Exception as e:
            traceback.print_exc()

    def store_absolute_stage_position_from_controller(self):
        # store as a vector
        self.absolute_stage_pos_um = self.get_abs_stage_pos_um_from_controller()

    def get_abs_stage_pos_um_from_controller(self):
        # stop_stage: refresh ax_pos in experiment
        self.parent_controller.stop_stage()

        # return stage pos dictionary
        stage_pos_dict = self.parent_controller.model.get_stage_position()

        # return a vector
        return vector({k.split('_')[0]: v for k, v in stage_pos_dict.items()})

    def set_xm_calibration(self, ax='x', i: int=0):
        if self.cursor is not None:
            # image position [pix]
            self.variables[f"{ax}{i}_pix"].set(float(self.cursor[ax]))

            # stage position [um]
            stage_pos = self.get_abs_stage_pos_um_from_controller()
            self.variables[f"{ax}{i}_um"].set(float(stage_pos[ax]))         

            # recalculate pixel size
            if i == 0:
                self.global_pixel_origin[ax] = self.cursor[ax]
                self.global_phys_origin[ax]  = stage_pos[ax]
            elif i == 1:
                self.calculate_xm_pixel_size(ax)
            
            self.update_calibration()

    def set_y_calibration(self):
        # stage position [um]
        stage_pos = self.get_abs_stage_pos_um_from_controller()

        y0 = int(self.curr_abs_pos_pix['y'])
        self.units['y'] = float(self.variables[f"dy_um_step"].get())
        
        self.global_pixel_origin['y'] = y0
        
        # set the physical focus origin to the absolute y-stage position
        self.global_phys_origin['y']  = stage_pos['y'] 

        self.variables["y0_step"].set(y0)

        self.update_calibration()

    def set_theta_calibration(self):
        theta0 = int(self.curr_abs_pos_pix['theta'])
        self.units['theta'] = float(self.variables[f"dtheta_deg_step"].get())
        self.global_pixel_origin['theta'] = theta0
        self.variables["theta0_step"].set(theta0)

        self.update_calibration()

    def calculate_xm_pixel_size(self, ax='x'):
        d_pix = self.variables[f"{ax}1_pix"].get() - self.variables[f"{ax}0_pix"].get()
        d_um  = self.variables[f"{ax}1_um"].get()  - self.variables[f"{ax}0_um"].get()       

        d_um_pix = abs(d_um / d_pix)
        
        self.units[ax] = d_um_pix
        self.variables[f"d{ax}_um_pix"].set(f"{d_um_pix:.3f}")

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

        # axis flipping binds
        self.do_flip = self.widgets['flip']['variable']
        def _update_pos_trace_wrapper(*args):
            self.update_positions()
        for ax in self.do_flip.keys():
            self.do_flip[ax].trace_add("write", _update_pos_trace_wrapper)

        # text variable
        self.text_var = self.variables['text']

        # variables
        self.calibration = {}
        self.stage_axes = self.parent_controller.configuration_controller.stage_axes
        self.curr_abs_pos_pix = vector(self.stage_axes, val=0.)
        self.annotated_positions = []
        self.well = None
        self.m_focus_position = None
        self.reference_view = 0
        self.nose_pos = None
        self.setting_nose_pos = False
        self.setting_focus_pos = False
        self.background = None
        self.current_display_image = None
        self._cursor_in_ax = False
        self._shift_held = False
        self.ref_channel = None

        # projection stuff
        self.do_projection = self.widgets['project']['variable']
        self.do_projection_check = self.widgets['project']['button']
        self.do_color = self.widgets['color']['variable']
        self.do_color_check = self.widgets['color']['button']

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
        self.buttons["load_well"].configure(command=self.load_specific_well) 
        self.buttons["pull_from_mp"].configure(command=self.pull_from_mp_table)       
        self.buttons["mark_position"].configure(command=self.create_new_annotated_position)
        self.buttons["query_stage"].configure(command=self.set_cursor_based_on_stage_query)
        self.buttons["save_calib"].configure(command=self.save_calibration)
        self.buttons["load_calib"].configure(command=self.load_calibration)

        self.do_projection_check.configure(command=self.draw_fish)
        self.do_color_check.configure(command=self.draw_fish)

        # calibration buttons
        for i in range(2):
            for ax in ['x', 'm']:
                self.buttons[f"set_{ax}{i}"].configure(
                    command=lambda ax=ax, i=i: self.set_xm_calibration(ax=ax, i=i)
                    )
        self.buttons["set_y0"].configure(command=self.set_y_calibration)
        self.buttons["set_theta0"].configure(command=self.set_theta_calibration)

        # widget events
        self.fish_widget.fig.canvas.mpl_connect(
            'motion_notify_event',
            self.move_crosshair
        )

        self.fish_widget.fig.canvas.mpl_connect(
            'figure_leave_event',
            self._on_figure_leave
        )

        self.fish_widget.fig.canvas.mpl_connect(
            'key_press_event',
            self._on_key_press
        )

        self.fish_widget.fig.canvas.mpl_connect(
            'key_release_event',
            self._on_key_release
        )

        # Give canvas keyboard focus on hover so key events fire without a click
        self.fish_widget.canvas.get_tk_widget().bind(
            '<Enter>',
            lambda e: self.fish_widget.canvas.get_tk_widget().focus_set()
        )

        self.fish_widget.fig.canvas.mpl_connect(
            'button_press_event',
            self.on_click
        )

        self.fish_widget.fig.canvas.mpl_connect(
            'scroll_event',
            lambda event: self._canvas_scroll_event_wrapper(event)
        )

        # query the current absolute stage position and store it
        self.store_absolute_stage_position_from_controller()

        # create the reference cursor
        self.cursor = None

        # create units vector
        self.units = vector(self.stage_axes, val=1.0)

    def _canvas_scroll_event_wrapper(self, event):
        self.mousewheel_axis(self.y_scrollbar, event.step, 'y')
        self.move_crosshair()

    def load_specific_well(self):
        well = filedialog.askdirectory(title="Choose the Well directory:")
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

    def load_next_fish(self, well):

        if well != self.well:
            self.well = well

        # pull calibration from experiment
        self.pull_calib_from_experiment()

        # get channel names and view folders
        try:
            (self.channel_names, self.view_names) = self.parse_well(well)
            self.n_views = len(self.view_names)
            self.n_channels = len(self.channel_names)      
        except Exception as e:
            print(e)
            traceback.print_exc()
            return

        # set the reference channel for image processing to Brightfield
        # Make sure Brightfield is 1st in VAST!
        if self.ref_channel is None:
            self.ref_channel = self.channel_names[0]

        self.curr_channel_idx = 0

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

        # # need to pick a view to calculate nose_pos, in_focus
        # self.reference_view = 0

        # # compute projections and find in_focus_slice
        # self.projections = {chan: [] for chan in self.images}
        # # # self.in_focus_slice = 0
        # for v in range(self.n_views):
        #     new_projection, indices = extended_depth_of_field(
        #         {chan: self.images[chan][v] for chan in self.images},
        #         ref_chan=self.ref_channel,
        #         ksize=5,
        #         bsize=11,
        #         dark_ref_bg=False
        #     )
        #     # if v == self.reference_view:
        #     #     # self.in_focus_slice = stats.mode(indices.flatten()).mode
        #     for chan in self.images:
        #         self.projections[chan].append(new_projection[chan])

        # automatically calculate nose position (if needed)
        # if self.nose_pos is None:
        #     self.nose_pos = self.find_nose_position(
        #         chan=self.ref_channel,
        #     )

        # start with scrollbar set to in-focus slice
        # self.y_scrollbar.set(# self.in_focus_slice)
        # self.set_axis(# self.in_focus_slice, axis=AXIS_MAPPING[1])

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

    def _on_key_press(self, event):
        if event.key == 'shift':
            self._shift_held = True
            self.move_crosshair()

    def _on_key_release(self, event):
        if event.key == 'shift':
            self._shift_held = False
            self.move_crosshair()

    def _on_figure_leave(self, _):
        if self.fish_widget.inset_ax.get_visible():
            self.fish_widget.inset_ax.set_visible(False)
            if self.background is not None:
                self.fish_widget.canvas.restore_region(self.background)
                self.fish_widget.canvas.blit(self.fish_widget.fig.bbox)

    def move_crosshair(self, event=None):
        ax = self.fish_widget.ax

        if event is not None:
            # Use display-space containment so inset_ax can't steal focus
            if not ax.bbox.contains(event.x, event.y):
                self._cursor_in_ax = False
                if self.fish_widget.inset_ax.get_visible():
                    self.fish_widget.inset_ax.set_visible(False)
                    if self.background is not None:
                        self.fish_widget.canvas.restore_region(self.background)
                        self.fish_widget.canvas.blit(self.fish_widget.fig.bbox)
                return

            self._cursor_in_ax = True
            xdata, ydata = ax.transData.inverted().transform((event.x, event.y))
            self.set_axis(xdata, AXIS_MAPPING[0])
            self.set_axis(ydata, AXIS_MAPPING[2])

        if self.background is None:
            return

        self.fish_widget.canvas.restore_region(self.background)

        # Retrieve x, y: still valid when called with event=None after a scroll
        x = self.curr_abs_pos_pix[AXIS_MAPPING[0]]
        y = self.curr_abs_pos_pix[AXIS_MAPPING[2]]

        x_line = self.fish_widget.lines[0]
        x_line.set_data([x]*2, [0, self.l])
        ax.draw_artist(x_line)

        m_line = self.fish_widget.lines[1]
        m_line.set_data([0, self.w], [y]*2)
        ax.draw_artist(m_line)

        # Update ROI if needed
        self._update_ROI((x, y))

        self.fish_widget.canvas.blit(self.fish_widget.fig.bbox)
        self.update_text()

    def _update_ROI(self, pos: tuple[float]):
        # pixel position
        x, y = pos

        if self.current_display_image is not None and self._shift_held:
            # Show the ROI if needed
            if not self.fish_widget.inset_ax.get_visible():
                self.fish_widget.inset_ax.set_visible(True)

            cx = int(np.clip(round(x), 0, self.w - 1))
            cy = int(np.clip(round(y), 0, self.l - 1))

            roi = self.get_pixels_ROI(
                self.current_display_image,
                pos=(cx, cy),
                dim=(self.l, self.w),
                roi_half=32
            )

            self.fish_widget.inset_im.set_data(roi)
            if roi.ndim == 2:
                self.fish_widget.inset_im.set_clim(np.nanmin(roi), np.nanmax(roi))

            self.fish_widget.set_inset_ax_position((cx, cy))
            self.fish_widget.inset_ax.draw_artist(self.fish_widget.inset_im)
        else:
            # Hide the ROI if there's no image
            if self.fish_widget.inset_ax.get_visible():
                self.fish_widget.inset_ax.set_visible(False)        

    @staticmethod
    def get_pixels_ROI(im: np.ndarray, pos: tuple[int], dim: tuple[int], roi_half: int=16):
        cx, cy = pos
        l, w   = dim

        xmin, xmax = max(0, cx - roi_half), min(w, cx + roi_half + 1)
        ymin, ymax = max(0, cy - roi_half), min(l, cy + roi_half + 1)
        
        # read ROI from im
        roi = im[ymin:ymax, xmin:xmax]

        if roi.ndim == 2:
            padded = np.zeros((2*roi_half + 1, 2*roi_half + 1), dtype=roi.dtype)
        else:
            padded = np.zeros((2*roi_half + 1, 2*roi_half + 1, roi.shape[2]), dtype=roi.dtype)

        yoff = (padded.shape[0] - roi.shape[0]) // 2
        xoff = (padded.shape[1] - roi.shape[1]) // 2
        padded[yoff:yoff + roi.shape[0], xoff:xoff + roi.shape[1], ...] = roi
        
        return padded[::-1]

    @staticmethod
    def format_vectors_to_table(vector_list : list[vector]):

        head = [ax.upper() for ax in vector_list[0]]
        body = [list(v.values()) for v in vector_list]

        return [head] + body

    def on_click(self, event):
        if event.button == 1:
            # just set the cursor
            self.cursor = deepcopy(self.curr_abs_pos_pix)
        elif event.button == 3:
            # remove most recent annotated position
            try:
                self.annotated_positions.pop(-1)
            except IndexError:
                pass

        self.update_positions()
        self.draw_fish()

    def create_new_annotated_position(self):

        if self.cursor is None:
            return

        # new_position = self.cursor - self.global_pixel_origin
        self.annotated_positions += [self.cursor - self.global_pixel_origin]

        # get rid of the cursor
        self.cursor = None

        # update positions list
        self.update_positions()

        # redraw
        self.draw_fish()

    def update_positions(self):
        if self.annotated_positions:

            # build signs vector
            signs = vector(self.stage_axes, val=1.)
            for ax, var in self.do_flip.items():
                signs[ax] = 2.*float(var.get()) - 1.

            physical_origin = self.global_phys_origin # in um, degrees measured from stage

            multipos_vectors_list = [
                physical_origin + signs * v * self.units \
                for v in self.annotated_positions
            ]

            # always add the origin
            multipos_vectors_list = [physical_origin] + multipos_vectors_list

            self.update_multiposition_controller(
                self.format_vectors_to_table(
                    multipos_vectors_list
                )
            )
        else:
            self.update_multiposition_controller([])

    def set_cursor_based_on_stage_query(self):

        # query absolute stage position (um / deg)
        physical_abs_pos = self.get_abs_stage_pos_um_from_controller()

        # compute physical position relative to the saved physical origin
        physical_rel_pos = physical_abs_pos - self.global_phys_origin

        # build signs vector (same convention as in update_positions)
        signs = vector(self.stage_axes, val=1.)
        for ax, var in self.do_flip.items():
            signs[ax] = 2. * float(var.get()) - 1.

        # compute pixel-relative position: v = (physical_rel_pos / units) * signs
        # safe elementwise division by units
        pixel_rel = vector({
            ax: (physical_rel_pos[ax] / self.units[ax]) if self.units[ax] else 0.0
            for ax in self.stage_axes
        })

        pixel_rel = signs * pixel_rel

        # integer axes: convert y/theta to integers (steps)
        pixel_rel['y'] = int(round(pixel_rel['y']))
        pixel_rel['theta'] = int(round(pixel_rel['theta']))

        # compute absolute pixel coordinates in image space
        pixel_abs = self.global_pixel_origin + pixel_rel

        # set the cursor (use deepcopy to be safe)
        self.cursor = deepcopy(pixel_abs)

        # force a redraw so the cursor appears
        self.update_positions()
        self.draw_fish()

    def update_multiposition_controller(self, multi_positions):
        self.parent_controller.model.configuration["multi_positions"] = multi_positions
        self.parent_controller.multiposition_tab_controller.set_positions(multi_positions)

    def update_text(self):
        relative_position_um = self.get_relative_position() * self.units
        
        tstr =  f"x: {relative_position_um['x']:.2f} um\t" \
                f"m: {relative_position_um['m']:.2f} um\t" \
                f"y: {relative_position_um['y']:.2f} um\t" \
                f"\u03B8: {relative_position_um['theta']:.2f} deg\t" \
                f"channel: {self.channel_names[self.curr_channel_idx]}"
        
        pix = self.curr_abs_pos_pix

        tstr += "\n" \
                f"x: {pix['x']:.2f} pix\t" \
                f"m: {pix['m']:.2f} pix\t" \
                f"y: {int(pix['y'])} steps\t" \
                f"\u03B8: {int(pix['theta'])} steps\t"
        
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
            self.curr_abs_pos_pix[axis] = value

    def get_axis(self, axis):
        if axis == 'chan':
            return self.curr_channel_idx
        else:
            return self.curr_abs_pos_pix[axis]

    def get_relative_position(self):
        return self.curr_abs_pos_pix - self.global_pixel_origin

    def draw_fish(self):
        # clear the plot
        ax = self.fish_widget.ax
        ax.clear()

        # index the image to display
        chan = self.channel_names[self.curr_channel_idx]
        v_idx = int(self.curr_abs_pos_pix['theta'])
        y_idx = int(self.curr_abs_pos_pix[AXIS_MAPPING[1]])

        do_projection = self.do_projection.get()
        do_color = self.do_color.get()

        if do_projection:
            image_to_display = self.projections[chan][v_idx]
        else:
            image_to_display = self.images[chan][v_idx][y_idx]

        # store the current image used by the display for ROI extraction
        self.current_display_image = image_to_display

        # TODO: Very hacky and unoptimized...
        # gamma
        gm = [
            0.85,
            0.65,
            0.45
        ]
        cl = [
            [0.05, 1.05],
            [0.05, 0.3],
            [0.10, 0.4]
        ]
        def gamma(c_idx: int):
            if do_projection:
                im = self.projections[self.channel_names[c_idx]][v_idx]
            else:
                im = self.images[self.channel_names[c_idx]][v_idx][y_idx]
            # gamma
            im = np.power(im/65535, gm[c_idx])
            # clip
            mi, mx = cl[c_idx]
            im = np.clip(im, a_min=mi, a_max=mx)
            # rescale
            im = (im - mi) / (mx - mi)

            return im
            
        if do_color:
            im_rgb = np.zeros((3,) + image_to_display.shape)

            im_rgb[0] = 0.3*gamma(0) + 0.7*gamma(2)
            im_rgb[1] = 0.3*gamma(0) + 0.7*gamma(1)
            im_rgb[2] = 0.3*gamma(0)

            disp_image = np.moveaxis(im_rgb, 0, -1)
            self.current_display_image = disp_image
            ax.imshow(disp_image)
        else:
            disp_image = np.power(image_to_display, gm[self.curr_channel_idx])
            self.current_display_image = disp_image
            ax.imshow(disp_image, cmap='gray')
        

        # SET UP AXES:
        # scale axes to VAST
        x_um_pix = self.units[AXIS_MAPPING[0]]
        res = 0.5
        ticks = ax.get_xticks()*x_um_pix/1000
        n_ticks = int(ticks.max()/res)
        tick_labels = np.linspace(0, res*n_ticks, n_ticks+1)
        ticks = np.uint(tick_labels*1000/x_um_pix)
        ax.set_xticks(ticks)
        _ = ax.set_xticklabels(tick_labels)

        y_um_pix = self.units[AXIS_MAPPING[2]]
        res = 0.25
        ticks = ax.get_yticks()*y_um_pix/1000
        n_ticks = int(ticks.max()/res)
        tick_labels = np.linspace(0, res*n_ticks, n_ticks+1)
        ticks = np.uint(tick_labels*1000/y_um_pix)
        ax.set_yticks(ticks)
        _ = ax.set_yticklabels(tick_labels)

        # title
        ax.set_title(
            self.view_names[int(self.curr_abs_pos_pix['theta'])]
        )

        # ORIGIN X: draw x-origin
        x_origin = self.global_pixel_origin[AXIS_MAPPING[0]]
        ax.vlines(x_origin, ymin=0, ymax=self.l, linestyles='--', color='b')

        # nose_pos: if different from x-origin
        if self.nose_pos != x_origin:
            ax.vlines(self.nose_pos, ymin=0, ymax=self.l, linestyles='--', color='g')

        # ORIGIN M: draw capillary top
        m_origin = self.global_pixel_origin[AXIS_MAPPING[2]]
        ax.hlines(m_origin, xmin=0, xmax=self.w, linestyles='--', color='b')

        if self.m_focus_position is not None and self.m_focus_position != m_origin:
            ax.hlines(self.m_focus_position, xmin=0, xmax=self.w, linestyles='--', color='g')

        # ORIGIN Y: draw circle to signify y-pos
        scale = 25
        defocus = (2*scale/self.n_slices) * self.get_relative_position()[AXIS_MAPPING[1]]
        ax.add_patch(
            Circle(
                xy=(x_origin - defocus, m_origin - defocus), 
                radius=abs(defocus) + 5,
                color='b',
                fill=(defocus == 0)
            )
        )
        ax.plot(
            [x_origin-scale, x_origin+scale],
            [m_origin-scale, m_origin+scale],
            color='b',
            ls='--'
        )

        # draw cursor
        if  self.cursor is not None:
            x = self.cursor['x']
            y = self.cursor['m']
            ax.scatter(x, y, s=75, marker='+', color=(0.0, 0.7, 0.2))

        # draw annotations
        for i, pos in enumerate(self.annotated_positions):
            curr = self.get_relative_position()
            if pos['theta'] != curr['theta']:
                continue

            abs_pos = self.global_pixel_origin + pos
            x = abs_pos['x']
            y = abs_pos['m']
            
            if pos['y'] == curr['y'] or do_projection:
                color = [1, 1, 1]
                weight = 'normal'

            else:
                color = [0.7, 0.15, 0.15]
                weight = 'normal'              

            ax.scatter(x, y, s=25, facecolors='none', edgecolors=color)
            ax.text(x+5, y+5, i+1, color=color, fontdict={'weight': weight})

        # label axes
        ax.set_xlabel(f"{AXIS_MAPPING[0].upper()} [mm]")
        ax.set_ylabel(f"{AXIS_MAPPING[2].upper()} [mm]")

        # fix xy limits
        ax.set_xlim(0, self.w)
        ax.set_ylim(0, self.l)

        # FINISH: set up canvas
        # Hide inset before capturing background so it is never baked into it
        self.fish_widget.inset_ax.set_visible(False)
        self.fish_widget.canvas.draw()
        self.background = self.fish_widget.canvas.copy_from_bbox(
            self.fish_widget.fig.bbox
        )

        # Re-render crosshair/ROI if the cursor was inside the axes when the
        # slice changed (e.g. mousewheel scroll), so they don't disappear
        if self._cursor_in_ax:
            self.move_crosshair()
        else:
            self.update_text()

    @staticmethod
    def load_stack(dir, chan):
        """
            Loads a single channel from /dir/

            Output dim: [slice, row, col]
        """
        im_list = glob(os.path.join(dir, f"*_{chan}_*.tiff"))

        # sort by filename
        def get_idx(f):
            return int(Path(f).stem.split('_')[-1].replace('step', ''))
        im_list.sort(key=get_idx)

        slices = np.array([tifffile.imread(f) for f in im_list])

        return np.flip(slices, axis=1)

    def pull_calib_from_experiment(self):
        
        self.calibration = self.vast_experiment["Calibration"]

        position_0 = vector(self.calibration["Position_0"])
        position_1 = vector(self.calibration["Position_1"])
        units      = vector(self.calibration["Units"])

        # init global origin [pix, steps]
        self.global_pixel_origin = vector(self.stage_axes, val=0.)
        self.global_pixel_origin['x'] = position_0['x']['pix']
        self.global_pixel_origin['m'] = position_0['m']['pix']
        self.global_pixel_origin['y'] = position_0['y']['step']
        self.global_pixel_origin['theta'] = position_0['theta']['step']
        
        # units
        self.units = units
        
        # init global origin [um, deg]
        self.global_phys_origin = vector(self.stage_axes, val=0.)
        self.global_phys_origin['x'] = position_0['x']['um']
        self.global_phys_origin['m'] = position_0['m']['um']
        self.global_phys_origin['y'] = position_0['y']['um']
        self.global_phys_origin['theta'] = 0.0 # defined as zero     

        # x vars
        self.variables["x0_pix"].set(position_0['x']['pix'])
        self.variables["x0_um"].set( position_0['x']['um'])
        self.variables["x1_pix"].set(position_1['x']['pix'])
        self.variables["x1_um"].set( position_1['x']['um'])
        self.variables["dx_um_pix"].set(f"{units['x']:.3f}")

        # m vars
        self.variables["m0_pix"].set(position_0['m']['pix'])
        self.variables["m0_um"].set( position_0['m']['um'])
        self.variables["m1_pix"].set(position_1['m']['pix'])
        self.variables["m1_um"].set( position_1['m']['um'])
        self.variables["dm_um_pix"].set(f"{units['m']:.3f}")

        # y vars
        self.variables["y0_step"].set(position_0['y']['step'])
        self.variables["dy_um_step"].set(units['y'])

        # theta vars
        self.variables["theta0_step"].set(position_0['theta']['step'])
        self.variables["dtheta_deg_step"].set(units['theta'])      

    def update_calibration(self):
        self.calibration['Position_0'] = {
            "x": {
                "pix": self.global_pixel_origin['x'],
                "um":  self.global_phys_origin['x']
            },
            "m": {
                "pix": self.global_pixel_origin['m'],
                "um":  self.global_phys_origin['m']
            },
            "y": {
                "step": self.global_pixel_origin['y'],
                "um":   self.global_phys_origin['y']
            },
            "theta": {
                "step": self.global_pixel_origin['theta']
            }
        }

        self.calibration['Position_1'] = {
            "x": {
                "pix": float(self.variables["x1_pix"].get()),
                "um":  float(self.variables["x1_um"].get())
            },
            "m": {
                "pix": float(self.variables["m1_pix"].get()),
                "um":  float(self.variables["m1_um"].get())
            }                       
        }

        self.calibration['Units'] = {ax: float(val) for ax, val in self.units.items()}

        # Update in experiment
        self.vast_experiment["Calibration"] = self.calibration

        # redraw fish
        self.draw_fish()

    def save_calibration(self):
        
        default_name = f"{Path(self.well).name.lower()}_calib"

        full_path = filedialog.asksaveasfilename(
            initialfile=default_name,
            initialdir=self.well,
            defaultextension=".yml",
            filetypes=[("YAML", "*.yml")]
            )

        save_yaml_file(
            file_directory=Path(full_path).parent,
            content_dict=self.calibration,
            filename=Path(full_path).name
        )

    def load_calibration(self):
        
        full_path = filedialog.askopenfile(
            initialdir=self.well,
            defaultextension=".yml",
            filetypes=[("YAML", "*.yml")]            
        ).name

        self.vast_experiment["Calibration"] = load_yaml_file(full_path)

        self.pull_calib_from_experiment()

        # redraw
        self.draw_fish()

    def parse_well(self, well):
        walk = os.walk(well)

        views = []
        for root, dirs, files in walk:
            if dirs:
                continue
            views.append(root)

        chans = {chan.split('_')[-2] for chan in files if ".tif" in chan}

        return sorted(chans), sorted(views)
