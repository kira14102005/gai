import shutil
import subprocess
from pathlib import Path


def extract_commits(repo_path: str, output_file: str):
    """Extracts commit messages and diffs from target repo and appends them to commits.txt"""
    repo_path = Path(repo_path)
    output_file = Path(output_file)

    if not repo_path.is_dir():
        raise FileNotFoundError(f"Repository path '{repo_path}' does not exist.")

    git_executable = shutil.which("git")
    if git_executable is None:
        raise RuntimeError("Git is not installed or is not on PATH.")

    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Get list of commit hashes and commit subjects
    hashes_output = subprocess.check_output(  # noqa: S603
        [git_executable, "log", "--pretty=format:%H%x1f%s"],
        cwd=repo_path,
        encoding="utf-8",
        errors="ignore",
    )

    repo_name = repo_path.resolve().name

    with output_file.open("a", encoding="utf-8") as f:
        f.write(f"\n--- Repository: {repo_name} ---\n")

        for line in hashes_output.strip().splitlines():
            if not line.strip():
                continue

            parts = line.split("\x1f", 1)
            commit_hash = parts[0]
            subject = parts[1] if len(parts) > 1 else ""

            # Fetch diff for the specific commit
            diff_output = subprocess.check_output(  # noqa: S603
                [git_executable, "show", "--format=", commit_hash],
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
