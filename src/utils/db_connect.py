import os
import time
import pyodbc
from dotenv import load_dotenv

load_dotenv()

_RETRY_DELAYS = [5, 15, 30]  # seconds between retries (Azure SQL cold-start can take ~20s)


def get_connection():
    driver = os.getenv("AZURE_SQL_DRIVER", "ODBC Driver 18 for SQL Server")
    conn_str = (
        f"DRIVER={{{driver}}};"
        f"SERVER={os.environ['AZURE_SQL_SERVER']};"
        f"DATABASE={os.environ['AZURE_SQL_DATABASE']};"
        f"UID={os.environ['AZURE_SQL_USERNAME']};"
        f"PWD={os.environ['AZURE_SQL_PASSWORD']};"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
        "Connection Timeout=30;"
    )
    last_err = None
    for attempt, delay in enumerate([0] + _RETRY_DELAYS, start=1):
        if delay:
            print(f"[db] Azure SQL cold-start detected — retrying in {delay}s (attempt {attempt}/4)...")
            time.sleep(delay)
        try:
            return pyodbc.connect(conn_str)
        except pyodbc.OperationalError as e:
            last_err = e
    raise last_err
