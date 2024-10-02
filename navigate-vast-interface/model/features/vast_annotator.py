import time

class TestFeature:
    def __init__(self, model, *args):
        self.model = model

        self.config_table = {
            "signal": {
                "main": self.run
            },
        }
    
    def run(self):
        self.model.run_command("move_plugin_device", "hello!")

class VastAnnotator:
    def __init__(self, model, *args):
        self.model = model

        self.config_table = {
            "signal": {
                "main": self.signal_func
            },
            "node": {
                "need_response": False
            }
        }

    def vast_status(self):
        return self.model.configuration["experiment"]["VAST"]["VASTAnnotatorStatus"]

    def init_autostore_loc(self):
        self.autost_dir = self.model.configuration["experiment"]["VAST"]["AutostoreLocation"]

        if self.autost_dir is None:
            # from tkinter import filedialog
            # autost_dir = filedialog.askdirectory(title="Choose VAST autostore directory...")
            autost_dir = "C:\\"
            self.model.run_command("set_autostore", autost_dir)
            self.autost_dir = autost_dir
            self.model.configuration["experiment"]["VAST"]["AutostoreLocation"] = self.autost_dir

    def signal_func(self):
        # build the vast annotator popup window
        self.model.event_queue.put(
            ("build_vast_popup", [])
        )

        # need to wait for vast_interface_controller to be initialized
        while True:
            try:
                if self.vast_status():
                    break
            except:
                time.sleep(0.1)

        # wait while user selects points (finish on close)
        while self.vast_status():
            time.sleep(0.1)