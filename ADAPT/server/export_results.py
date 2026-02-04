import sqlite3
import os
from pathlib import Path

# --- Configuration ---
DB_PATH = 'results.db'
OUTPUT_BASE_DIR = 'test_results'
TABLE_NAME = 'autofill_results'  # <--- IMPORTANT: Change this to your actual table name

def export_data():
    # 1. Connect to the database
    if not os.path.exists(DB_PATH):
        print(f"Error: Database file '{DB_PATH}' not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # 2. Execute Query
        # We use GROUP BY to ensure we only pick one entry per browser/test combination.
        # SQLite will arbitrarily pick one row for the non-aggregated column (autofill_structure).
        query = f"""
            SELECT browser_package, test_number, autofill_structure 
            FROM {TABLE_NAME}
            GROUP BY browser_package, test_number
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        print(f"Found {len(rows)} unique records to export.")

        # 3. Iterate and Write Files
        for browser_package, test_number, content in rows:
            # Handle cases where data might be missing
            if not browser_package or not test_number:
                continue

            # Define the directory structure: test_results/{browser_package}/
            output_dir = Path(OUTPUT_BASE_DIR) / str(browser_package)
            output_dir.mkdir(parents=True, exist_ok=True)

            # Define the filename: test_{test_number}.json
            file_path = output_dir / f"test_{test_number}.json"

            # Write the content
            # We assume 'content' is already a string (JSON string). 
            # If it is None, we write an empty string or handle accordingly.
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(str(content) if content is not None else "")

        print("Export complete!")

    except sqlite3.OperationalError as e:
        print(f"SQL Error: {e}")
        print(f"Hint: Check if TABLE_NAME = '{TABLE_NAME}' is correct.")
    
    finally:
        conn.close()

if __name__ == '__main__':
    export_data()