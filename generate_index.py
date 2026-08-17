#!/usr/bin/env python3
import argparse
import datetime
import glob
import os
import yaml

def scan_manifests(data_dir: str) -> list:
    """Finds and parses all manifest.yaml files recursively inside data_dir."""
    manifest_paths = glob.glob(os.path.join(data_dir, "**", "manifest.yaml"), recursive=True)
    manifests = []

    for path in manifest_paths:
        try:
            with open(path, "r") as f:
                data = yaml.safe_load(f)
                if isinstance(data, dict):
                    manifests.append(data)
        except Exception as e:
            print(f"[!] Warning: Failed to read {path}: {e}")

    # Sort runs newest first by start date
    manifests.sort(key=lambda x: x.get("date_started", ""), reverse=True)
    return manifests

def format_params(params: dict) -> str:
    """Formats parameter dictionary into a clean inline string."""
    if not params or not isinstance(params, dict):
        return "-"
    return ", ".join([f"`{k}={v}`" for k, v in params.items()])

def generate_markdown(manifests: list, notes_dir: str) -> str:
    """Builds the Markdown index table string."""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    
    status_badge = {
        "completed": "✅ Completed",
        "running": "⏳ Running",
        "failed": "❌ Failed"
    }

    lines = [
        "# Master Experiment Index",
        "",
        f"*Last updated: {now} | Total simulations logged: {len(manifests)}*",
        "",
        "| Run ID | Date Started | Status | Parameters | Note File |",
        "| :--- | :--- | :---: | :--- | :---: |"
    ]

    for m in manifests:
        run_id = m.get("run_id", "N/A")
        date_started = m.get("date_started", "N/A").replace("T", " ")
        status = status_badge.get(m.get("status"), m.get("status", "Unknown"))
        params = format_params(m.get("parameters", {}))
        
        # Check if corresponding Markdown note file exists
        note_filename = f"{run_id}.md"
        note_path = os.path.join(notes_dir, "runs", note_filename)
        
        if os.path.exists(note_path):
            note_link = f"[{run_id}](runs/{note_filename})"
        else:
            note_link = "—"

        lines.append(f"| `{run_id}` | {date_started} | {status} | {params} | {note_link} |")

    lines.append("")
    return "\n".join(lines)


def update_index(data_dir: str = "./data_store", notes_dir: str = "./notes", output: str = "index.md"):
    """Scans manifest files and regenerates the Master Markdown index."""
    manifests = scan_manifests(data_dir)
    markdown_content = generate_markdown(manifests, notes_dir)
    
    output_path = os.path.join(notes_dir, output)
    os.makedirs(notes_dir, exist_ok=True)
    
    with open(output_path, "w") as f:
        f.write(markdown_content)
    print(f"[+] Master index updated at {output_path}")

def main():
    parser = argparse.ArgumentParser(description="Build Master Markdown Index from manifest files.")
    parser.add_argument("-d", "--data-dir", default="./data_store", help="Path to data storage root")
    parser.add_argument("-n", "--notes-dir", default="./notes", help="Path to Neovim Markdown notes root")
    parser.add_argument("-o", "--output", default="index.md", help="Filename of the master index")

    args = parser.parse_args()

    manifests = scan_manifests(args.data_dir)
    markdown_content = generate_markdown(manifests, args.notes_dir)

    output_path = os.path.join(args.notes_dir, args.output)
    os.makedirs(args.notes_dir, exist_ok=True)

    with open(output_path, "w") as f:
        f.write(markdown_content)

    print(f"[+] Master index written to {output_path} ({len(manifests)} runs found)")

if __name__ == "__main__":
    main()
