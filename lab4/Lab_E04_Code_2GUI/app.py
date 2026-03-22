import sys, time                # import sys for exit, and time for timing function
from collections import deque   # import deque for fixed-size data storage

import serial                   # import pyserial for serial communication
from PyQt6.QtCore import QTimer # import QTimer for updates periodically
from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QPushButton, QHBoxLayout, QVBoxLayout # import GUI elements: application, widget and so on
import pyqtgraph as pg          # import pyqtgraph for real-time plotting


COM_PORT = "COM7"    # change it to port that is used
BAUD = 9600          # serial baud rate
WINDOW_S = 5         # show last N seconds in the time graph
MAX_POINTS = 400     # store 400 points in graph buffer


class Main(QWidget):        # main app window class creation
    def __init__(self):     # runs when window created
        super().__init__()  # call the QWidget
        self.setWindowTitle("Joystick (Minimal + Start/Stop)") # set window title

        self.btn = QPushButton("Start")             # create a button with "Start" text
        self.btn.clicked.connect(self.toggle)       # add toggle logic, when its pressed

        self.lbl_status = QLabel("● DISCONNECTED")                        # create a label "DISCONNECTED"
        self.lbl_status.setStyleSheet("font-weight:bold; color:#aa0000;") # make it bold and red

        self.lbl = QLabel("Waiting data...")        # create a label "Waiting data...", used to show current joystick data
        self.lbl.setStyleSheet("font-size:16px;")   # make it larger

        self.lbl_rate = QLabel("Sample rate: 0.0 Hz") # create a label current sample rate

        top = QHBoxLayout()             # create a horizontal layout for top controls
        top.addWidget(self.btn)         # add start/stop button to the top
        top.addWidget(self.lbl_status)  # add the connection status label
        top.addStretch(1)               # empty space gap
        top.addWidget(self.lbl_rate)    # add the sample rate label on the right

        self.xy = pg.PlotWidget(title="Joystick (dx,dy)")   # create a scatter plot widget
        self.xy.setLabel("bottom", "dx")                    # label x-axis as dx
        self.xy.setLabel("left", "dy")                      # label y-axis as dy
        self.xy.setXRange(-600, 600)                        # set x-axis range
        self.xy.setYRange(-600, 600)                        # set y-axis range
        self.xy.showGrid(x=True, y=True)                    # show grid lines on axes
        self.xy.addLine(x=0); self.xy.addLine(y=0)          # draw center reference lines at x = 0 and y = 0
        self.dot = pg.ScatterPlotItem([0], [0], size=14)    # create a scatter point at (0, 0)
        self.xy.addItem(self.dot)                           # add the dot to the plot

        self.g = pg.PlotWidget(title="LR & UD (live)")      # create a line graph widget 
        self.g.setLabel("bottom", "Time (s)")               # label x-axis as time in sec
        self.g.setLabel("left", "ADC")                      # label y-axis as ADC value
        self.g.setYRange(0, 1023)                           # set ADC range 0-1023
        self.g.showGrid(x=True, y=True)                     # show grid lines on axes
        self.lr_curve = self.g.plot([], [])                 # create a curve for LR
        self.ud_curve = self.g.plot([], [])                 # create a curve for UD

        # Control position and resizing automatically
        lay = QVBoxLayout()         # Creates a vertical layout
        lay.addLayout(top)          # add top control layout
        lay.addWidget(self.lbl)     # add data label
        lay.addWidget(self.xy, 1)   # add scatter plot
        lay.addWidget(self.g, 1)    # add line graph
        self.setLayout(lay)         # set the vertical layout as window layout

        # Start state
        self.running = False        # data collection is false
        self.ser = None             # serial objects start as none, not connected
        self.rx = b""               # buffer for data is empty

        # Data for plots
        self.t0 = None                      # store the time when data collection started
        self.t = deque(maxlen=MAX_POINTS)   # buffer for time 
        self.lr = deque(maxlen=MAX_POINTS)  # buffer for LR
        self.ud = deque(maxlen=MAX_POINTS)  # buffer for UD

        # Sample rate
        self.sample_count = 0       # total samples received
        self.last_rate_time = 0.0   # time when last updated
        self.last_rate_count = 0    # samples at last update

        # Reads when running
        self.timer = QTimer()                   # create timer
        self.timer.setInterval(20)              # set interval 20 ms for timer
        self.timer.timeout.connect(self.tick)   # timeout calls tick
        self.timer.start()                      # start the timer

    def start(self):        # to start serial communication and data transfer
        # Open serial
        self.ser = serial.Serial(COM_PORT, BAUD, timeout=0)     # open serial port with settings
        self.ser.setDTR(False)                                  # disable Data Terminal Ready signal - reduce reset issues
        time.sleep(0.2)                                         # wait for port stabilization
        self.ser.reset_input_buffer()                           # clear old serial data from buffer

        # Reset buffers/timing
        self.rx = b""                                       # clear rx = receive buffer
        self.t.clear(); self.lr.clear(); self.ud.clear()    # clear all plot data
        self.t0 = time.time()                               # save current time as start reference

        self.sample_count = 0                               # reset total sample counter
        self.last_rate_time = self.t0                       # assign last rate update time to start time
        self.last_rate_count = 0                            # reset previous sample count
        self.lbl_rate.setText("Sample rate: 0.0 Hz")        # reset sample rate label

        self.running = True                                 # set system as running 
        self.btn.setText("Stop")                            # change button text
        self.lbl_status.setText("● CONNECTED")              # change status text
        self.lbl_status.setStyleSheet("font-weight:bold; color:#00aa00;") # change status label to green

    def stop(self):        # to stop data transfer and close serial communication                
        self.running = False                                # set system as stopped
        self.btn.setText("Start")                           # change button text
        self.lbl_status.setText("● DISCONNECTED")           # change status text
        self.lbl_status.setStyleSheet("font-weight:bold; color:#aa0000;") # change status label to red
        if self.ser:                                        # if serial port exists
            try:
                self.ser.close()                            # close the serial connection
            except:
                pass                                        # ignore error while closing
        self.ser = None                                     # remove serial connection

    def toggle(self):         # button when pressed to start or stop
        try:
            if not self.running:                            # if program stopped
                self.start()                                # then start serial read
            else:                                           # if program is running
                self.stop()                                 # then stop serial read
        except Exception as e:                              # if error happens 
            self.stop()                                     # stop 
            self.lbl.setText(f"ERROR: {e}")                 # show error message

    def handle_line(self, s: str): # to get one line as completed text
        parts = s.split(",")                                # split lines by commas
        if len(parts) != 5:                                 # check if count is 5 or not
            return                                          # if it's less or more, then ignore it
        try:
            lr = int(parts[0]); ud = int(parts[1])          # LR and UD assign to integers
            dx = int(parts[2]); dy = int(parts[3])          # dx and dy assign to integers
            direction = parts[4].strip()                    # get the text of direction and remove spaces
        except:                                             
            return                                          # if smth fails, then ignore it 

        # label + dot
        self.lbl.setText(f"{direction}   LR:{lr}  UD:{ud}   dx:{dx} dy:{dy}") # show direction, lr, ud, dx and dy in text 
        dx = max(-600, min(600, dx))                        # limit dx for safety
        dy = max(-600, min(600, dy))                        # limit dy for safety
        self.dot.setData([dx], [dy])                        # move the dot to new position

        # plot
        now = time.time()                                   # get current time
        tt = now - self.t0                                  # get elapsed time since start
        self.t.append(tt); self.lr.append(lr); self.ud.append(ud) # store them in buffers
        t_list = list(self.t)                               # convert time to list for plotting
        # Redraw curves
        self.lr_curve.setData(t_list, list(self.lr))        # update LR line graph
        self.ud_curve.setData(t_list, list(self.ud))        # update UD line graph
        if tt > WINDOW_S:                                   # only last N=5 sec
            self.g.setXRange(tt - WINDOW_S, tt)             # show only last 5 sec window on x side

        # sample rate update every 0.5 s
        self.sample_count += 1                              # increase sample count
        if (now - self.last_rate_time) >= 0.5:              # update rate each 0.5 sec
            dt = now - self.last_rate_time                  # calculate time passed since last update
            dn = self.sample_count - self.last_rate_count   # calculate new samples count since last update
            hz = dn / dt if dt > 0 else 0.0                 # dt = time passed, dn = number of samples received in that time; calculate hz
            self.lbl_rate.setText(f"Sample rate: {hz:.1f} Hz") # show rate with 1 decimal place
            self.last_rate_time = now                       # save current time as last rate update time
            self.last_rate_count = self.sample_count        # save current sample count as reference

    def tick(self):                                         # called by timer each 20 ms
        if not self.running or not self.ser:                # if not running
            return                                          # ignore it
        try:
            chunk = self.ser.read(self.ser.in_waiting or 1) # read available serial bytes
            if chunk:                                       # if some were received
                self.rx += chunk                            # add to the receive buffer
            while b"\n" in self.rx:                         # while one complete line is present
                raw, self.rx = self.rx.split(b"\n", 1)      # split one line from remaining
                self.handle_line(raw.decode(errors="ignore").strip()) # process line and decode to text
        except Exception as e:                              # if serial fails
            self.lbl.setText(f"Serial read error: {e}")     # show error
            self.stop()                                     # stop connection

    def closeEvent(self, e):        # call when window is closed
        self.stop()                 # stop serial communication
        e.accept()                  # accept the event and close the window


if __name__ == "__main__":          # run if file is started directly
    app = QApplication(sys.argv)    # create PyQt app object
    w = Main()                      # create the main window
    w.resize(900, 600)              # set window size
    w.show()                        # show window on screen
    sys.exit(app.exec())            # start GUI loop and exit when finished
