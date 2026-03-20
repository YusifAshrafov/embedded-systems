import sys                                    
import csv                      # save in CSV file
from datetime import datetime   # generate real timestamps

import serial

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton
)

import pyqtgraph as pg          

BAUD = 9600
THRESHOLD = 400
SAMPLES_ON_SCREEN = 200         # How many last samples we see
UPDATE_MS = 50                  # How often triggers reading
PORT = "COM13"

class SoundGUI(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Sound Level Monitor (UART)")
        self.resize(900, 550)

        self.ser = None
        self.running = False

        main = QVBoxLayout(self)                 # Main layout is vertical

        self.status = QLabel("Status: stopped")
        main.addWidget(self.status)

        btn_row = QHBoxLayout()                  # Horizontal row for buttons
        main.addLayout(btn_row)

        self.start_btn = QPushButton("Start")
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)

        btn_row.addWidget(self.start_btn)
        btn_row.addWidget(self.stop_btn) 

        # PLOT SETUP
        self.plot = pg.PlotWidget()
        main.addWidget(self.plot)

        self.plot.setTitle("Live Sound Level")
        self.plot.setLabel("left", "Sound (0–1023)")
        self.plot.setLabel("bottom", "Sample #")
        self.plot.showGrid(x=True, y=True)

        self.x = []              # x-axis 1,2,3...
        self.y = []              # y-axis sound
        self.sample_idx = 0

        self.curve = self.plot.plot(self.x, self.y)  # CURVE

        self.threshold_line = pg.InfiniteLine(pos=THRESHOLD, angle=0)  # Horizontal -> THRESHOLD
        self.plot.addItem(self.threshold_line)

        # CSV
        self.csv_file = open("sound_threshold_log.csv", "a", newline="", encoding="utf-8")
        self.csv_writer = csv.writer(self.csv_file)

        # empty = write column once
        if self.csv_file.tell() == 0:
            self.csv_writer.writerow(["timestamp", "sound_value"])

        self.timer = QTimer()
        self.timer.timeout.connect(self.read_serial)

        self.start_btn.clicked.connect(self.start_monitoring)
        self.stop_btn.clicked.connect(self.stop_monitoring)


    def start_monitoring(self):
        """Connect to Arduino serial port and start reading live data."""
        if self.running:
            return
        
        port = PORT

        if port is None:
            self.status.setText("Status: Arduino not found. Set PORT='COMx' in code.")
            return

        # open serial port with BAUD rate
        try:
            self.ser = serial.Serial(port, BAUD, timeout=0.1)
        except Exception as e:
            self.status.setText(f"Status: cannot open {port}: {e}")
            return

        self.x.clear()
        self.y.clear()
        self.sample_idx = 0
        self.curve.setData(self.x, self.y)

        self.running = True
        self.timer.start(UPDATE_MS)

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

        self.status.setText(f"Status: running (connected {port} @ {BAUD})")


    def stop_monitoring(self):
        """Stop reading, stop timer, and close serial port to free COM port."""
        if not self.running:
            return

        self.timer.stop()
        self.running = False

        try:
            if self.ser is not None and self.ser.is_open:
                self.ser.close()
        except:
            pass

        self.ser = None

        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

        self.status.setText("Status: stopped")


    def read_serial(self):
        """
        Reads incoming serial lines from Arduino.
        Expected Arduino format: SOUND:<value>
        Updates status label, logs alerts, and updates the plot.
        """
        if not self.running or self.ser is None:
            return

        try:
            while self.ser.in_waiting:

                # Read one line from serial and decode bytes -> string
                line = self.ser.readline().decode(errors="ignore").strip()

                if not line.startswith("SOUND:"):
                    continue

                try:
                    value = int(line.split(":", 1)[1])
                except ValueError:
                    continue

                if value > THRESHOLD:
                    # ALERT condition: update CSV
                    self.status.setText(f"Status: ALERT | Sound={value} (>{THRESHOLD})")

                    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    self.csv_writer.writerow([ts, value])              # Save to CSV
                    self.csv_file.flush()
                else:
                    self.status.setText(f"Status: running | Sound={value} (threshold {THRESHOLD})")

                self.sample_idx += 1
                self.x.append(self.sample_idx)
                self.y.append(value)

                # Keep only SAMPLES_ON_SCREEN
                if len(self.x) > SAMPLES_ON_SCREEN:
                    self.x = self.x[-SAMPLES_ON_SCREEN:]
                    self.y = self.y[-SAMPLES_ON_SCREEN:]

                self.curve.setData(self.x, self.y)

        except Exception as e:
            self.status.setText(f"Status: serial read error: {e}")
            self.stop_monitoring()


    def closeEvent(self, event):
        self.stop_monitoring()

        try:
            self.csv_file.close()
        except:
            pass

        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = SoundGUI()
    w.show()
    sys.exit(app.exec())
