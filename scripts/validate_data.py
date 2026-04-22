import os
import pandas as pd

def validate_csvs(directory):
    print(f"Validating CSVs in {directory}...")
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".csv"):
                filepath = os.path.join(root, file)
                try:
                    df = pd.read_csv(filepath)
                    if df.empty:
                        print(f"  [WARNING] {filepath} is empty")
                    else:
                        print(f"  [OK] {filepath} - {len(df)} rows")
                except Exception as e:
                    print(f"  [ERROR] {filepath} failed to load: {e}")

if __name__ == "__main__":
    validate_csvs("data")
