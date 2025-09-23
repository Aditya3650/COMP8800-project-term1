import win32evtlog  # pip install pywin32
import json

def read_and_save_logs(server="localhost", log_type="System", num_records=50):
    """
    Reads Windows Event Logs.
    :param server: Server name (default: localhost)
    :param log_type: Log type (e.g., 'System', 'Security', 'Application')
    :param num_records: Number of most recent records to fetch
    """
    try:
        hand = win32evtlog.OpenEventLog(server, log_type)

        # Flags: read backwards (newest first)
        flags = win32evtlog.EVENTLOG_BACKWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ

        # Collect events
        events = win32evtlog.ReadEventLog(hand, flags, 0)
        logs = []
        count = 0

        for event in events:
            logs.append({
                "EventID": event.EventID,
                "Source": event.SourceName,
                "Time": str(event.TimeGenerated),
                "Category": event.EventCategory,
                "Record": event.RecordNumber,
                "EventType": event.EventType,
                "Message": event.StringInserts
            })
            count += 1
            if count >= num_records:
                break

        # Save to JSON file
        filename = f"{log_type.lower()}_logs.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(logs, f, indent=4)

        print(f"✅ Saved {count} {log_type} log records to {filename}")

    except Exception as e:
        print(f"Error reading {log_type} logs: {e}")


if __name__ == "__main__":
    read_and_save_logs(log_type="System")
    read_and_save_logs(log_type="Security")
    read_and_save_logs(log_type="Application")
