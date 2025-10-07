import win32evtlog  # pip install pywin32
import json

def read_and_save_with_metadata(server="localhost", log_type="System", num_records=100):
    """
    Reads Windows Event Logs (newest first), saves up to num_records into <log>_logs.json,
    and includes a 'metadata' section with timeframe + count.
    """
    try:
        hand = win32evtlog.OpenEventLog(server, log_type)
        flags = win32evtlog.EVENTLOG_BACKWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ

        logs = []
        count = 0

        # Read in batches until we collect num_records or run out
        while count < num_records:
            batch = win32evtlog.ReadEventLog(hand, flags, 0)
            if not batch:
                break
            for event in batch:
                # Convert inserts (can be None) to a list for JSON safety
                inserts = list(event.StringInserts) if event.StringInserts else []

                logs.append({
                    "EventID": event.EventID,
                    "Source": event.SourceName,
                    "Time": str(event.TimeGenerated),
                    "Category": event.EventCategory,
                    "Record": event.RecordNumber,
                    "EventType": event.EventType,
                    "Message": inserts
                })
                count += 1
                if count >= num_records:
                    break

        # Build metadata using the collected (subset) logs
        if logs:
            newest_time = logs[0]["Time"]      # because we read newest first
            oldest_time = logs[-1]["Time"]     # last one is the oldest in this saved set
        else:
            newest_time = "N/A"
            oldest_time = "N/A"

        out = {
            "metadata": {
                "log_type": log_type,
                "total_records_saved": len(logs),
                "oldest_log": oldest_time,
                "newest_log": newest_time
            },
            "events": logs
        }

        filename = f"{log_type.lower()}_logs.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=4)

        print(f"✅ {log_type}: saved {len(logs)} records to {filename}")
        if logs:
            print(f"   timeframe → {oldest_time}  to  {newest_time}")
        else:
            print("   (no records saved)")

    except Exception as e:
        # Friendlier message for Security log privilege issues
        msg = str(e)
        if "A required privilege is not held by the client" in msg or "OpenEventLogW" in msg:
            print(f"⚠️  {log_type}: need Administrator privileges to read this log.")
        else:
            print(f"Error reading {log_type} logs: {e}")


if __name__ == "__main__":
    # Adjust num_records as you like
    read_and_save_with_metadata(log_type="System", num_records=100)
    read_and_save_with_metadata(log_type="Security", num_records=100)
    read_and_save_with_metadata(log_type="Application", num_records=100)
