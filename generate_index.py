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

    manifests.sort(key=lambda x: x.get("date_started", ""), reverse=True)
    return manifests

def format_params(params: dict) -> str:
    """Formats parameter dictionary into a clean inline string."""
    if not params or not isinstance(params, dict):
        return "-"
    return ", ".join([f"`{k}={v}`" for k, v in params.items()])

def generate_markdown(manifests: list, notebooks_dir: str, output_path: str) -> str:
    """Builds the Master Index markdown string with links to Quarto notebooks."""
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
        "| Run ID | Date Started | Status | Parameters | Quarto Notebook |",
        "| :--- | :--- | :---: | :--- | :---: |"
    ]

    index_dir = os.path.dirname(os.path.abspath(output_path))

    for m in manifests:
        run_id = m.get("run_id", "N/A")
        date_started = m.get("date_started", "N/A").replace("T", " ")
        status = status_badge.get(m.get("status"), m.get("status", "Unknown"))
        params = format_params(m.get("parameters", {}))
        
        # Determine notebook location
        nb_path = m.get("notebook")
        
        # Fallback check inside notebooks_dir if not stored in manifest
        if not nb_path or not os.path.exists(nb_path):
            for ext in [".qmd", ".ipynb", ".md"]:
                candidate = os.path.join(notebooks_dir, f"{run_id}{ext}")
                if os.path.exists(candidate):
                    nb_path = candidate
                    break

        # Generate relative link to the notebook
        if nb_path and os.path.exists(nb_path):
            rel_link = os.path.relpath(nb_path, start=index_dir)
            nb_name = os.path.basename(nb_path)
            note_link = f"[{nb_name}]({rel_link})"
        else:
            note_link = "—"

        lines.append(f"| `{run_id}` | {date_started} | {status} | {params} | {note_link} |")

    lines.append("")
    return "\n".join(lines)

def update_index(data_dir: str = "./data", notebooks_dir: str = "./notebooks", output: str = "index.md"):
    """Scans manifest files and regenerates the Master Index markdown file."""
    manifests = scan_manifests(data_dir)
    markdown_content = generate_markdown(manifests, notebooks_dir, output)
    
    os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
    with open(output, "w") as f:
        f.write(markdown_content)
    print(f"[+] Master index updated at {output}")

def main():
    parser = argparse.ArgumentParser(description="Build Master Markdown Index from manifest files.")
    parser.add_argument("-d", "--data-dir", default="./data", help="Path to data storage root")
    parser.add_argument("-nb", "--notebooks-dir", default="./notebooks", help="Path to Quarto notebooks directory")
    parser.add_argument("-o", "--output", default="index.md", help="Path of the master index file")

    args = parser.parse_args()
    update_index(data_dir=args.data_dir, notebooks_dir=args.notebooks_dir, output=args.output)

if __name__ == "__main__":
    main()
