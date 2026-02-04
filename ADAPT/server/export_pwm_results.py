import sqlite3
import os

# 1. Define the input database and the target packages
db_file = 'results.db'

target_packages = [
    "com.google.android.gms", 
    "com.callpod.android_apps.keeper", 
    "com.lastpass.lpandroid",
    "com.authenticator.app.starnest", 
    "com.x8bit.bitwarden",
    "com.nordpass.android.app.password.manager",
    "authenticator.app.otp.mfa.password.manager.private.browser",
    "com.onepassword.android",
    "com.avira.passwordmanager",
    "com.siber.roboform"
]

columns_to_select = [
    "pwm_package",
    "browser_package", 
    "test_number", 
    "repetition", 
    "a_username_final", 
    "a_password_final", 
    "b_username_final", 
    "b_password_final",  
    "a_username_suggested", 
    "a_password_suggested", 
    "b_username_suggested", 
    "b_password_suggested", 
    "autofill_response"
]

def export_results_numerical_sort():
    if not os.path.exists(db_file):
        print(f"Error: Database file '{db_file}' not found.")
        return

    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()

        for package_folder_name in target_packages:
            # Create output directory
            output_dir = os.path.join("pwm_test_results", package_folder_name)
            os.makedirs(output_dir, exist_ok=True)
            output_file = os.path.join(output_dir, "results.txt")

            # Construct query columns
            cols_query = ", ".join(columns_to_select)
            
            # Query logic:
            # We CAST test_number AS INTEGER in the ORDER BY clause
            # to ensure 2 comes before 10.
            query = f"""
                SELECT {cols_query} 
                FROM autofill_results 
                WHERE pwm_package LIKE ?
                ORDER BY 
                    browser_package ASC, 
                    CAST(test_number AS INTEGER) ASC, 
                    repetition ASC
            """
            
            cursor.execute(query, (f'%{package_folder_name}%',))
            rows = cursor.fetchall()

            if not rows:
                print(f"Skipping: {package_folder_name} (0 entries found).")
                continue

            # --- ALIGNMENT LOGIC ---

            # 1. Start column widths based on Header lengths
            col_widths = [len(col) for col in columns_to_select]

            # 2. Convert rows to string and calculate max widths
            processed_rows = []
            for row in rows:
                str_row = [str(item) if item is not None else "NULL" for item in row]
                processed_rows.append(str_row)
                
                for i, value in enumerate(str_row):
                    col_widths[i] = max(col_widths[i], len(value))

            # 3. Add padding (+3 spaces)
            final_col_widths = [w + 3 for w in col_widths]

            # 4. Create format string
            fmt = "".join([f"{{:<{w}}}" for w in final_col_widths])

            # --- WRITING TO FILE ---
            
            with open(output_file, 'w', encoding='utf-8') as f:
                # Header
                f.write(fmt.format(*columns_to_select) + "\n")
                
                # Separator
                separator = ["-" * w for w in col_widths]
                f.write(fmt.format(*separator) + "\n")

                # Rows
                for row in processed_rows:
                    f.write(fmt.format(*row) + "\n")
            
            print(f"Processed: {package_folder_name} -> {len(rows)} entries.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    export_results_numerical_sort()