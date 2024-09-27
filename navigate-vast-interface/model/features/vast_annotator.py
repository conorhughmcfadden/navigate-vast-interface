import time

class VastAnnotator:
    def __init__(self, model, *args):
        self.model = model

        self.config_table = {
            "signal": {
                "main": self.signal_func,
            },
            "node": {
                "need_response": False
            }
        }

    def vast_status(self):
        return self.model.configuration["experiment"]["VASTAnnotatorStatus"]

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
