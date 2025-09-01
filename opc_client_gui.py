import asyncio
import csv
import os
import time
from datetime import datetime
import pytz 
from asyncua import Client
import logging
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading


# ✅ Prosys server endpoint (check in Simulation Server window)

DEFAULT_SERVER_URL = "opc.tcp://127.0.0.1:53530/OPCUA/SimulationServer"

TAG_NODES = {
    "Constant_Val": "ns=3;i=1001",      
    "Counter_Val": "ns=3;i=1002",       
    "Random_Val": "ns=3;i=1003",        
    "Sawtooth_Val": "ns=3;i=1004",      
    "Sinusoid_Val": "ns=3;i=1005",      
    "Square_Val": "ns=3;i=1006",        
    "Triangle_Val": "ns=3;i=1007",      
    "MyLevel_Gauge": "ns=6;s=MyLevel",  
    "MySwitch_State": "ns=6;s=MySwitch",
    "Generic_Double": "ns=5;s=Double"   
}
# --------------------------------------------------------------------------------------

# Default logging interval and reconnect delay
DEFAULT_LOG_INTERVAL = 60
RECONNECT_DELAY = 10

# --- Specific Timezone Configuration ---
IST_TIMEZONE = pytz.timezone('Asia/Kolkata') # Define IST timezone

# --- Setup Application Logger (Filters out asyncua's verbose output) ---
app_logger = logging.getLogger(__name__) # Logger specific to our application
app_logger.setLevel(logging.INFO)
app_logger.propagate = False # Prevent messages from going to the root logger by default

# Add a console handler to our app_logger
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
app_logger.addHandler(console_handler)

class GuiLogHandler(logging.Handler):
    def __init__(self, text_widget, status_label, level=logging.NOTSET):
        super().__init__(level)
        self.text_widget = text_widget
        self.status_label = status_label 
        self.formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        self.max_status_len = 70 

    def emit(self, record):
        msg = self.format(record)
        self.text_widget.after(0, self._append_msg, msg)
        self.status_label.after(0, self._update_status, record.message)

    def _append_msg(self, msg):
        self.text_widget.config(state=tk.NORMAL) 
        self.text_widget.insert(tk.END, msg + "\n")
        self.text_widget.see(tk.END) 
        self.text_widget.config(state=tk.DISABLED) 

    def _update_status(self, msg_content):
        display_msg = msg_content
        if len(display_msg) > self.max_status_len:
            display_msg = display_msg[:self.max_status_len - 3] + "..."
        self.status_label.config(text=f"Status: {display_msg}")

# --- Core OPC UA Logging Logic (Adapted for Threading/GUI) ---
async def opc_logger_loop(server_url, log_interval, stop_event: threading.Event):
    """
    The main asynchronous loop for connecting, reading, and logging OPC UA data.
    Runs in a separate thread.
    """
    app_logger.info("OPC UA Logger Thread started.")

    while not stop_event.is_set(): 
        app_logger.info(f"Attempting to connect to OPC UA Server at {server_url}...")
        try:
            async with Client(url=server_url) as client:
                app_logger.info("✅ Connected to OPC UA Server")
                
                node_id_list = list(TAG_NODES.values())
                tag_nodes_objs = [client.get_node(node_id) for node_id in node_id_list]

                while not stop_event.is_set(): 
                    
                    now_local = datetime.now(IST_TIMEZONE) 
                    formatted_timestamp = now_local.strftime("%Y-%m-%d %H:%M:%S")

                    now_utc_for_epoch = datetime.now(pytz.utc) 
                    epoch_time = int(now_utc_for_epoch.timestamp())
                    # --------------------------------------------------------

                    # Filename will now use the IST hour for consistency in logging files
                    filename = f"OPC_Log_{now_local.strftime('%Y-%m-%d_%H')}.csv"

                    file_exists = os.path.isfile(filename)
                    with open(filename, "a", newline="", encoding='utf-8') as f:
                        writer = csv.writer(f)
                        if not file_exists:
                            # ✅ Header labels now explicitly state IST and UTC
                            header = ["Timestamp (24hr IST)", "Timestamp (epochtime UTC)"] + list(TAG_NODES.keys())
                            writer.writerow(header)

                        values = []
                        for node_obj in tag_nodes_objs:
                            try:
                                val = await node_obj.read_value()
                                values.append(val)
                            except Exception as e:
                                app_logger.warning(f"Error reading node {node_obj.nodeid}: {e}")
                                values.append(None) 

                        row = [formatted_timestamp, epoch_time] + values
                        writer.writerow(row)
                        # Log to console/GUI
                        app_logger.info(f"Data for {len(TAG_NODES)} tags logged to {filename}")

                    await asyncio.sleep(log_interval)

        except asyncio.CancelledError:
            app_logger.info("OPC UA connection/logging task cancelled.")
            break # Exit the loop if cancelled
        except ConnectionRefusedError:
            app_logger.error(f"Connection refused. Is the OPC UA server running at {server_url}? Retrying in {RECONNECT_DELAY}s...")
        except asyncio.TimeoutError:
            app_logger.error(f"Connection timed out. Check network or server address. Retrying in {RECONNECT_DELAY}s...")
        except Exception as e:
            app_logger.exception(f"An unexpected error occurred: {e}. Connection lost. Retrying in {RECONNECT_DELAY}s...")
        
        if not stop_event.is_set():
            await asyncio.sleep(RECONNECT_DELAY)

    app_logger.info("OPC UA Logger Thread gracefully shut down.")

# --- GUI Class ---
class OpcClientGui:
    def __init__(self, master):
        self.master = master
        master.title("OPC UA Client Logger")
        master.geometry("800x600") # Set initial window size
        master.resizable(True, True) # Allow resizing

        style = ttk.Style()
        style.theme_use('clam') 

        self.logger_thread = None
        self.stop_event = threading.Event()
        self.asyncio_loop = None 

        self.create_widgets()
        master.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_widgets(self):
        self.master.grid_columnconfigure(0, weight=1)
        self.master.grid_rowconfigure(3, weight=1) 

        config_frame = ttk.LabelFrame(self.master, text="Logger Configuration", padding="10 10 10 10")
        config_frame.grid(row=0, column=0, padx=10, pady=5, sticky=tk.EW)
        config_frame.grid_columnconfigure(1, weight=1) 

        ttk.Label(config_frame, text="Server URL:").grid(row=0, column=0, sticky=tk.W, pady=2, padx=5)
        self.server_url_entry = ttk.Entry(config_frame, width=50)
        self.server_url_entry.insert(0, DEFAULT_SERVER_URL)
        self.server_url_entry.grid(row=0, column=1, sticky=tk.EW, pady=2, padx=5)

        ttk.Label(config_frame, text="Log Interval (seconds):").grid(row=1, column=0, sticky=tk.W, pady=2, padx=5)
        self.interval_entry = ttk.Entry(config_frame, width=10)
        self.interval_entry.insert(0, str(DEFAULT_LOG_INTERVAL))
        self.interval_entry.grid(row=1, column=1, sticky=tk.W, pady=2, padx=5)

        # Buttons Frame
        button_frame = ttk.Frame(self.master)
        button_frame.grid(row=1, column=0, pady=5, padx=10, sticky=tk.EW)
        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(1, weight=1)

        self.start_button = ttk.Button(button_frame, text="Start Logging", command=self.start_logging, style='Accent.TButton')
        self.start_button.grid(row=0, column=0, sticky=tk.EW, padx=5, pady=2)

        self.stop_button = ttk.Button(button_frame, text="Stop Logging", command=self.stop_logging, state=tk.DISABLED)
        self.stop_button.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=2)

        # Log Display Area
        ttk.Label(self.master, text="Logger Output:").grid(row=2, column=0, sticky=tk.SW, padx=10, pady=(10,0))
        self.log_text = scrolledtext.ScrolledText(self.master, wrap=tk.WORD, height=15, state=tk.DISABLED, bg="#2b2b2b", fg="#cccccc", insertbackground="#cccccc") # Dark theme for log
        self.log_text.grid(row=3, column=0, padx=10, pady=5, sticky=tk.NSEW)
        
        # Status Bar (placed at row 4)
        self.status_label = ttk.Label(self.master, text="Status: Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.grid(row=4, column=0, sticky=tk.EW, ipady=3)

       
        self.gui_log_handler = GuiLogHandler(self.log_text, self.status_label)
        app_logger.addHandler(self.gui_log_handler)
        app_logger.info("GUI started. Ready for configuration.") 


    def start_logging(self):
        server_url = self.server_url_entry.get()
        try:
            log_interval = int(self.interval_entry.get())
            if log_interval <= 0:
                raise ValueError("Interval must be a positive number.")
        except ValueError as e:
            messagebox.showerror("Invalid Input", f"Log Interval error: {e}")
            return
        
        # Disable config inputs, enable stop button
        self.server_url_entry.config(state=tk.DISABLED)
        self.interval_entry.config(state=tk.DISABLED)
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        
        # Clear previous logs in the GUI
        self.log_text.config(state=tk.NORMAL) 
        self.log_text.delete(1.0, tk.END) 
        self.log_text.config(state=tk.DISABLED) 

        self.stop_event.clear() 
        
        self.logger_thread = threading.Thread(
            target=self._run_asyncio_thread,
            args=(server_url, log_interval, self.stop_event),
            daemon=True 
        )
        self.logger_thread.start()
        app_logger.info("Logger started.") # This message will go to GUI and console

    def _run_asyncio_thread(self, server_url, log_interval, stop_event):
        """Target function for the background thread to run the asyncio loop."""
        self.asyncio_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.asyncio_loop)
        
        try:
            self.asyncio_loop.run_until_complete(opc_logger_loop(server_url, log_interval, stop_event))
        except asyncio.CancelledError:
            app_logger.info("Asyncio task was cancelled.")
        finally:
            self.asyncio_loop.close()
            app_logger.info("Asyncio loop closed.")
        
        self.master.after(0, self._reset_gui_buttons)


    def stop_logging(self):
        app_logger.info("Stopping logger...") 
        self.stop_event.set() 
        
        # Reset GUI buttons immediately
        self._reset_gui_buttons()

    def _reset_gui_buttons(self):
        """Resets GUI buttons to initial state."""
        self.server_url_entry.config(state=tk.NORMAL)
        self.interval_entry.config(state=tk.NORMAL)
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        app_logger.info("Status: Ready") # This message will go to GUI and console

    def on_closing(self):
        """Called when the Tkinter window is closed."""
        if messagebox.askokcancel("Quit", "Do you want to quit the logger?"):
            if self.logger_thread and self.logger_thread.is_alive():
                app_logger.info("Signaling background thread to stop...")
                self.stop_event.set() 
                self.logger_thread.join(timeout=RECONNECT_DELAY * 2 + DEFAULT_LOG_INTERVAL + 5) 
                if self.logger_thread.is_alive():
                    app_logger.warning("Background thread did not terminate in time.")
            app_logger.info("Destroying GUI window.")
            self.master.destroy()

# --- Main Program Entry Point ---
if __name__ == "__main__":
    logging.getLogger('asyncua').setLevel(logging.WARNING)
    
    root = tk.Tk()
    app = OpcClientGui(root)
    root.mainloop() # Start the Tkinter GUI event loop

    app_logger.info("Main GUI program finished.")
