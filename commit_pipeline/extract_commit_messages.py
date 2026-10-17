import os
import subprocess


def extract_commits(repo_path: str, output_file: str):
    """Extracts commit messages and diffs from target repo and appends them to commits.txt"""
    if not os.path.isdir(repo_path):
        raise FileNotFoundError(f"Repository path '{repo_path}' does not exist.")

    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    # Get list of commit hashes and commit subjects
    hashes_output = subprocess.check_output(
        ["git", "log", "--pretty=format:%H%x1f%s"],
        cwd=repo_path,
        encoding="utf-8",
        errors="ignore",
    )

    repo_name = os.path.basename(os.path.abspath(repo_path))

    with open(output_file, "a", encoding="utf-8") as f:
        f.write(f"\n--- Repository: {repo_name} ---\n")

        for line in hashes_output.strip().splitlines():
            if not line.strip():
                continue

            parts = line.split("\x1f", 1)
            commit_hash = parts[0]
            subject = parts[1] if len(parts) > 1 else ""

            # Fetch diff for the specific commit
            diff_output = subprocess.check_output(
                ["git", "show", "--format=", commit_hash],
                cwd=repo_path,
                encoding="utf-8",
                errors="ignore",
            )

            # Delimited block for easy parsing
            f.write("<<<COMMIT_START>>>\n")
            f.write(f"{subject}\n")
            f.write("<<<DIFF_START>>>\n")
            f.write(f"{diff_output}\n")
            f.write("<<<COMMIT_END>>>\n\n")

    print(
        f"[1/2 Extract] Appended commits with diffs from '{repo_name}' to '{output_file}'"
    )
