#!/usr/bin/env python3
import argparse
import datetime
import os
import shutil
import subprocess
import sys
import yaml

try:
    from generate_index import update_index
except ImportError:
    update_index = None

def get_git_commit() -> str:
    """Returns current git commit hash if inside a repository."""
    try:
        return subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], 
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "not_a_git_repo"

def parse_parameters(param_list: list) -> dict:
    """Converts a list of key=val strings into a formatted dictionary."""
    params = {}
    if not param_list:
        return params
    for item in param_list:
        if "=" in item:
            key, val = item.split("=", 1)
            try:
                # Convert numbers automatically to floats or ints
                val = float(val) if "." in val else int(val)
            except ValueError:
                pass
            params[key] = val
    return params

def create_markdown_note(notes_dir: str, run_id: str, manifest: dict, data_dir: str):
    """Generates a pre-filled Markdown note stub for the simulation run."""
    os.makedirs(notes_dir, exist_ok=True)
    note_path = os.path.join(notes_dir, f"{run_id}.md")
    
    # SAFEGUARD: Do not overwrite existing notes if the script is re-run
    if os.path.exists(note_path):
        print(f"[!] Note already exists at {note_path}, skipping creation.")
        return

    # Format parameter list into Markdown bullets
    params = manifest.get("parameters", {})
    param_bullets = "\n".join([f"* **{k}:** {v}" for k, v in params.items()]) if params else "* None"
    
    abs_data_path = os.path.abspath(os.path.join(data_dir, run_id))
    abs_fig_path = os.path.join(abs_data_path, "figures")

    content = f"""---
run_id: {run_id}
date: {manifest['date_started']}
script: {manifest['source_script']}
data_location: {abs_data_path}
tags:
  - lammps_run
---

# Run: {run_id}

## Purpose & Hypothesis
<!-- Write what you are testing here -->


## Key Parameters
{param_bullets}

## Results & Figures
<!-- Link plots saved in data storage -->
<!-- Example: ![Plot](file://{abs_fig_path}/density.png) -->


## Observations & Conclusions
<!-- Document your findings here -->

"""

    with open(note_path, "w") as f:
        f.write(content)
    print(f"[+] Created Markdown note stub: {note_path}")

def open_in_editor(file_path: str):
    """Opens the generated note using $EDITOR or defaults to Neovim."""
    # Respect system $EDITOR env variable, falling back to 'nvim'
    editor = os.environ.get("EDITOR", "nvim")
    
    try:
        print(f"[+] Opening {file_path} in {editor}...")
        subprocess.run([editor, file_path])
    except FileNotFoundError:
        print(f"[-] Could not find editor '{editor}'. Is it installed?")

def main():
    parser = argparse.ArgumentParser(description="LAMMPS Simulation Launcher & Manifest Generator")
    parser.add_argument("-s", "--script", required=True, help="Path to base LAMMPS input script")
    parser.add_argument("-d", "--data-dir", default="./data_store", help="Target heavy storage directory")
    parser.add_argument("-r", "--run-id", help="Custom Run ID (default: timestamped)")
    parser.add_argument("-p", "--params", nargs="*", help="Parameters passed to LAMMPS as variables (e.g. temp=300 press=1.0)")
    parser.add_argument("--lmp-exec", default="lmp_serial", help="LAMMPS binary execution command")
    parser.add_argument("-n", "--notes-dir", default="./notes/runs", help="Path to Markdown ELN notes directory")
    parser.add_argument("--open", action="store_true", help="Open markdown note in Neovim immediately")
    args = parser.parse_args()

    # 1. Setup metadata & paths
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    run_id = args.run_id if args.run_id else f"run_{timestamp}"
    params = parse_parameters(args.params)
    
    run_dir = os.path.abspath(os.path.join(args.data_dir, run_id))
    os.makedirs(run_dir, exist_ok=True)
    os.makedirs(os.path.join(run_dir, "figures"), exist_ok=True)

    # 2. Copy source script to execution directory
    src_script = os.path.abspath(args.script)
    dest_script_path = os.path.join(run_dir, "in.lammps")
    shutil.copy2(src_script, dest_script_path)

    # 3. Write initial manifest
    manifest_path = os.path.join(run_dir, "manifest.yaml")
    manifest = {
        "run_id": run_id,
        "date_started": datetime.datetime.now().isoformat(timespec='seconds'),
        "git_commit": get_git_commit(),
        "source_script": src_script,
        "parameters": params,
        "status": "running",
    }
    with open(manifest_path, "w") as f:
        yaml.dump(manifest, f, sort_keys=False)
    
    note_path = os.path.join(args.notes_dir, "runs", f"{run_id}.md")
    create_markdown_note(args.notes_dir, run_id, manifest, args.data_dir)

    # UPDATE INDEX: Shows the run as "Running" in index.md
    if update_index:
        update_index(data_dir=args.data_dir, notes_dir=args.notes_dir)

    # 4. Construct LAMMPS execution command (passes parameters via -var)
    lmp_cmd = [args.lmp_exec, "-in", "in.lammps"]
    for k, v in params.items():
        lmp_cmd.extend(["-var", str(k), str(v)])

    print(f"[+] Launching {run_id}")
    print(f"[+] Run folder: {run_dir}")

    # 5. Execute LAMMPS in the run directory
    try:
        with open(os.path.join(run_dir, "stdout.log"), "w") as stdout, \
             open(os.path.join(run_dir, "stderr.log"), "w") as stderr:
            subprocess.run(lmp_cmd, cwd=run_dir, stdout=stdout, stderr=stderr, check=True)
        
        manifest["status"] = "completed"
        manifest["date_finished"] = datetime.datetime.now().isoformat(timespec='seconds')
        print("[+] Simulation finished successfully.")

    except subprocess.CalledProcessError as e:
        manifest["status"] = "failed"
        manifest["error"] = f"LAMMPS exited with code {e.returncode}"
        print(f"[-] Run failed! Check stderr.log in {run_dir}", file=sys.stderr)

    finally:
        # Update manifest with final run status
        with open(manifest_path, "w") as f:
            yaml.dump(manifest, f, sort_keys=False)
        # UPDATE INDEX: Marks the run as "Completed" or "Failed" in index.md
        if update_index:
            update_index(data_dir=args.data_dir, notes_dir=args.notes_dir)
        if args.open:
            open_in_editor(note_path)
    

if __name__ == "__main__":
    main()
