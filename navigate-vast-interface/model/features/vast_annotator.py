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
        }

    def vast_status(self):
        return self.model.configuration["experiment"]["VAST"]["VASTAnnotatorStatus"]

    # def init_autostore_loc(self):
    #     self.autost_dir = self.model.configuration["experiment"]["VAST"]["AutostoreLocation"]

    #     if self.autost_dir is None:
    #         # from tkinter import filedialog
    #         # autost_dir = filedialog.askdirectory(title="Choose VAST autostore directory...")
    #         autost_dir = "C:\\"
    #         self.model.run_command("set_autostore", autost_dir)
    #         self.autost_dir = autost_dir
    #         self.model.configuration["experiment"]["VAST"]["AutostoreLocation"] = self.autost_dir

    def signal_func(self):
        
        print('Pausing data thread...')
        self.model.pause_data_thread()
        
        # build the vast annotator popup window
        self.model.event_queue.put(
            ("build_vast_popup", [])
        )

        # need to wait for vast_interface_controller to be initialized
        while True:
            try:
                vast_status = self.vast_status()
                print(f"VAST Annotator status = {vast_status}")
                if vast_status:
                    print('Initiated!')
                    break
            except:
                pass
            
            time.sleep(1)

        # wait while user selects points (finish on close)
        while self.vast_status():
            print('Waiting for user selected points...')
            time.sleep(1)
        
        print('Resuming data thread...')
        self.model.resume_data_thread()

        # return True
        