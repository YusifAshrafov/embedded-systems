import sys                      # import sys for exit                                   
import csv                      # import csv for saving in a CSV file
from datetime import datetime   # import datetime for generating real timestamps

import serial                   # import pyserial for serial communication

from PyQt6.QtCore import QTimer # import QTimer for updates periodically
from PyQt6.QtWidgets import (   # import GUI elements: application, widget and so on
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton
)

import pyqtgraph as pg          # import pyqtgraph for real-time plotting

BAUD = 9600                     # serial baud rate
THRESHOLD = 400                 # sound threshold; values above will generate alert
SAMPLES_ON_SCREEN = 200         # how many last samples we see
UPDATE_MS = 50                  # how often triggers reading
PORT = "COM13"                  # change it to the port that is used

class SoundGUI(QWidget):        # main app window class creation
    def __init__(self):         # runs when window created
        super().__init__()      # call the QWidget

        self.setWindowTitle("Sound Level Monitor (UART)") # set window title
        self.resize(900, 550)   # set initial window size

        self.ser = None         # serial objects start as none, not connected
        self.running = False    # monitoring is false

        main = QVBoxLayout(self)                 # main layout is vertical

        self.status = QLabel("Status: stopped")  # create a label "Status: stopped"
        main.addWidget(self.status)              # add label to main layout

        btn_row = QHBoxLayout()                  # horizontal row for buttons
        main.addLayout(btn_row)                  # add the button layout to main layout

        self.start_btn = QPushButton("Start")   # create a button with "Start" text
        self.stop_btn = QPushButton("Stop")     # create a button with "Stop" text
        self.stop_btn.setEnabled(False)         # disable stop at startup

        btn_row.addWidget(self.start_btn)       # add start button to row with buttons
        btn_row.addWidget(self.stop_btn)        # add stop button to row with buttons

        # PLOT SETUP
        self.plot = pg.PlotWidget()             # create the plot widget for live graph
        main.addWidget(self.plot)               # add the plot widget to the main layout

        self.plot.setTitle("Live Sound Level")      # set the title
        self.plot.setLabel("left", "Sound (0–1023)")# label y-axis as sound value
        self.plot.setLabel("bottom", "Sample #")    # label x-axis as sample number
        self.plot.showGrid(x=True, y=True)          # show grid lines on axes

        self.x = []              # list to store x-axis - sample numbers
        self.y = []              # list to store y-axis - sound readings
        self.sample_idx = 0      # count of samples received

        self.curve = self.plot.plot(self.x, self.y) # create the graph curve using x and y data

        self.threshold_line = pg.InfiniteLine(pos=THRESHOLD, angle=0)  # create horizontal line at THRESHOLD
        self.plot.addItem(self.threshold_line)      # add this line to graph

        # CSV
        self.csv_file = open("sound_threshold_log.csv", "a", newline="", encoding="utf-8") # open/create csv file in append mode (alerts will be added without deleting old data)
        self.csv_writer = csv.writer(self.csv_file) # create csv object for writing rows

        # empty = write column once
        if self.csv_file.tell() == 0:               # check if file is empty
            self.csv_writer.writerow(["timestamp", "sound_value"]) # if yes, write csv column headers

        self.timer = QTimer()                       # create timer
        self.timer.timeout.connect(self.read_serial)# when timer times out, call read_serial

        self.start_btn.clicked.connect(self.start_monitoring) # connect start button to start_monitoring
        self.stop_btn.clicked.connect(self.stop_monitoring)   # connect stop button to stop_monitoring
 

    def start_monitoring(self):             # start serial monitoring
        """Connect to Arduino serial port and start reading live data."""
        if self.running:            # if it's running
            return                  # do nothing and exit
        
        port = PORT                 # copy predefined COM port into variable

        if port is None:            # if no port is defined
            self.status.setText("Status: Arduino not found. Set PORT='COMx' in code.") # show this message
            return                  # exit the function

        # open serial port with BAUD rate
        try:
            self.ser = serial.Serial(port, BAUD, timeout=0.1)       # try to open serial port
        except Exception as e:                                      
            self.status.setText(f"Status: cannot open {port}: {e}") # show error message 
            return                                                  # exit if connection failed

        self.x.clear()                      # clear old x sample data
        self.y.clear()                      # clear old y sample data
        self.sample_idx = 0                 # reset sample counter
        self.curve.setData(self.x, self.y)  # clear graph display

        self.running = True                 # running - monitoring
        self.timer.start(UPDATE_MS)         # start the timer so it will run every UPDATE_MS ms

        self.start_btn.setEnabled(False)    # disable start button
        self.stop_btn.setEnabled(True)      # enable stop button

        self.status.setText(f"Status: running (connected {port} @ {BAUD})") # update status label to show connection


    def stop_monitoring(self):             # stop serial monitoring
        """Stop reading, stop timer, and close serial port to free COM port."""
        if not self.running:            # if it's not running          
            return                      # do nothing and exit

        self.timer.stop()               # stop timer 
        self.running = False            # stopped running - monitoring

        try:
            if self.ser is not None and self.ser.is_open: # if object exists
                self.ser.close()        # close the serial port
        except:
            pass                        # ignore errors

        self.ser = None                 # serial objects start as none, not connected

        self.start_btn.setEnabled(True) # enable start button
        self.stop_btn.setEnabled(False) # disable stop button

        self.status.setText("Status: stopped") # update status label


    def read_serial(self):             # read incoming serial data
        """
        Reads incoming serial lines from Arduino.
        Expected Arduino format: SOUND:<value>
        Updates status label, logs alerts, and updates the plot.
        """
        if not self.running or self.ser is None: # if monitoring is off or serial is not connected
            return                               # do nothing

        try:
            while self.ser.in_waiting:           # while unread data is in the buffer

                # Read one line from serial and decode bytes -> string
                line = self.ser.readline().decode(errors="ignore").strip() # read serial line, ignore errors, remove spaces

                if not line.startswith("SOUND:"):# check if the line has prefix
                    continue                     # if not, ignore it

                try:
                    value = int(line.split(":", 1)[1])  # split after ":" and convert value to integer
                except ValueError:                      
                    continue                            # if not, ignore it

                if value > THRESHOLD:                                  # ALERT condition: update csv
                    self.status.setText(f"Status: ALERT | Sound={value} (>{THRESHOLD})") # show alert in GUI

                    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # generate date and time in string
                    self.csv_writer.writerow([ts, value])              # save to csv
                    self.csv_file.flush()                              # force data to save
                else:
                    self.status.setText(f"Status: running | Sound={value} (threshold {THRESHOLD})") # if below, show normal status

                self.sample_idx += 1                        # sample number increases
                self.x.append(self.sample_idx)              # add new sample number to x list
                self.y.append(value)                        # add new sound to y list

                # Keep only SAMPLES_ON_SCREEN
                if len(self.x) > SAMPLES_ON_SCREEN:         # if there are more than allowed samples on screen
                    self.x = self.x[-SAMPLES_ON_SCREEN:]    # keep only last SAMPLES_ON_SCREEN x values
                    self.y = self.y[-SAMPLES_ON_SCREEN:]    # keep only last SAMPLES_ON_SCREEN y values

                self.curve.setData(self.x, self.y)          # update the graph with x and y

        except Exception as e:                              # if serial-reading error happens
            self.status.setText(f"Status: serial read error: {e}") # show the error
            self.stop_monitoring()                          # stop monitoring


    def closeEvent(self, event):    # call when window is closed
        self.stop_monitoring()      # stop monitoring 

        try:
            self.csv_file.close()   # close csv file
        except:
            pass                    # ignore errors

        event.accept()              # accept the event and close the window


if __name__ == "__main__":          # run if file is started directly
    app = QApplication(sys.argv)    # create PyQt app object
    w = SoundGUI()                  # create SoundGUI window
    w.show()                        # show window on screen
    sys.exit(app.exec())            # start GUI loop and exit when finished
