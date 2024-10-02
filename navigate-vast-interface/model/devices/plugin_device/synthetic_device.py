from navigate.model.devices.stages.synthetic import SyntheticStage

class SyntheticDevice(SyntheticStage):
    def __init__(self, microscope_name, device_connection, configuration, device_id=0):
        super().__init__(microscope_name, device_connection, configuration, device_id)

    @property
    def commands(self):
        """Return commands dictionary

        Returns
        -------
        commands : dict
            commands that the device supports
        """
        return {
            "move_plugin_device": lambda *args: print(
                f"move synthetic plugin device {args[0]}!"
            )
        }