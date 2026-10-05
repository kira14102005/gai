import argparse
import os
import sys

from .extract_commit_messages import extract_commits
from .process_commits import process_commits

# Default paths
BASE_DATA_DIR = r"D:\HarshitPC\Projects\commit-aid\data"
DEFAULT_TXT = os.path.join(BASE_DATA_DIR, "commits.txt")
DEFAULT_JSON = os.path.join(BASE_DATA_DIR, "commits_messages.json")


def run_pipeline(repo_path: str, txt_file: str = DEFAULT_TXT, json_file: str = DEFAULT_JSON):
    print(f"\n=== Starting Pipeline for Repo: {repo_path} ===")
    try:
        # Step 1: Extract raw commits
        extract_commits(repo_path=repo_path, output_file=txt_file)

        # Step 2: Process raw commits to JSON
        process_commits(input_file=txt_file, output_json=json_file)

        print("=== Pipeline Execution Complete! ===\n")

    except Exception as e:
        print(f"Pipeline failed: {e}", file=sys.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract and process Git commits into structured JSON.")
    parser.add_argument("repo_path", nargs="?", default=os.getcwd(), help="Target Git repository path")
    parser.add_argument("--txt", default=DEFAULT_TXT, help="Custom target commits.txt path")
    parser.add_argument("--json", default=DEFAULT_JSON, help="Custom target commits_messages.json path")

    args = parser.parse_args()
    run_pipeline(repo_path=args.repo_path, txt_file=args.txt, json_file=args.json)