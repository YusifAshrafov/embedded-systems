import csv                                      # import csv for saving and reading player data
import os                                       # import os for file and folder paths
import queue                                    # import queue for sending serial messages safely to GUI
import re                                       # import re for cleaning player names for file names
import threading                                # import threading for reading serial in background
from datetime import datetime                   # import datetime for real timestamps
import tkinter as tk                            # import tkinter for GUI window
from tkinter import ttk, scrolledtext, messagebox # import tkinter widgets and message boxes

import serial                                   # import pyserial for serial communication
import serial.tools.list_ports                  # import list_ports for finding Arduino COM ports
from matplotlib.figure import Figure            # import Figure for creating charts
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg # import canvas to show matplotlib chart inside tkinter


class ReactionGameGUI:                          # main GUI class for reaction game
    def __init__(self, root):                   # runs when GUI object is created
        self.root = root                        # store main tkinter window
        self.root.title("Two-Player Reaction Game") # set window title
        self.root.geometry("1050x720")          # set window size

        # creates and finds the folder - player_data
        self.base_dir = os.path.dirname(os.path.abspath(__file__)) # get folder where this python file exists
        self.data_dir = os.path.join(self.base_dir, "player_data") # create path for player_data folder
        os.makedirs(self.data_dir, exist_ok=True) # create player_data folder if it does not exist

        self.ser = None                         # serial object starts as none
        self.connected = False                  # stores connection state; false = not connected
        self.reader_running = False             # stores serial reader thread state
        self.msg_queue = queue.Queue()          # queue to pass messages from serial thread to GUI
        self.connected_port = None              # stores current connected COM port

        self.p1 = "Player 1"                    # default player 1 name
        self.p2 = "Player 2"                    # default player 2 name
        self.score = [0, 0]                     # stores score for player 1 and player 2
        self.round_number = 0                   # stores current round number
        self.match_over = False                 # stores match state; true when match finished
        self.player_file_map = {}               # dictionary to connect player name with csv file path

        self.build_gui()                        # create GUI tabs and elements
        self.refresh_player_list()              # load existing players from csv files

        # selected player changed -> automatically update the opponent dropdown
        self.analytics_player.bind("<<ComboboxSelected>>", self.update_opponent_list) # update opponents when player is selected

        self.root.after(100, self.process_serial_queue) # check serial queue every 100 ms
        self.root.after(500, self.auto_connect_loop)    # start auto connect loop after 500 ms
        self.root.protocol("WM_DELETE_WINDOW", self.on_close) # call on_close when window is closed

    # ! GUI
    def build_gui(self):                        # create main notebook with tabs
        nb = ttk.Notebook(self.root)            # create notebook widget
        nb.pack(fill="both", expand=True, padx=10, pady=10) # place notebook in window

        self.game_tab = ttk.Frame(nb)           # create game tab frame
        self.analytics_tab = ttk.Frame(nb)      # create analytics tab frame
        nb.add(self.game_tab, text="Game")      # add game tab to notebook
        nb.add(self.analytics_tab, text="Analytics") # add analytics tab to notebook

        self.build_game_tab()                   # create all widgets inside game tab
        self.build_analytics_tab()              # create all widgets inside analytics tab

    def build_game_tab(self):                   # create game tab interface
        conn = ttk.LabelFrame(self.game_tab, text="Connection", padding=10) # create connection frame
        conn.pack(fill="x", padx=10, pady=8)    # place connection frame

        self.conn_label = ttk.Label(conn, text="Not connected", font=("Arial", 11, "bold")) # create connection status label
        self.conn_label.grid(row=0, column=0, padx=10, pady=5, sticky="w") # place connection label

        players = ttk.LabelFrame(self.game_tab, text="Players", padding=10) # create players frame
        players.pack(fill="x", padx=10, pady=8) # place players frame

        ttk.Label(players, text="Player 1 Name:").grid(row=0, column=0, padx=5, pady=5, sticky="w") # label for player 1 name
        self.p1_entry = ttk.Entry(players, width=18) # create entry for player 1 name
        self.p1_entry.grid(row=0, column=1, padx=5, pady=5) # place player 1 entry
        self.p1_entry.insert(0, "Player 1")     # put default player 1 name

        ttk.Label(players, text="Player 2 Name:").grid(row=0, column=2, padx=5, pady=5, sticky="w") # label for player 2 name
        self.p2_entry = ttk.Entry(players, width=18) # create entry for player 2 name
        self.p2_entry.grid(row=0, column=3, padx=5, pady=5) # place player 2 entry
        self.p2_entry.insert(0, "Player 2")     # put default player 2 name

        ttk.Button(players, text="Start Match", command=self.start_match).grid(row=0, column=4, padx=8) # button to start match
        self.next_btn = ttk.Button(players, text="Next Round", command=self.start_round, state="disabled") # button for next round
        self.next_btn.grid(row=0, column=5, padx=8) # place next round button
        ttk.Button(players, text="Reset Match", command=self.reset_match).grid(row=0, column=6, padx=8) # button to reset match
        ttk.Button(players, text="Center Servo", command=lambda: self.send("CENTER_SERVO")).grid(row=0, column=7, padx=8) # button to center servo

        status = ttk.LabelFrame(self.game_tab, text="Status", padding=10) # create status frame
        status.pack(fill="x", padx=10, pady=8) # place status frame

        self.state_label = ttk.Label(status, text="State: Idle", font=("Arial", 11, "bold")) # create state label
        self.state_label.grid(row=0, column=0, padx=10, pady=5, sticky="w") # place state label

        self.round_label = ttk.Label(status, text="Round: 0", font=("Arial", 11, "bold")) # create round label
        self.round_label.grid(row=0, column=1, padx=10, pady=5, sticky="w") # place round label

        self.result_label = ttk.Label(status, text="No results yet", font=("Arial", 11)) # create result label
        self.result_label.grid(row=1, column=0, columnspan=4, padx=10, pady=5, sticky="w") # place result label

        score_box = ttk.LabelFrame(self.game_tab, text="Score", padding=10) # create score frame
        score_box.pack(fill="x", padx=10, pady=8) # place score frame

        self.p1_score_label = ttk.Label(score_box, text="Player 1: 0", font=("Arial", 12, "bold")) # create player 1 score label
        self.p1_score_label.grid(row=0, column=0, padx=20, pady=5, sticky="w") # place player 1 score label

        self.p2_score_label = ttk.Label(score_box, text="Player 2: 0", font=("Arial", 12, "bold")) # create player 2 score label
        self.p2_score_label.grid(row=0, column=1, padx=20, pady=5, sticky="w") # place player 2 score label

        log_frame = ttk.LabelFrame(self.game_tab, text="Game Log", padding=10) # create game log frame
        log_frame.pack(fill="both", expand=True, padx=10, pady=8) # place game log frame

        self.log_box = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, font=("Consolas", 10)) # create scrollable text box for logs
        self.log_box.pack(fill="both", expand=True) # place log box

    def build_analytics_tab(self):              # create analytics tab interface
        top = ttk.LabelFrame(self.analytics_tab, text="Analytics Controls", padding=10) # create analytics controls frame
        top.pack(fill="x", padx=10, pady=8)     # place analytics controls frame

        ttk.Label(top, text="Player:").grid(row=0, column=0, padx=5, pady=5, sticky="w") # label for player selection
        self.analytics_player = ttk.Combobox(top, width=22, state="readonly") # create player dropdown
        self.analytics_player.grid(row=0, column=1, padx=5, pady=5) # place player dropdown

        ttk.Button(top, text="Refresh Player List", command=self.refresh_player_list).grid(row=0, column=2, padx=10) # button to refresh player list

        ttk.Label(top, text="Opponent:").grid(row=0, column=3, padx=5, pady=5, sticky="w") # label for opponent selection
        self.opponent_combo = ttk.Combobox(top, width=22, state="readonly") # create opponent dropdown
        self.opponent_combo.grid(row=0, column=4, padx=5, pady=5) # place opponent dropdown

        ttk.Button(top, text="Plot Reaction Times", command=self.plot_reaction_times).grid(row=1, column=0, columnspan=2, padx=8, pady=8, sticky="w") # button for reaction time graph
        ttk.Button(top, text="Plot Head-to-Head", command=self.plot_head_to_head).grid(row=1, column=2, columnspan=2, padx=8, pady=8, sticky="w") # button for head-to-head graph
        ttk.Button(top, text="Plot Win Rate vs All Opponents", command=self.plot_all_opponents).grid(row=1, column=4, padx=8, pady=8, sticky="w") # button for all opponents graph

        summary = ttk.LabelFrame(self.analytics_tab, text="Summary", padding=10) # create summary frame
        summary.pack(fill="x", padx=10, pady=8) # place summary frame
        self.summary_label = ttk.Label(summary, text="Load a player to see analytics.") # create summary label
        self.summary_label.pack(anchor="w")     # place summary label

        chart = ttk.LabelFrame(self.analytics_tab, text="Chart", padding=10) # create chart frame
        chart.pack(fill="both", expand=True, padx=10, pady=8) # place chart frame

        self.figure = Figure(figsize=(8.8, 5), dpi=100) # create matplotlib figure
        self.ax = self.figure.add_subplot(111) # create one chart area
        self.ax.set_title("No data loaded yet") # set default chart title
        self.canvas = FigureCanvasTkAgg(self.figure, master=chart) # create tkinter canvas for matplotlib chart
        self.canvas.get_tk_widget().pack(fill="both", expand=True) # place chart inside GUI

    # ! Small helpers
    def log(self, text):                        # add text to game log box
        stamp = datetime.now().strftime("%H:%M:%S") # create current time stamp
        self.log_box.insert(tk.END, f"[{stamp}] {text}\n") # insert log message
        self.log_box.see(tk.END)               # scroll to the bottom

    def set_state(self, text):                  # update state label
        self.state_label.config(text=f"State: {text}") # show current game state

    def update_labels(self):                    # update round and score labels
        self.round_label.config(text=f"Round: {self.round_number}") # update round number
        self.p1_score_label.config(text=f"{self.p1}: {self.score[0]}") # update player 1 score
        self.p2_score_label.config(text=f"{self.p2}: {self.score[1]}") # update player 2 score

    def safe_filename(self, name):              # make player name safe for file name
        name = re.sub(r'[<>:"/\\|?*]', "_", name.strip()) # replace forbidden file name characters with _
        return name or "unknown_player"         # return name, or unknown_player if name is empty

    def player_file(self, name):                # file name is built from the player name
        return os.path.join(self.data_dir, f"{self.safe_filename(name)}.csv") # return path to player's csv file

    def csv_fields(self):                       # return csv column names
        return [
            "timestamp", "event_type", "player", "opponent", "round_number",
            "outcome", "reaction_ms", "result_type", "false_start_committed",
            "score_self", "score_opponent", "match_winner"
        ]                                       # columns saved in each csv file

    def append_csv(self, player_name, row):     # results appended
        path = self.player_file(player_name)    # get csv file path for this player
        exists = os.path.exists(path)           # check if file already exists
        with open(path, "a", newline="", encoding="utf-8") as f: # open csv in append mode
            writer = csv.DictWriter(f, fieldnames=self.csv_fields()) # create csv writer with column names
            if not exists:                      # if file is new
                writer.writeheader()            # write column headers first
            writer.writerow(row)                # write one result row

    # what saved in round: player/opponent/round/number/outcome/reaction/time/false start or valid press/score
    def make_row(self, player, opponent, event_type, outcome, reaction_ms="",
                 result_type="", false_start="NO", match_winner=""): # create one csv row
        return {
            "timestamp": datetime.now().isoformat(timespec="seconds"), # save date and time
            "event_type": event_type,          # save event type, ROUND or MATCH
            "player": player,                  # save player name
            "opponent": opponent,              # save opponent name
            "round_number": self.round_number, # save current round number
            "outcome": outcome,                # save WIN or LOSE
            "reaction_ms": reaction_ms,        # save reaction time if it exists
            "result_type": result_type,        # save VALID or EARLY
            "false_start_committed": false_start, # save if player false started
            "score_self": self.score[0] if player == self.p1 else self.score[1], # save this player's score
            "score_opponent": self.score[1] if player == self.p1 else self.score[0], # save opponent score
            "match_winner": match_winner       # save match winner only for match row
        }

    def load_rows(self, player):                # load all csv rows for selected player
        path = self.player_file_map.get(player) # get file path from player map
        if not path or not os.path.exists(path): # if path does not exist
            return []                           # return empty list
        with open(path, "r", newline="", encoding="utf-8") as f: # open csv file for reading
            return list(csv.DictReader(f))      # read csv rows and return as list

    def draw_plot(self, title, xlabel="", ylabel=""): # prepare chart before drawing new graph
        self.ax.clear()                         # clear old graph
        self.ax.set_title(title)                # set graph title
        self.ax.set_xlabel(xlabel)              # set x-axis label
        self.ax.set_ylabel(ylabel)              # set y-axis label

    # ! Auto serial
    def get_available_ports(self):              # get available COM ports
        return [p.device for p in serial.tools.list_ports.comports()] # return list with port names

    def try_auto_connect(self):                 # try to connect to Arduino automatically
        if self.connected and self.ser and self.ser.is_open: # if already connected
            return                              # do nothing

        ports = self.get_available_ports()      # get all available ports
        if not ports:                           # if no ports found
            self.conn_label.config(text="Not connected") # show not connected
            return                              # exit function

        for port in ports:                      # try each available port
            try:
                self.ser = serial.Serial(port, 9600, timeout=0.1) # try to open serial port
                self.connected = True           # set connection state as true
                self.reader_running = True      # allow serial reader thread to run
                self.connected_port = port      # save connected port name
                self.conn_label.config(text="Connected") # show connected state
                self.log(f"Connected automatically to {port}") # write connection in log
                threading.Thread(target=self.serial_reader, daemon=True).start() # serial reader run in background
                return                          # stop trying after successful connection
            except Exception:                   # if this port failed
                continue                        # try next port

        self.connected = False                  # if no port connected, set false
        self.connected_port = None              # clear connected port
        self.conn_label.config(text="Not connected") # show not connected

    def disconnect_serial(self, log_message=True): # disconnect serial connection
        self.reader_running = False             # stop serial reader thread
        self.connected = False                  # set connection state as false
        self.connected_port = None              # clear connected port

        try:
            if self.ser and self.ser.is_open:   # if serial exists and is open
                self.ser.close()                # close serial port
        except Exception:                       # if close gives error
            pass                                # ignore error

        self.conn_label.config(text="Not connected") # update connection label
        if log_message:                         # if log message is needed
            self.log("Serial disconnected")     # write disconnect message in log

    def auto_connect_loop(self):                # repeat auto connection checking
        ports = self.get_available_ports()      # get current available ports

        if self.connected and self.connected_port not in ports: # if connected port disappeared
            self.disconnect_serial(log_message=True) # disconnect from old port

        if not self.connected:                  # if not connected
            self.try_auto_connect()             # try to connect automatically

        self.root.after(1500, self.auto_connect_loop) # repeat this function every 1.5 sec

    def send(self, cmd):                        # responsible for controlling the game flow
        if not (self.connected and self.ser and self.ser.is_open): # if Arduino is not connected
            self.log("Arduino is not connected.") # write message in log
            return                              # exit function
        try:
            self.ser.write((cmd + "\n").encode()) # send command to Arduino with new line
            self.log(f"TX -> {cmd}")            # log transmitted command
        except Exception as e:                  # if sending failed
            self.log(f"Serial write error: {e}") # show serial write error

    def serial_reader(self):                    # Arduino sends messages
        while self.reader_running:              # loop while reader is enabled
            try:
                if self.ser and self.ser.is_open and self.ser.in_waiting: # if serial has unread data
                    line = self.ser.readline().decode(errors="ignore").strip() # read one line from Arduino
                    if line:                    # if line is not empty
                        self.msg_queue.put(line) # reads arduino and puts into a queue
            except Exception as e:              # if reading failed
                self.msg_queue.put(f"ERROR_SERIAL:{e}") # send error message to GUI queue
                break                           # stop reading loop

    def process_serial_queue(self):             # processes messages in the GUI thread
        while not self.msg_queue.empty():       # while queue has messages
            self.handle_serial(self.msg_queue.get()) # take message and handle it
        self.root.after(100, self.process_serial_queue) # repeat every 100 ms

    # ! Game actions
    def start_match(self):                      # start new match
        if not self.connected:                  # if Arduino is not connected
            messagebox.showwarning("Warning", "Arduino is not connected yet.") # show warning
            return                              # exit function

        self.p1 = self.p1_entry.get().strip() or "Player 1" # read player 1 name from entry
        self.p2 = self.p2_entry.get().strip() or "Player 2" # read player 2 name from entry

        if self.p1.lower() == self.p2.lower():  # check if names are same
            messagebox.showwarning("Warning", "Player names must be different.") # show warning
            return                              # exit function

        self.score = [0, 0]                     # reset scores
        self.round_number = 0                   # reset round number
        self.match_over = False                 # match is not over
        self.update_labels()                    # update score and round labels
        self.set_state("Match started")         # update state label
        self.result_label.config(text=f"Match started: {self.p1} vs {self.p2}") # show match start text
        self.log("=" * 60)                      # print separator in log
        self.log(f"New match: {self.p1} vs {self.p2}") # log new match names

        self.send("RESET_MATCH")                # send reset command to Arduino
        self.root.after(200, self.start_round)  # start first round after 200 ms

    def start_round(self):                      # start next round
        if self.match_over:                     # if match already finished
            self.log("Match is already over.")  # write message in log
            return                              # exit function
        self.next_btn.config(state="disabled")  # disable next button while round is active
        self.send("START_ROUND")                # send start round command to Arduino

    def reset_match(self):                      # reset match from GUI
        self.score = [0, 0]                     # reset scores
        self.round_number = 0                   # reset round number
        self.match_over = False                 # match is not over
        self.update_labels()                    # update score and round labels
        self.set_state("Idle")                  # set state to idle
        self.result_label.config(text="Match reset") # show reset text
        self.next_btn.config(state="disabled")  # disable next round button
        self.send("RESET_MATCH")                # send reset command to Arduino
        self.log("Match reset from GUI")        # log reset action

    # ! Serial handling
    def handle_serial(self, line):              # handle one message from Arduino
        # do not log WAIT_MS - wait time
        if not line.startswith("WAIT_MS:"):     # if message is not hidden wait time
            self.log(f"RX <- {line}")           # show received message in log

        if line.startswith("ERROR_SERIAL:"):    # if serial error received
            self.disconnect_serial(log_message=False) # disconnect without extra log
            self.conn_label.config(text="Not connected") # show not connected
            return                              # exit function

        if line == "READY":                     # Arduino ready message
            self.set_state("Arduino ready")     # show Arduino ready state

        elif line == "ROUND_START":             # round start message
            self.round_number += 1              # increase round number
            self.update_labels()                # update round label
            self.set_state("Waiting for buzzer") # show waiting state
            self.result_label.config(text=f"Round {self.round_number} started") # show round started text

        elif line.startswith("WAIT_MS:"):        # wait time message from Arduino
            # Hidden from players: do nothing
            pass                                # do not show this time to players

        elif line == "GO":                      # GO message from Arduino
            self.set_state("GO")                # show GO state
            self.result_label.config(text="Buzzer fired. Players can press now.") # show instruction to press

        elif line.startswith("RESULT:"):         # round result message
            self.process_result(line)            # parse and save round result

        elif line.startswith("MATCH_WINNER:"):   # match winner message
            self.process_match_winner(line)      # parse and save match winner

        elif line == "VICTORY_SPIN_DONE":        # stepper finished victory spin
            self.log("Stepper victory spin completed") # write message in log

        elif line == "ROUND_DONE":               # round finished message
            if not self.match_over:              # if match is not finished
                self.set_state("Round complete") # show round complete
                self.next_btn.config(state="normal") # enable next round button

        elif line == "MATCH_RESET":              # Arduino reset message
            self.set_state("Reset complete")     # show reset complete

    def process_result(self, line):              # handling round results
        # RESULT:winner:type:reaction:score1:score2:round
        try:
            _, winner, result_type, reaction_ms, s1, s2, rnd = line.split(":") # split result message
            winner = int(winner)              # convert winner number to integer
            reaction_ms = int(reaction_ms)    # convert reaction time to integer
            self.score = [int(s1), int(s2)]   # update scores from Arduino
            self.round_number = int(rnd)      # update round number from Arduino
            self.update_labels()              # update labels with new score

            loser = 2 if winner == 1 else 1   # find loser number
            winner_name = self.p1 if winner == 1 else self.p2 # get winner name
            loser_name = self.p1 if loser == 1 else self.p2   # get loser name

            if result_type == "EARLY":        # if result was false start
                text = f"{winner_name} wins because {loser_name} pressed too early." # create false start result text
            else:                             # if result was valid press
                text = f"{winner_name} wins with reaction time {reaction_ms} ms." # create valid result text

            self.result_label.config(text=text) # show result text in GUI
            self.log(text)                     # write result in log

            self.save_round_result(winner, result_type, reaction_ms) # save round result to csv
            self.refresh_player_list()         # refresh analytics player list

        except Exception as e:                 # if result parsing failed
            self.log(f"Failed to parse RESULT message: {e}") # show parse error in log

    def process_match_winner(self, line):       # handle match winner message
        try:
            winner = int(line.split(":")[1])   # get winner number from message
            self.match_over = True             # set match over to true
            self.next_btn.config(state="disabled") # disable next round button

            winner_name = self.p1 if winner == 1 else self.p2 # get match winner name
            self.set_state("Match finished")   # update state label
            self.result_label.config(text=f"Match winner: {winner_name}") # show match winner
            self.log(f"Match winner: {winner_name}") # write match winner in log

            self.save_match_result(winner_name) # save match result to csv
            self.refresh_player_list()          # refresh analytics list

        except Exception as e:                  # if parsing failed
            self.log(f"Failed to parse MATCH_WINNER message: {e}") # show parse error in log

    # saving results
    def save_round_result(self, winner, result_type, reaction_ms): # save round result for both players
        p1_outcome = "WIN" if winner == 1 else "LOSE" # player 1 result
        p2_outcome = "WIN" if winner == 2 else "LOSE" # player 2 result

        p1_reaction = reaction_ms if (result_type == "VALID" and winner == 1) else "" # save p1 reaction only if p1 valid win
        p2_reaction = reaction_ms if (result_type == "VALID" and winner == 2) else "" # save p2 reaction only if p2 valid win

        p1_false = "YES" if (result_type == "EARLY" and winner == 2) else "NO" # p1 false start if p2 won by EARLY
        p2_false = "YES" if (result_type == "EARLY" and winner == 1) else "NO" # p2 false start if p1 won by EARLY

        row1 = self.make_row(self.p1, self.p2, "ROUND", p1_outcome, p1_reaction, result_type, p1_false) # create row for player 1
        row2 = self.make_row(self.p2, self.p1, "ROUND", p2_outcome, p2_reaction, result_type, p2_false) # create row for player 2

        self.append_csv(self.p1, row1)          # save player 1 row
        self.append_csv(self.p2, row2)          # save player 2 row

    def save_match_result(self, winner_name):   # player wins the whole match -> save
        row1 = self.make_row(self.p1, self.p2, "MATCH", "WIN" if winner_name == self.p1 else "LOSE", match_winner=winner_name) # create match row for player 1
        row2 = self.make_row(self.p2, self.p1, "MATCH", "WIN" if winner_name == self.p2 else "LOSE", match_winner=winner_name) # create match row for player 2

        self.append_csv(self.p1, row1)          # save match result for player 1
        self.append_csv(self.p2, row2)          # save match result for player 2

    # ! Analytics
    def refresh_player_list(self):              # reload players from csv files
        self.player_file_map = {}               # clear old player file map
        names = []                              # list to store player names

        for filename in os.listdir(self.data_dir): # check all files in player_data folder
            if not filename.lower().endswith(".csv"): # if file is not csv
                continue                        # skip this file

            path = os.path.join(self.data_dir, filename) # create full file path
            name = os.path.splitext(filename)[0] # get name from filename without .csv

            try:
                with open(path, "r", newline="", encoding="utf-8") as f: # open csv file
                    first = next(csv.DictReader(f), None) # read first csv row
                    if first and first.get("player"): # if player name exists in file
                        name = first["player"]       # use real player name from csv
            except Exception:                       # if file reading failed
                pass                                # ignore this file problem

            self.player_file_map[name] = path       # save player name and file path
            names.append(name)                      # add player name to list

        names = sorted(set(names))                  # remove duplicates and sort names
        self.analytics_player["values"] = names     # put names into player dropdown

        if names and self.analytics_player.get() not in names: # if selected player is not in list
            self.analytics_player.set(names[0])     # select first player

        self.update_opponent_list()                 # update opponent dropdown

    def update_opponent_list(self, event=None):      # update opponent list for selected player
        player = self.analytics_player.get().strip() # get selected player name
        opponents = []                              # list to store opponents

        if player:                                  # if player selected
            rows = self.load_rows(player)           # load rows for selected player
            opponents = sorted({r["opponent"].strip() for r in rows if r.get("opponent", "").strip()}) # get unique opponents

        if not opponents:                           # if no opponents found from csv
            opponents = [name for name in self.player_file_map.keys() if name != player] # use all other players

        self.opponent_combo["values"] = opponents   # put opponents into dropdown

        current = self.opponent_combo.get().strip() # get current selected opponent
        if opponents:                               # if opponent list is not empty
            if current not in opponents:            # if current opponent is not valid
                self.opponent_combo.set(opponents[0]) # select first opponent
        else:                                       # if no opponents
            self.opponent_combo.set("")             # clear opponent dropdown

    def plot_reaction_times(self):                  # plot reaction times for selected player
        player = self.analytics_player.get().strip() # get selected player
        if not player:                              # if no player selected
            messagebox.showwarning("Warning", "Select a player first.") # show warning
            return                                  # exit function

        # analytics tab loads saved CSV files and plots graphs
        rows = [
            r for r in self.load_rows(player)       # load rows for selected player
            if r["event_type"] == "ROUND" and r["outcome"] == "WIN" and str(r["reaction_ms"]).strip() # keep only valid winning reaction rows
        ]

        values = []                                 # list to store reaction times
        for r in rows:                              # go through selected rows
            try:
                values.append(int(r["reaction_ms"])) # convert reaction time to integer and add to list
            except Exception:                       # if value is not valid
                pass                                # ignore it

        if not values:                              # if no reaction data found
            self.summary_label.config(text=f"No reaction-time data for {player}.") # show no data summary
            self.draw_plot("No reaction-time data") # clear chart and show title
            self.canvas.draw()                      # redraw chart
            return                                  # exit function

        avg_val = sum(values) / len(values)          # calculate average reaction time
        best_val = min(values)                       # find best reaction time

        self.summary_label.config(
            text=f"{player}: {len(values)} valid winning reactions | Average = {avg_val:.1f} ms | Best = {best_val} ms"
        )                                           # show analytics summary

        x = list(range(1, len(values) + 1))          # create x values for graph
        self.draw_plot(f"Reaction Times - {player}", "Winning reaction number", "Reaction time (ms)") # prepare chart
        self.ax.plot(x, values, marker="o")         # plot reaction time line with points
        self.ax.grid(True)                          # show grid on graph
        self.canvas.draw()                          # redraw canvas

    def plot_head_to_head(self):                    # plot wins and losses against one opponent
        player = self.analytics_player.get().strip() # get selected player
        opponent = self.opponent_combo.get().strip() # get selected opponent

        if not player:                              # if no player selected
            messagebox.showwarning("Warning", "Select a player first.") # show warning
            return                                  # exit function
        if not opponent:                            # if no opponent selected
            messagebox.showwarning("Warning", "Select an opponent first.") # show warning
            return                                  # exit function

        rows = [
            r for r in self.load_rows(player)       # load rows for selected player
            if r["event_type"] == "ROUND" and r["opponent"].strip().lower() == opponent.lower() # keep only rounds vs selected opponent
        ]

        if not rows:                                # if no head-to-head data
            self.summary_label.config(text=f"No head-to-head data for {player} vs {opponent}.") # show no data summary
            self.draw_plot("No head-to-head data") # clear chart
            self.canvas.draw()                      # redraw chart
            return                                  # exit function

        wins = sum(r["outcome"] == "WIN" for r in rows) # count wins
        losses = sum(r["outcome"] == "LOSE" for r in rows) # count losses
        total = wins + losses                       # calculate total rounds
        rate = (wins / total * 100) if total else 0 # calculate win rate in percent

        self.summary_label.config(
            text=f"{player} vs {opponent}: Wins = {wins}, Losses = {losses}, Win rate = {rate:.1f}%"
        )                                           # show head-to-head summary

        self.draw_plot(f"Head-to-Head: {player} vs {opponent}", "", "Rounds") # prepare bar graph
        self.ax.bar(["Wins", "Losses"], [wins, losses]) # draw wins and losses bars
        self.canvas.draw()                          # redraw chart

    def plot_all_opponents(self):                   # plot win rate against all opponents
        player = self.analytics_player.get().strip() # get selected player
        if not player:                              # if no player selected
            messagebox.showwarning("Warning", "Select a player first.") # show warning
            return                                  # exit function

        rows = [r for r in self.load_rows(player) if r["event_type"] == "ROUND"] # load all round rows

        if not rows:                                # if no round data
            self.summary_label.config(text=f"No round data for {player}.") # show no data summary
            self.draw_plot("No opponent data")     # clear chart
            self.canvas.draw()                      # redraw chart
            return                                  # exit function

        stats = {}                                  # dictionary to store wins and total per opponent
        for r in rows:                              # go through all round rows
            opp = r["opponent"].strip()             # get opponent name
            stats.setdefault(opp, {"wins": 0, "total": 0}) # create stats for opponent if not exists
            stats[opp]["total"] += 1                # increase total rounds
            if r["outcome"] == "WIN":               # if player won this round
                stats[opp]["wins"] += 1             # increase wins

        opponents = list(stats.keys())              # get opponent names
        rates = [(stats[o]["wins"] / stats[o]["total"] * 100) if stats[o]["total"] else 0 for o in opponents] # calculate win rates

        self.summary_label.config(
            text=f"{player}: showing win rate against {len(opponents)} opponent(s)."
        )                                           # show summary text

        self.draw_plot(f"Win Rate vs Opponents - {player}", "", "Win rate (%)") # prepare win rate graph
        self.ax.bar(opponents, rates)               # draw win rate bars
        self.ax.set_ylim(0, 100)                    # set y-axis from 0 to 100 percent
        self.ax.tick_params(axis="x", rotation=25)  # rotate opponent names on x-axis
        self.canvas.draw()                          # redraw chart

    # ! Close
    def on_close(self):                             # call when window is closed
        self.disconnect_serial(log_message=False)   # disconnect serial without extra log
        self.root.destroy()                         # close GUI window


if __name__ == "__main__":                          # run only if this file started directly
    root = tk.Tk()                                  # create main tkinter window
    app = ReactionGameGUI(root)                     # create GUI app object
    root.mainloop()                                 # start tkinter GUI loop
