# Standard library imports
import os
from pathlib import Path
import numpy as np
import tkinter as tk
from tkinter import filedialog
from copy import deepcopy

# Third party imports
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from tifffile import tifffile
from skimage.exposure import adjust_gamma

# Local application imports
from navigate.controller.sub_controllers.gui import GUIController
from navigate.tools.file_functions import load_yaml_file

VAST_UM_PIX = 718.5/221 # Measured Cap / expt.CapWd

class VastInterfaceController(GUIController):

    def __init__(self, view, parent_controller=None):
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
        self.text = self.variables['text']

        # variables
        self.perspective = 0
        self.coord = [0, 0, 0, 0, 0] # (x,y,z,theta,f)
        self.positions = []
        self.nose_position = None
        self.x_pos = 0
        self.y_pos = 0
        self.background = None
        self.locked = False
        
        self.autost_dir = self.parent_controller.configuration['experiment']['VAST']['AutostoreLocation']

        # TODO: these are hardcoded rn... get from VastServer?
        self.channel_names = [
            "",
            "Bl-led512",
            "Yl-led615"
        ]
        self.curr_channel = 0
        self.n_views = 2
        self.gammas = [1.0] * len(self.channel_names)

        # load fish images
        self.images = []

        for v in range(self.n_views):
            new_view = {}
            for chan in self.channel_names:
                new_view[chan] = self.load_image(
                    view = self.n_views - v,
                    chan = chan
                )
            self.images += [new_view]

        self.l, self.w = self.images[0][self.channel_names[0]].shape

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

    def close(self):
        self.parent_controller.model.configuration['experiment']['VAST']['VASTAnnotatorStatus'] = False

    def update_experiment_values(self):
        self.parent_controller.model.configuration['experiment']['MultiPositions'] = self.positions
        self.parent_controller.model.configuration["experiment"]["MicroscopeState"][
            "multiposition_count"
        ] = len(self.positions)

    def load_image(self, dir="C:/Users/vastopmv3/Documents/Python/Fish/Well_A04/", chan="Yl-led615", view=1, slice=5):
        im_path = os.path.join(
            dir,
            f"test001_W_A04_0{view}_YStack",
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
        ax.imshow(
            adjust_gamma(self.images[self.perspective][chan], self.gammas[self.curr_channel]),
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
            ax.set_ylabel("Z [mm]")
        else:
            ax.set_ylabel("Y [mm]")

        # fix xy limits
        ax.set_xlim(0, self.w)
        ax.set_ylim(0, self.l)

        # display selected points
        if self.nose_position is not None:
            ax.scatter(self.nose_position[0], self.nose_position[2-self.perspective], marker='x', color=[0,0,1])
        if len(self.positions) > 0:
            c = np.array(self.positions)
            ax.scatter(c[:,0], c[:,2-self.perspective], marker='+', color=[0,1,0])

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
        if self.nose_position:
            tstr += self.coord2str(self.nose_position)
            p0 = self.nose_position[:3]
            tstr += "current: "
        
        try:
            if self.perspective == 0:
                pos = np.asarray([self.x_pos, np.nan, self.y_pos])
            else:
                pos = np.asarray([self.coord[0], self.y_pos, self.coord[2]])
            tstr += self.coord2str(pos - p0)     
        except TypeError:
            pass

        self.text.set(tstr)

    def move_crosshair(self, event):
        if not self.locked:
            # create the new data    
            if self.perspective == 0:
                self.x_pos = event.xdata
            self.y_pos = event.ydata
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
            relative_positions = [(np.array(p) - np.array(self.nose_position)).tolist() for p in self.positions]
            relative_positions = np.array(relative_positions) * VAST_UM_PIX
            self.update_multiposition_controller(relative_positions)
        else:
            self.nose_position = new_position

    def key_press(self, event):
        for c, _ in enumerate(self.channel_names):
            if int(event.key) == (c+1):
                self.curr_channel = c
                self.draw_fish()

    def mouse_wheel(self, event):
        self.gammas[self.curr_channel] += event.step * 0.02
        self.gammas[self.curr_channel] = np.clip(self.gammas[self.curr_channel], 0.02, 1.0)
        self.draw_fish()

    def on_click(self, event):
        if event.button == 1:
            if not self.locked:          
                if self.perspective == 0:
                    self.coord[0] = self.x_pos # x
                    self.coord[2] = self.y_pos # z
                    self.perspective = 1
                elif self.perspective == 1:
                    self.coord[1] = self.y_pos # y
                    self.update_positions()
                    self.perspective = 0
        elif event.button == 3:
            if self.perspective < self.n_views-1:
                self.perspective += 1
            else:
                self.perspective = 0
            
            self.locked = self.perspective > 0

        self.draw_fish()

    def update_multiposition_controller(self, positions=[[]]):
        self.parent_controller.multiposition_tab_controller.set_positions(positions)
        self.update_experiment_values()

    def build_vast_popup(self, event):
        print(f"Event = {event}")
        try:
            self.parent_controller.plugin_controller.popup_funcs[self.plugin_name]()
        except Exception as e:
            print(e)

    @property
    def custom_events(self):
        """Custom events for the controller"""
        return {
            "build_vast_popup": self.build_vast_popup,
            "close": self.close
        }