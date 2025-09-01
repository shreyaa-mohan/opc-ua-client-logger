# OPC UA Client Logger

This project demonstrates how to set up an **OPC UA client** that connects to a simulated OPC UA server, reads multiple tags at regular intervals, and logs the data into **hourly CSV/Excel files**.  

It was built as part of an internship assignment to gain hands-on experience with **OPC UA protocol, client-server communication, and industrial data logging**.

---

### 🚀 Features
- Connects to **Prosys OPC UA Simulation Server**  
- Reads **10 dummy tags** once per minute  
- Logs values with both **24hr timestamp** and **epoch time (UTC)**  
- Automatically creates a **new log file each hour**  
- Data stored in **CSV/Excel format** for easy analysis  

---

### 🛠️ Setup Instructions

#### 1. Prerequisites
- Python 3.8 or above  
- `pip` (Python package manager)  
- Prosys OPC UA Simulation Server → [Download Here](https://www.prosysopc.com/products/opc-ua-simulation-server/)  
- UAExpert Client → [Download Here](https://www.unified-automation.com/downloads/opc-ua-clients.html)  

#### 2. Install Dependencies
pip install asyncua

#### 3. Run the Server

- Start the Prosys Simulation Server.

- Verify tags using UAExpert (at least 10 dummy tags such as Constant_Val, Counter_Val, Random_Val, etc.).

#### 4. Run the Client
python client.py 
The client will: 
Connect to the server 
Read 10 tags every minute 
Save logs into hourly files (e.g., OPC_Log_2025-09-01_13.csv) 

#### 🔮 Future Enhancements


Store logs directly into a database (SQLite/PostgreSQL) 

Implement OPC UA security (certificates, authentication) 
