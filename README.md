# Real-Time Windows Event Log Analysis Engine

## 📘 Project Overview
This project is part of **COMP 8800 – Major Project 1** at  **British Columbia Institute of Technology (BCIT)**.  
The goal is to develop a **Real-Time Windows Event Log Analysis Engine** that collects, stores, and analyzes Windows Event Logs to detect unusual or suspicious system activity.

The system currently supports **log collection, database storage, and visualization through a FastAPI dashboard**.  
This project focuses on the **Windows OS** for Term 1 and will extend to **Linux log analysis** in Term 2.

---

## 🧩 Features (Prototype 1)
- Collects **Windows Event Logs** using PowerShell and the `Get-WinEvent` command.
- Parses logs and stores them in a local **SQLite database** (`logs.db`).
- Provides a simple **FastAPI dashboard** to view and filter collected logs.
- Prepares ground for **AI-based anomaly detection** in upcoming milestones.

---

## 🧠 Objectives
- Automate collection and organization of Windows event logs.
- Enable real-time monitoring and querying of logs.
- Lay foundation for detecting suspicious or repetitive event patterns.
- Build a scalable framework that can later integrate AI/ML modules for smarter detection.

---

## ⚙️ Technologies Used
| Component | Technology |
|------------|-------------|
| Language | Python 3.11 |
| Backend | FastAPI |
| Database | SQLite |
| OS Integration | PowerShell (`Get-WinEvent`) |
| Visualization | HTML / JavaScript Dashboard |
| Environment | Windows 10/11 |

---

## 🧪 Current Progress
✅ **Collector Script (`collector_to_sqlite.py`)**  
- Fetches Windows Event Logs and stores them in SQLite.  
- Automatically avoids duplicate entries using event record IDs.

✅ **Database Schema (`logs.db`)**  
- Stores key fields such as:
  - `record_id`, `event_id`, `level`, `provider`, `timestamp`, `message`.

✅ **Dashboard (FastAPI)**  
- Displays recent logs with filtering options.  
- Shows basic statistics like total log count and top event types.

---

## 💻 How to Run

### 1. **Run the Collector**
```bash
python collector_to_sqlite.py
```
### 2. **Start the Dashboard**
```bash
uvicorn dashboard.app:app --reload
```
Then open your browser at http://127.0.0.1:8000