import os
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from notion_client import Client

load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("NOTION_DBID_Time_Tracker")

notion = Client(auth=NOTION_TOKEN)

def insert_datetime_range_entry():
    try:
        # Example: Tehran timezone (+03:30) or UTC
        tz = timezone(timedelta(hours=3, minutes=30))
        
        # Start time: Current time
        start_dt = datetime.now(tz)
        # End time: 1 hour and 30 minutes later
        end_dt = start_dt + timedelta(hours=1, minutes=30)
        
        start_iso = start_dt.isoformat()
        end_iso = end_dt.isoformat()
        
        new_page = notion.pages.create(
            parent={"database_id": DATABASE_ID},
            properties={
                "Name": {
                    "title": [
                        {"text": {"content": "Work Session with Start & End Time"}}
                    ]
                },
                "Description": {
                    "rich_text": [
                        {"text": {"content": "Testing date range with start & end timestamps."}}
                    ]
                },
                "MDuration": {
                    "number": 90
                },
                "Date": {
                    "date": {
                        "start": start_iso,
                        "end": end_iso
                    }
                },
                "Satisfaction": {
                    "select": {
                        "name": "عالی"
                    }
                }
            }
        )
        
        print("Success! Row with datetime range inserted into Notion.")
        print(f"Start: {start_iso}")
        print(f"End:   {end_iso}")
        print(f"Page URL: {new_page['url']}")
        
    except Exception as e:
        print("Error creating page:", e)

if __name__ == "__main__":
    insert_datetime_range_entry()