# src/collector_to_sqlite.py
import win32evtlog  # pip install pywin32
from shared.storage import insert_events
from datetime import datetime

def read_latest(server="localhost", log_type="System", num_records=200):
    """
    Reads newest-first events from a Windows log and returns a list[dict].
    """
    hand = win32evtlog.OpenEventLog(server, log_type)
    flags = win32evtlog.EVENTLOG_BACKWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ
    out, count = [], 0
    while count < num_records:
        batch = win32evtlog.ReadEventLog(hand, flags, 0)
        if not batch:
            break
        for event in batch:
            inserts = list(event.StringInserts) if event.StringInserts else []
            out.append({
                "EventID": event.EventID,
                "Source": event.SourceName,
                "Time": str(event.TimeGenerated),  # already stringy
                "Category": event.EventCategory,
                "Record": event.RecordNumber,
                "EventType": event.EventType,
                "Message": inserts
            })
            count += 1
            if count >= num_records:
                break
    return out

if __name__ == "__main__":
    # You can adjust counts; run elevated to capture Security.
    for lt in ("System", "Security", "Application"):
        try:
            events = read_latest(log_type=lt, num_records=500)
            inserted = insert_events(lt, events)
            print(f"✅ {lt}: inserted {inserted} new rows into events.db")
        except Exception as e:
            print(f"⚠️  {lt}: {e}")
