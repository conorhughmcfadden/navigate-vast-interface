# Standard Imports
import os
import platform
from pathlib import Path
from multiprocessing.managers import ListProxy

# Navigate specific imports
from navigate.tools.common_functions import load_module_from_file
from navigate.model.device_startup_functions import device_not_found, auto_redial, DummyDeviceConnection
from navigate.model.devices.stages.synthetic import SyntheticStage

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

    if stage_type.lower() == "vast" and platform.system() == "Windows":
        plugin_device = load_module_from_file(
            "plugin_device",
            os.path.join(Path(__file__).resolve().parent, "plugin_device.py"),
        )

        return auto_redial(
            plugin_device.build_VAST_connection,
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
    id = kwargs['id']

    device_config = configuration["configuration"]["microscopes"][microscope_name][DEVICE_TYPE_NAME]["hardware"]
    if is_synthetic:
        device_type = "synthetic"
    elif type(device_config) == ListProxy:
        device_type = device_config[id]["type"]
    else:
        device_type = device_config["type"]

    if device_type.lower() == "vast":
        plugin_device = load_module_from_file(
            "plugin_device",
            os.path.join(Path(__file__).resolve().parent, "plugin_device.py"),
        )
        return plugin_device.PluginDevice(
            microscope_name, 
            device_connection, 
            configuration,
            id
            )
    
    elif device_type == "synthetic":
        synthetic_device = load_module_from_file(
            "synthetic_device",
            os.path.join(Path(__file__).resolve().parent, "synthetic_device.py"),
        )
        return synthetic_device.SyntheticDevice(
            microscope_name, 
            device_connection, 
            configuration,
            id
            )
    
    else:
        return device_not_found(microscope_name, device_type)
