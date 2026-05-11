import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import serial
import serial.tools.list_ports
import threading
import queue
from datetime import datetime

# SQLite database file 
DB_NAME = "rfid_tags.db"                         # database file name where RFID tags will be saved
BAUD_RATE = 9600                                 # serial baud rate, same as Arduino Serial.begin(9600)

# id          -> automatic unique ID
# uid         -> RFID card UID
# scan_count  -> how many times card was scanned
# first_seen  -> first scan time
# last_seen   -> latest scan time


class RFIDDatabase:                              # class for working with SQLite database
    def __init__(self, db_name):                 # runs when database object is created
        self.conn = sqlite3.connect(db_name)     # if the file does not exist, Python creates it
        self.create_table()                      # create the table if it does not already exist

    def create_table(self):                      # creates the database table
        cursor = self.conn.cursor()              # cursor is used to run SQL commands

        # creates a table named tags only if it does not already exist
        cursor.execute("""  
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uid TEXT UNIQUE NOT NULL,
                scan_count INTEGER NOT NULL DEFAULT 1,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL
            )
        """)

        # creates unique ID for every tag automatically
        # stores RFID UID -> unique
        # stores how many times the tag was scanned
        # stores first scan time
        # stores latest scan time    

        self.conn.commit()                       # save changes

    # this function receives RFID UID from Arduino
    def add_or_update_tag(self, uid):            # add new RFID tag or update existing one
        cursor = self.conn.cursor()              # create cursor for SQL commands
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S") # gets current date and time

        # check if UID already exsitsts
        cursor.execute("SELECT id, scan_count FROM tags WHERE uid = ?", (uid,)) # search tag by UID
        row = cursor.fetchone()                    # gets one result

        if row:                                    # if UID already exists in database
            tag_id, count = row                    # get tag ID and old scan count
            new_count = count + 1                  # increase scan count by 1

            cursor.execute("""
                UPDATE tags
                SET scan_count = ?, last_seen = ?
                WHERE uid = ?
            """, (new_count, now, uid))            # update scan count and last seen time

            # updates existing tag:
            # scan_count increases
            # last_seen becomes current time

            self.conn.commit()                     # save updated data
            return tag_id, new_count, False        # false = not new tag

        else:                                      # if UID is new
            cursor.execute("""
                INSERT INTO tags (uid, scan_count, first_seen, last_seen)
                VALUES (?, ?, ?, ?)
            """, (uid, 1, now, now))               # insert new tag into database

            # for a new tag:
            # scan_count = 1
            # first_seen = now
            # last_seen = now

            self.conn.commit()                     # saves new row
            tag_id = cursor.lastrowid              # gets the automatically created unique ID
            return tag_id, 1, True                 # true = new tag

    def get_all_tags(self):                        # get all RFID tags from database
        cursor = self.conn.cursor()                # create cursor for SQL command

        cursor.execute("""
            SELECT id, uid, scan_count, first_seen, last_seen
            FROM tags
            ORDER BY id ASC
        """)                                       # select all recods and orders by ID

        return cursor.fetchall()                   # return all rows from database

    def close(self):                               # close database connection
        self.conn.close()                          # close SQLite database


class RFIDApp:                                     # main GUI app class
    def __init__(self, root):                      # runs when GUI object is created
        self.root = root                           # store main tkinter window
        self.root.title("RFID Security System Database") # set window title
        self.root.geometry("900x550")              # set window size

        self.db = RFIDDatabase(DB_NAME)            # create database object

        self.serial_port = None                    # serial port object starts as None
        self.running = False                       # stores reading state; false = not reading
        self.serial_thread = None                  # thread object for serial reading
        self.data_queue = queue.Queue()            # queue for sending serial data to GUI safely

        self.create_widgets()                      # create all GUI elements
        self.refresh_ports()                       # load available COM ports
        self.refresh_table()                       # load database data into table

        self.root.after(100, self.process_serial_data) # check serial data every 100 ms

    def create_widgets(self):                      # create GUI widgets
        # top frame
        top_frame = ttk.LabelFrame(self.root, text="Serial Connection") # create serial connection frame
        top_frame.pack(fill="x", padx=10, pady=10) # place frame at the top

        ttk.Label(top_frame, text="Port:").pack(side="left", padx=5) # create label for COM port

        self.port_box = ttk.Combobox(top_frame, width=20, state="readonly") # create dropdown for COM ports
        self.port_box.pack(side="left", padx=5)     # place COM port dropdown

        self.refresh_button = ttk.Button(
            top_frame,
            text="Refresh Ports",
            command=self.refresh_ports
        )                                           # create button to refresh COM port list
        self.refresh_button.pack(side="left", padx=5) # place refresh button

        self.connect_button = ttk.Button(
            top_frame,
            text="Connect",
            command=self.connect_serial
        )                                           # create button to connect serial port
        self.connect_button.pack(side="left", padx=5) # place connect button

        self.disconnect_button = ttk.Button(
            top_frame,
            text="Disconnect",
            command=self.disconnect_serial,
            state="disabled"
        )                                           # create disconnect button, disabled at start
        self.disconnect_button.pack(side="left", padx=5) # place disconnect button

        self.status_label = ttk.Label(top_frame, text="Status: Disconnected") # create status label
        self.status_label.pack(side="left", padx=20) # place status label

        # table frame
        table_frame = ttk.LabelFrame(self.root, text="RFID Tag Database") # create table frame
        table_frame.pack(fill="both", expand=True, padx=10, pady=10) # place table frame

        # defines table columns
        columns = ("id", "uid", "scan_count", "first_seen", "last_seen") # define table column names

        # creates table widget
        self.tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            height=12
        )                                           # create table widget for RFID records

        # sets column titles
        self.tree.heading("id", text="Unique ID")   # set title for id column
        self.tree.heading("uid", text="RFID UID")   # set title for uid column
        self.tree.heading("scan_count", text="Scan Count") # set title for scan count column
        self.tree.heading("first_seen", text="First Seen") # set title for first seen column
        self.tree.heading("last_seen", text="Last Seen")   # set title for last seen column

        self.tree.column("id", width=80, anchor="center") # set id column width and center text
        self.tree.column("uid", width=180, anchor="center") # set uid column width and center text
        self.tree.column("scan_count", width=100, anchor="center") # set scan count column width and center text
        self.tree.column("first_seen", width=180, anchor="center") # set first seen column width and center text
        self.tree.column("last_seen", width=180, anchor="center")  # set last seen column width and center text

        scrollbar = ttk.Scrollbar(
            table_frame,
            orient="vertical",
            command=self.tree.yview
        )                                           # create vertical scrollbar for table

        self.tree.configure(yscrollcommand=scrollbar.set) # connect table scrolling with scrollbar

        self.tree.pack(side="left", fill="both", expand=True) # place table on left side
        scrollbar.pack(side="right", fill="y")      # place scrollbar on right side

        # refresh table button frame
        button_frame = ttk.Frame(self.root)          # create frame for refresh table button
        button_frame.pack(fill="x", padx=10, pady=5) # place button frame

        self.refresh_table_button = ttk.Button(
            button_frame,
            text="Refresh Table",
            command=self.refresh_table
        )                                           # create button to refresh database table
        self.refresh_table_button.pack(side="left", padx=5) # place refresh table button

        # log frame
        log_frame = ttk.LabelFrame(self.root, text="Arduino Serial Log") # create serial log frame
        log_frame.pack(fill="both", expand=True, padx=10, pady=10) # place serial log frame

        self.log_text = tk.Text(log_frame, height=8) # create text box for serial log
        self.log_text.pack(fill="both", expand=True) # place log text box

    def refresh_ports(self):                         # refresh available COM ports
        ports = serial.tools.list_ports.comports()   # get all available serial ports
        port_names = [port.device for port in ports] # store only port names like COM3, COM4

        self.port_box["values"] = port_names         # put port names into dropdown

        if port_names:                               # if at least one port exists
            self.port_box.current(0)                 # select first port by default

    def connect_serial(self):                        # connect to selected serial port
        selected_port = self.port_box.get()          # get selected COM port from dropdown

        if not selected_port:                        # if no port selected
            messagebox.showerror("Error", "Please select a COM port.") # show error message
            return                                   # stop function

        try:
            self.serial_port = serial.Serial(selected_port, BAUD_RATE, timeout=1) # open selected serial port
            self.running = True                      # allow serial reading

            self.serial_thread = threading.Thread(
                target=self.read_serial,
                daemon=True
            )                                       # create background thread for serial reading
            self.serial_thread.start()               # start serial reading thread

            self.status_label.config(text=f"Status: Connected to {selected_port}") # update connection status
            self.connect_button.config(state="disabled") # disable connect button
            self.disconnect_button.config(state="normal") # enable disconnect button

            self.add_log(f"Connected to {selected_port}") # add connection message to log

        except Exception as e:                       # if connection failed
            messagebox.showerror("Connection Error", str(e)) # show connection error

    def disconnect_serial(self):                     # disconnect from serial port
        self.running = False                         # stop serial reading loop

        if self.serial_port and self.serial_port.is_open: # if serial port exists and is open
            self.serial_port.close()                 # close serial port

        self.status_label.config(text="Status: Disconnected") # update status label
        self.connect_button.config(state="normal")   # enable connect button
        self.disconnect_button.config(state="disabled") # disable disconnect button

        self.add_log("Disconnected")                 # add disconnected message to log

    def read_serial(self):                           # read data from Arduino in background thread
        while self.running:                          # keep reading while running is true
            try:
                if self.serial_port and self.serial_port.in_waiting > 0: # if data is available
                    line = self.serial_port.readline().decode("utf-8", errors="ignore").strip() # read and decode one line
                    # reads one line from Arduino

                    if line:                         # if line is not empty
                        self.data_queue.put(line)    # put received line into queue

            except Exception as e:                   # if serial reading error happens
                self.data_queue.put(f"ERROR,{e}")    # put error into queue
                break                                # stop reading loop

    def process_serial_data(self):                   # process received serial data in GUI thread
        while not self.data_queue.empty():           # while queue has data
            line = self.data_queue.get()             # get one line from queue

            self.add_log(line)                       # show received line in log

            if line.startswith("TAG,"):              # if line contains RFID tag UID
                uid = line.split(",", 1)[1].strip()  # get UID after TAG,

                if uid:                              # if UID is not empty
                    # saves or updates tag in database
                    tag_id, count, is_new = self.db.add_or_update_tag(uid) # save new tag or update old one

                    if is_new:                       # if tag is new
                        self.add_log(f"New tag saved: ID={tag_id}, UID={uid}") # show new tag saved message
                    else:                            # if tag already exists
                        self.add_log(f"Existing tag updated: ID={tag_id}, Count={count}") # show updated tag message

                    self.refresh_table()             # update table after saving data

        self.root.after(100, self.process_serial_data) # repeat this function every 100 ms
        # the GUI continuously checks for new Serial data without freezing

    def refresh_table(self):                         # refresh table with database records
        # deletes old visible rows from the GUI table (only GUI rows, not database rows)
        for row in self.tree.get_children():         # go through all visible table rows
            self.tree.delete(row)                    # delete row from GUI table

        # gets all records from SQLite database
        records = self.db.get_all_tags()             # get all RFID records from database

        # inserts each database row into GUI table
        for record in records:                       # go through each database record
            self.tree.insert("", "end", values=record) # insert record into GUI table

    def add_log(self, message):                      # add message to serial log box
        self.log_text.insert("end", message + "\n") # insert message at the end
        self.log_text.see("end")                    # scroll log to the end

    def on_close(self):                             # call when GUI window is closed
        self.disconnect_serial()                    # disconnect serial port
        self.db.close()                             # close database connection
        self.root.destroy()                         # close GUI window


if __name__ == "__main__":                          # run only if this file is started directly
    root = tk.Tk()                                  # create main tkinter window
    app = RFIDApp(root)                             # create RFID GUI app object
    root.protocol("WM_DELETE_WINDOW", app.on_close) # call on_close when window is closed
    root.mainloop()                                 # start tkinter GUI loop
