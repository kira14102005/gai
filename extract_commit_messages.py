import os
import subprocess
import sys

TARGET_FILE = r"D:\HarshitPC\Projects\commits.txt"

def append_commit_messages(target_file=TARGET_FILE):
    try:
        os.makedirs(os.path.dirname(target_file), exist_ok=True)

        result = subprocess.run(
            ["git", "log", "--pretty=format:%s"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            check=True
        )

        with open(target_file, "a", encoding="utf-8") as f:
            f.write(f"--- Repository: {os.path.basename(os.getcwd())} ---\n")
            f.write(result.stdout)
            f.write("\n\n")

        print(f"Successfully appended commits to '{target_file}'.")

    except subprocess.CalledProcessError:
        print("Error: Ensure you are running this inside a valid Git repository.", file=sys.stderr)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)

if __name__ == "__main__":
    append_commit_messages()