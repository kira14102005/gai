import os
import subprocess
import sys

def extract_commits(repo_path: str, output_file: str):
    """Extracts commits from target repo and appends them to commits.txt"""
    if not os.path.isdir(repo_path):
        raise FileNotFoundError(f"Repository path '{repo_path}' does not exist.")

    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    # Fetch commits from target repo without changing current directory
    result = subprocess.run(
        ["git", "log", "--pretty=format:%s"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
        check=True
    )

    repo_name = os.path.basename(os.path.abspath(repo_path))

    with open(output_file, "a", encoding="utf-8") as f:
        f.write(result.stdout)
        f.write("\n\n")

    print(f"[1/2 Extract] Appended commits from '{repo_name}' to '{output_file}'")