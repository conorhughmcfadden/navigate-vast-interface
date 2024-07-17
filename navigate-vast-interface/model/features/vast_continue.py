class VastAnnotator:
    def __init__(self, model, *args):
        self.model = model

        self.config_table = {
            "signal": {
                "main": self.in_func_signal
            }
            }


    def in_func_signal(self):
        """Sends the VAST to run the 'ContinueOperation' command."""
        #self.model.vast_controller.continue_operation()
        pass
