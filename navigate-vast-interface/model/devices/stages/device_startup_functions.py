# Standard Imports
import os
import platform
from pathlib import Path

from navigate.tools.common_functions import load_module_from_file
from navigate.model.device_startup_functions import device_not_found, auto_redial, DummyDeviceConnection
from navigate.model.devices.stages.stage_synthetic import SyntheticStage

DEVICE_TYPE_NAME = "stage"  # Same as in configuraion.yaml, for example "stage", "filter_wheel", "remote_focus_device"...
DEVICE_REF_LIST = ["type", "axes", "serial_number", "axes_mapping"]  # the reference value from configuration.yaml

def load_device(hardware_configuration, is_synthetic=False, **kwargs):
    """Build device connection.

    Parameters
    ----------
    hardware_configuration : dict
        device hardware configuration section
    is_synthetic : bool
        use synthetic hardware

    Returns
    -------
    device_connection : object
    """

    if is_synthetic:
        stage_type = "SyntheticStage"
    else:
        stage_type = hardware_configuration["type"]

    if stage_type == "VAST" and platform.system() == "Windows":
        from model.devices.stages.stage_vast import build_VAST_connection

        return auto_redial(
            build_VAST_connection,
            (),
            exception=Exception,
        )
    else:
        return DummyDeviceConnection

def start_device(microscope_name, device_connection, configuration, is_synthetic=False, **kwargs):
    """Start device.

    Parameters
    ----------
    microscope_name : string
        microscope name
    device_connection : object
        device connection object returned by load_device()
    configuration : dict
        navigate configuration
    is_synthetic : bool
        use synthetic hardware

    Returns
    -------
    device_object : object
    """
    if is_synthetic:
        device_type = "synthetic"
    else:
        device_type = configuration["configuration"]["microscopes"][microscope_name][
            DEVICE_TYPE_NAME
        ]["hardware"]["type"]

    if device_type == "VAST":
        plugin_device = load_module_from_file(
            "stage_vast",
            os.path.join(Path(__file__).resolve().parent, "stage_vast.py"),
        )
        return plugin_device.VASTStage(
            microscope_name, 
            device_connection, 
            configuration,
            id=kwargs['id']
            )
    
    elif device_type == "synthetic":
        return SyntheticStage(
            microscope_name,
            device_connection,
            configuration,
            id=kwargs['id']
        )
    
    else:
        return device_not_found(microscope_name, device_type)
