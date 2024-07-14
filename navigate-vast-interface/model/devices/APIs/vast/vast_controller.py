import time
import struct
import subprocess

class VASTController:
    
    # 1 um = 21333.33 microsteps
    # 1 step = 0.72 degrees
    UM_TO_US = 21.33333
    DEG_TO_US = 1 / 0.72

    def __init__(self):
        self.holster = "C:\\Users\\mesoO\\Documents\\TestAutoSampIntegration\\bin\\Debug\\TestAutoSampIntegration.exe"
        self.f = None
        self.vast_process = subprocess.Popen(self.holster)

        # Stage starts at (x,y) = home when you boot up the VAST by default
        # It would be nice to query the stage directly, but not sure if this can be done...
        self.x_pos = 0
        self.y_pos = 0
        # Infinity motor, so abs theta pos is arbitrary!
        self.theta_pos = 0
        # NOTE: Keep positions in [um] and convert to uS under the hood!

        self.wait_until_done = False # Maybe implement this later...

        self.connect()

    def __del__(self):
        self.close()
        self.vast_process.kill() # Maybe don't just rudely kill the process... Is there a VAST.shutdown()?

    def close(self):
        self.f.close()
        
    def connect(self):
        connect_init = False

        print("Beginning VAST connection...")

        # NOTE: Pipe will fail due to win32 File not found error if the DebugView is not open!
        
        while not connect_init:
            try:
                self.f = open(r'\\.\pipe\VASTInteropPipe', 'r+b', 0)
                connect_init = True
            except:
                time.sleep(1)
            
            print("Waiting for connection..." if not connect_init else "Connection established!")

    def get_current_position(self):
        return (
            self.x_pos,
            self.y_pos,
            self.theta_pos
        )

    def send(self, s):
        # Write to pipe
        self.f.write(struct.pack('I', len(s)) + s.encode(encoding="ascii"))   # Write str length and str
        self.f.seek(0)                               # EDIT: This is also necessary
        
        # read from pipe
        n = struct.unpack('I', self.f.read(4))[0]    # Read str length
        s = self.f.read(n)                           # Read str
        self.f.seek(0)                               # Important!!!
        
        # output data, if any
        out_str = s.decode()
        if out_str:
            return out_str

    def start_vast(self):
        self.send('boot')

    def rotate(self, steps):
        self.send(
            f"rot,{steps}"
        )

    def rotate_deg(self, theta):
        self.theta_pos += theta # All rotation moves are relative...
        
        self.rotate(int(theta * VASTController.DEG_TO_US))

        if self.wait_until_done:
            self.wait()

    def move_rel(self, x, y):
        self.send(
            f"mrel,{x},{y}"
        )
    
    def move_abs(self, x, y):
        self.send(
            f"mabs,{x},{y}"
        )

    def move_rel_um(self, x_um, y_um):
        self.x_pos += x_um
        self.y_pos += y_um

        self.move_rel(
            int(x_um * VASTController.UM_TO_US), 
            int(y_um * VASTController.UM_TO_US)
        )

        # include in the relevant moves, maybe include in all later
        if self.wait_until_done:
            self.wait()
    
    def move_abs_um(self, x_um, y_um):
        self.x_pos = x_um
        self.y_pos = y_um
        
        self.move_abs(
            int(x_um * VASTController.UM_TO_US), 
            int(y_um * VASTController.UM_TO_US)
        )
    
    def wait(self):
        busy_status = 1 # anything but zero
        itr = 0
        while busy_status:
            busy_status = self.check_motors_busy_status()
            # print(f"Waiting {itr}:\t{busy_status}")
            time.sleep(0.01)

    def check_motors_busy_status(self):
        busy_str = self.send("busy")
        return int(busy_str.split(',')[-1])

    def move_to_specified_position(self, x_pos=0.0, y_pos=0.0, theta_pos=0.0):

        print("\nvast_controller/move_to_specified_position: BEGIN")
        print(f"\ttheta_pos = {(theta_pos)}")
        print(f"\tself.theta_pos = {(self.theta_pos)}")
        print(f"\t(theta_pos - self.theta_pos) = {(theta_pos - self.theta_pos)}")

        print("\n---- SEND MOVE COMMAND ----")
        # Move the stage first
        # self.move_abs_um(x_um=x_pos, y_um=y_pos)
        # Perform relative move in (x,y). Seems to work better for the x-axis.
        self.move_rel_um(
            x_um=(x_pos - self.x_pos),
            y_um=(y_pos - self.y_pos)
        )

        # If there is a theta move, do an "absolute" capillary rotation
        if theta_pos != self.theta_pos:
            self.rotate_deg(theta=(theta_pos - self.theta_pos))

        print("\nvast_controller/move_to_specified_position: END")
        print(f"\ttheta_pos = {(theta_pos)}")
        print(f"\tself.theta_pos = {(self.theta_pos)}")
        print(f"\t(theta_pos - self.theta_pos) = {(theta_pos - self.theta_pos)}")
        