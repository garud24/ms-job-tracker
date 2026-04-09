# check_jobs.py
import os
import json
import hashlib
from pathlib import Path

import requests

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# Separate state files for each search
TOP10_IC2_FILE = Path("top10_ic2.txt")
TOP10_SWE_FILE = Path("top10_swe.txt")

# IC2 search (API version of your existing URL)
SEARCH_URL_IC2 = (
    "https://apply.careers.microsoft.com/api/pcsx/search"
    "?domain=microsoft.com"
    "&query=IC2"
    "&location=United%20States"
    "&start=0"
    "&sort_by=timestamp"
    "&filter_include_remote=1"
)

# Software Engineer search (based on your new URL)
SEARCH_URL_SWE = (
    "https://apply.careers.microsoft.com/api/pcsx/search"
    "?domain=microsoft.com"
    "&query=Software%20Engineer"
    "&location=United%20States"
    "&start=0"
    "&sort_by=timestamp"
    "&filter_include_remote=1"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (job-watcher-bot)",
    "Accept": "application/json",
}


def find_jobs_list(node):
    if isinstance(node, list):
        if node and all(isinstance(x, dict) for x in node):
            return node
        for item in node:
            found = find_jobs_list(item)
            if found:
                return found
    elif isinstance(node, dict):
        for value in node.values():
            found = find_jobs_list(value)
            if found:
                return found
    return None

def fetch_top_n_jobs(search_url, label, top_n=10):
    try:
        resp = requests.get(search_url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[{label}] Error fetching jobs: {e}")
        return []

    jobs = find_jobs_list(data)
    if not jobs:
        print(f"[{label}] No jobs found")
        return []

    result = []

    for job in jobs[:top_n]:
        job_id = str(job.get("jobId") or job.get("id") or "").strip()
        if not job_id:
            job_id = hashlib.md5(str(job).encode()).hexdigest()

        title = job.get("title") or job.get("jobTitle") or "Unknown title"
        location = job.get("location") or job.get("primaryLocation") or "Unknown location"
        url = job.get("url") or job.get("detailsUrl") or job.get("jobUrl") or ""

        result.append({
            "id": job_id,
            "title": title,
            "location": location,
            "url": url,
        })

    return result

def send_telegram_message(text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    r = requests.post(
        url,
        json={"chat_id": TELEGRAM_CHAT_ID, "text": text},
        timeout=20,
    )
    r.raise_for_status()

def commit_if_changed():
    import subprocess

    subprocess.run(["git", "config", "user.name", "github-actions[bot]"], check=True)
    subprocess.run(
        ["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"],
        check=True
    )

    status = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=True
    )

    if not status.stdout.strip():
        print("No changes to commit")
        return

    subprocess.run(["git", "add", "top10_ic2.txt", "top10_swe.txt"], check=True)
    subprocess.run(["git", "commit", "-m", "Update tracked top 10 jobs"], check=True)
    subprocess.run(["git", "push"], check=True)

def get_saved_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {line.strip() for line in path.read_text().splitlines() if line.strip()}

def save_current_top10(path: Path, job_ids: list[str]):
    path.write_text("\n".join(job_ids) + "\n")
    
def check_search(label, search_url, state_file, top_n=10):
    jobs = fetch_top_n_jobs(search_url, label, top_n=top_n)
    if not jobs:
        return

    previous_ids = get_saved_ids(state_file)
    current_ids = [job["id"] for job in jobs]

    new_jobs = [job for job in jobs if job["id"] not in previous_ids]

    if new_jobs:
        for job in reversed(new_jobs):
            msg = (
                f"🚨 New {label} job found\n\n"
                f"{job['title']}\n"
                f"{job['location']}\n"
                f"{job['url']}"
            )
            send_telegram_message(msg)

        print(f"[{label}] Found {len(new_jobs)} new jobs")
    else:
        print(f"[{label}] No new jobs in current top {top_n}")

    # replace old saved top 10 with the current top 10
    save_current_top10(state_file, current_ids)

def main():
    check_search("IC2", SEARCH_URL_IC2, TOP10_IC2_FILE, top_n=10)
    check_search("Software Engineer", SEARCH_URL_SWE, TOP10_SWE_FILE, top_n=10)
    commit_if_changed()


if __name__ == "__main__":
    main()