import time
import struct
import subprocess

class VASTController:
    
    # 1 um = 21333.33 microsteps
    # 1 step = 0.72 degrees
    UM_TO_US = 21.33333
    DEG_TO_US = 1 / 0.72

    def __init__(
            self,
            holster = "c:\\Users\\vastopmv3\\Documents\\NET\\Projects\\VastNavigateServer\\bin\\Debug\\VastNavigateServer.exe",
        ):
        self.holster = holster
        self.f = None
        self.wait_until_done = False

        # Establish pipe connection to VAST server
        self.connect()

        # Establish coordinate system and position variables
        self.update_xy_position_from_vast()
        self.theta_pos = 0.0

    def __del__(self):
        self.close()
        # self.vast_process.kill() # Maybe don't just rudely kill the process... Is there a VAST.shutdown()?

    def close(self):
        self.f.close()
        
    def connect(self):
        connect_init = False

        print("Beginning VAST connection...")

        while not connect_init:
            try:
                self.f = open(r'\\.\pipe\VastServerPipe', 'r+b', 0)
                connect_init = True
            except:
                time.sleep(1)
                print("Waiting for connection...")
            
        print("Connection established!")

    def get_current_position(self):
        self.update_xy_position_from_vast()

        return (
            self.x_pos,
            self.y_pos,
            self.theta_pos
        )

    def get_abs_position_um(self):
        pos_str = self.send("get_xy_pos")
        x_str, y_str = pos_str.split(",")
        
        return float(x_str), float(y_str)

    def update_xy_position_from_vast(self):
        self.x_pos, self.y_pos = self.get_abs_position_um()

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

    def get_last_autostore_location(self):
        return self.send("get_autost")

    def set_autostore_location(self, autost_dir):
        self.send(f"set_autost,{autost_dir}")

    def start_vast(self):
        self.send("boot")

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
            f"mrel,0,{x},{y}"
        )
    
    def move_abs(self, x, y):
        self.send(
            f"mabs,0,{x},{y}"
        )

    def move_rel_um(self, x_um, y_um):
        self.x_pos += x_um
        self.y_pos += y_um

        self.move_rel(
            int(x_um * VASTController.UM_TO_US), 
            int(y_um * VASTController.UM_TO_US)
        )

        if self.wait_until_done:
            self.wait()
    
    def move_abs_um(self, x_um, y_um):
        self.x_pos = x_um
        self.y_pos = y_um
        
        self.move_abs(
            int(x_um * VASTController.UM_TO_US), 
            int(y_um * VASTController.UM_TO_US)
        )

        if self.wait_until_done:
            self.wait()

    # TODO: implement...
    def continue_operation(self):
        self.send("cont")

    def wait(self):
        busy_status = 1 # anything but zero
        itr = 0
        while busy_status:
            busy_status = self.check_motors_busy_status()
            print(f"Waiting {itr}:\t{busy_status}")
            itr += 1
            time.sleep(0.01)

    def check_motors_busy_status(self):
        return int(self.send("busy"))

    def move_to_specified_position(self, x_pos=0.0, y_pos=0.0, theta_pos=0.0):

        self.move_rel_um(
            x_um=(x_pos - self.x_pos),
            y_um=(y_pos - self.y_pos)
        )

        # If there is a theta move, do an "absolute" capillary rotation
        if theta_pos != self.theta_pos:
            self.rotate_deg(theta=(theta_pos - self.theta_pos))
        