# Copyright (c) 2021-2022  The University of Texas Southwestern Medical Center.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted for academic and research use only (subject to the
# limitations in the disclaimer below) provided that the following conditions are met:
#
#      * Redistributions of source code must retain the above copyright notice,
#      this list of conditions and the following disclaimer.
#
#      * Redistributions in binary form must reproduce the above copyright
#      notice, this list of conditions and the following disclaimer in the
#      documentation and/or other materials provided with the distribution.
#
#      * Neither the name of the copyright holders nor the names of its
#      contributors may be used to endorse or promote products derived from this
#      software without specific prior written permission.
#
# NO EXPRESS OR IMPLIED LICENSES TO ANY PARTY'S PATENT RIGHTS ARE GRANTED BY
# THIS LICENSE. THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND
# CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A
# PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR
# BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER
# IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

# Standard Imports
import os
import pathlib
import logging
import time

# Third Party Imports

# Navigate Imports
from navigate.model.devices.stages.stage_base import StageBase
from navigate.tools.common_functions import load_module_from_file

# Logger Setup
# p = __name__.split(".")[1]
# logger = logging.getLogger(p)
"""
    Not sure how to handle logger in a plugin...
"""

def build_VAST_connection() -> object:
    """Connect to the ASI Stage

    Parameters
    ----------
    com_port : str
        Communication port for ASI Tiger Controller - e.g., COM1
    baud_rate : int
        Baud rate for ASI Tiger Controller - e.g., 9600

    Returns
    -------
    asi_stage : object
        Successfully initialized stage object.
    """

    # Need to load the VAST API using load_module_from_file...
    vast_api = load_module_from_file(
        'vast_controller',
        os.path.join(
            pathlib.Path(__file__).resolve().parent.parent,
            'APIs',
            'vast',
            'vast_controller.py'
        )
    )

    # load the VAST connection through the pipe
    vast_controller = vast_api.VASTController()
    vast_controller.start_vast()

    # n_iters = 45
    # for i in range(n_iters):
    #     print(f"stage_vast: waiting for VAST software to boot... {i}/{n_iters}")
    #     time.sleep(1)

    return vast_controller


class VASTStage(StageBase):
    """VAST BioImager Stage Control

    Based of the tage class for now...
    """

    def __init__(self, microscope_name, device_connection, configuration, device_id=0):
        """Initialize the ASI Stage connection.

        Parameters
        ----------
        microscope_name : str
            Name of microscope in configuration
        device_connection : object
            Hardware device to connect to
        configuration : multiprocessing.managers.DictProxy
            Global configuration of the microscope
        """
        super().__init__(microscope_name, device_connection, configuration, device_id)

        # Default axes mapping
        axes_mapping = {"x": "x", "y": "y", "theta": "theta"}
        if not self.axes_mapping:
            self.axes_mapping = {
                axis: axes_mapping[axis] for axis in self.axes if axis in axes_mapping
            }

        self.vast_axes = dict(map(lambda v: (v[1], v[0]), self.axes_mapping.items()))

        # Set the VAST stage as the device_connection
        self.stage = device_connection

        # Define the stage positions (there is no Z!)
        self.stage_x_pos = None
        self.stage_y_pos = None
        self.stage_theta_pos = None

        self.report_position()

    def __del__(self):
        """Delete tage Serial Port.



        Raises
        ------
        UserWarning
            Error while closing the tage Serial Port.
        """
        self.close()

    def report_position(self):
        """Reports the position for all axes, and creates a position dictionary.

        Positions from the VAST are converted to microns.

        Returns
        -------
        position : dict
            Dictionary containing the position of all axes
        """
        position = {}
        try:
            (
                self.stage_x_pos,
                self.stage_y_pos,
                self.stage_theta_pos,
            ) = self.stage.get_current_position()
            for axis, hardware_axis in self.axes_mapping.items():
                hardware_position = getattr(self, f"stage_{hardware_axis}_pos")
                self.__setattr__(f"{axis}_pos", hardware_position)

            position = self.get_position_dict()
            # logger.debug(f"VAST - Position: {position}")
        except Exception as e:
            print(f"VAST: Failed to report position: {e}")
            # logger.debug(f"VAST - Error: {e}")
            time.sleep(0.01)

        return position

    def move_axis_absolute(self, axis, abs_pos, wait_until_done=False):
        """Implement movement logic along a single axis.

        Parameters
        ----------
        axis : str
            An axis. For example, 'x', 'y', 'z', 'f', 'theta'.
        abs_pos : float
            Absolute position value
        wait_until_done : bool
            Block until stage has moved to its new spot.

        Returns
        -------
        bool
            Was the move successful?
        """
        move_dictionary = {f"{axis}_abs": abs_pos}
        return self.move_absolute(move_dictionary, wait_until_done)

    def move_absolute(self, move_dictionary, wait_until_done=True):
        """Move stage along a single axis.

        Parameters
        ----------
        move_dictionary : dict
            A dictionary of values required for movement. Includes 'x_abs', 'x_min',
            etc. for one or more axes. Expects values in micrometers, except for theta,
            which is in degrees.
        wait_until_done : bool
            Wait until the stage has finished moving before returning.

        Returns
        -------
        bool
            Was the move successful?
        """
        print("\nvast_stage/move_absolute: BEGIN")

        pos_dict = self.verify_abs_position(move_dictionary)
        if not pos_dict:
            return False

        print(f"\tpos_dict = {pos_dict}")

        # rely on cached positions
        # if len(pos_dict.keys()) < 3:
        #     self.report_position()
        self.stage.wait_until_done = wait_until_done # This does nothing...

        move_stage = {}
        for axis in pos_dict:
            if (
                abs(
                    getattr(self, f"stage_{self.axes_mapping[axis]}_pos")
                    - pos_dict[axis]
                )
                < 0.02
            ):
                move_stage[axis] = False
            else:
                move_stage[axis] = True
                print(f"\tmove_stage[{axis}] = {move_stage[axis]}")
                setattr(self, f"stage_{self.axes_mapping[axis]}_pos", pos_dict[axis])

        print(f"\tself.stage_x_pos = {self.stage_x_pos}")
        print(f"\tself.stage_y_pos = {self.stage_y_pos}")
        print(f"\tself.stage_theta_pos = {self.stage_theta_pos}")

        move_stage = any(move_stage.values())
        if move_stage is True:
            try:
                self.stage.move_to_specified_position(
                    x_pos=self.stage_x_pos,
                    y_pos=self.stage_y_pos,
                    theta_pos=self.stage_theta_pos,
                )
            except Exception as e:
                # logger.debug(f"VAST: move_axis_absolute failed - {e}")
                # make sure the cached positions are the "same" as device
                self.report_position()
                return False

        return True

    def stop(self):
        """Stop all stage movement abruptly."""
        # try:
        #     self.stage.interrupt_move()
        # except Exception as error:
        #     # logger.exception(f"VAST - Stage stop failed: {error}")
        pass
        # May not be able to do this with VAST..?

    def close(self):
        """Close the stage."""

        try:
            self.stop()
            self.stage.close()
            # logger.debug("VAST stage connection closed")
        except (AttributeError, BaseException) as e:
            print("Error while closing the VAST stage connection", e)
            # logger.debug("Error while disconnecting the VAST stage", e)
