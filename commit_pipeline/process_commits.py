import json
import os
import sys

INPUT_FILE = r"D:\HarshitPC\Projects\commit-aid\commit_pipeline\data\commits.txt"
OUTPUT_JSON = r"D:\HarshitPC\Projects\commit-aid\commit_pipeline\data\commits_messages.json"

def process_commits(input_file=INPUT_FILE, output_file=OUTPUT_JSON):
    try:
        # Check if the target file exists
        if not os.path.exists(input_file):
            print(f"Error: Input file '{input_file}' not found.", file=sys.stderr)
            return

        commit_list = []
        unique_tags = set()

        # Read lines from commits.txt
        with open(input_file, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        for line in lines:
            line = line.strip()
            
            if not line or line.startswith("---"):
                continue

            if ":" in line:
                tag, message = line.split(":", 1)
                tag = tag.strip().lower()  # Normalize tags to lowercase
                message = message.strip()
            else:
                continue  # Skip lines that don't have a tag

            unique_tags.add(tag)
            commit_list.append({
                "tag": tag,
                "message": message
            })

        # Ensure target directory exists
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        # 1. Save formatted JSON output
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(commit_list, f, indent=2, ensure_ascii=False)

        print(f"--- Unique Tags Found ({len(unique_tags)}) ---")
        print(sorted(list(unique_tags)))
        print(f"\nSuccessfully generated '{output_file}' with {len(commit_list)} commit entries.")

    except Exception as e:
        print(f"An error occurred: {e}", file=sys.stderr)

if __name__ == "__main__":
    process_commits()