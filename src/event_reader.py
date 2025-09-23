import win32evtlog  # Requires: pip install pywin32

def read_event_logs(server="localhost", log_type="System", num_records=10):
    """
    Reads Windows Event Logs.
    :param server: Server name (default: localhost)
    :param log_type: Log type (e.g., 'System', 'Security', 'Application')
    :param num_records: Number of most recent records to fetch
    """
    try:
        hand = win32evtlog.OpenEventLog(server, log_type)

        # Total number of records
        total_records = win32evtlog.GetNumberOfEventLogRecords(hand)

        # Flags
        backwards_flags = win32evtlog.EVENTLOG_BACKWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ
        forwards_flags = win32evtlog.EVENTLOG_FORWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ

        # Newest event
        newest_event = win32evtlog.ReadEventLog(hand, backwards_flags, 0)
        newest_time = newest_event[0].TimeGenerated if newest_event else "N/A"

        # Oldest event
        oldest_event = win32evtlog.ReadEventLog(hand, forwards_flags, 0)
        oldest_time = oldest_event[0].TimeGenerated if oldest_event else "N/A"

        # Print timeframe info
        print(f"=== {log_type} Logs ===")
        print(f" Total Records: {total_records}")
        print(f" Oldest Log: {oldest_time}")
        print(f" Newest Log: {newest_time}\n")

        # Print recent records
        events = win32evtlog.ReadEventLog(hand, backwards_flags, 0)
        count = 0
        for event in events:
            print(f"Event ID: {event.EventID}, Source: {event.SourceName}")
            print(f"Time: {event.TimeGenerated}, Category: {event.EventCategory}")
            print(f"Record #: {event.RecordNumber}, Event Type: {event.EventType}")
            print(f"Message: {event.StringInserts}\n")

            count += 1
            if count >= num_records:
                break

    except Exception as e:
        print(f"Error reading {log_type} logs: {e}")


if __name__ == "__main__":
    print("=== System Logs ===")
    read_event_logs(log_type="System")

    print("\n=== Security Logs ===")
    read_event_logs(log_type="Security")

    print("\n=== Application Logs ===")
    read_event_logs(log_type="Application")
