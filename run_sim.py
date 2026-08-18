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
                val = float(val) if "." in val else int(val)
            except ValueError:
                pass
            params[key] = val
    return params

def resolve_notebook_path(run_id: str, notebook_arg: str, notebooks_dir: str) -> str:
    """Determines the path of the associated Quarto notebook."""
    if notebook_arg:
        return notebook_arg
    
    # Auto-detect standard notebook extensions if user didn't specify one
    for ext in [".qmd", ".ipynb", ".md"]:
        candidate = os.path.join(notebooks_dir, f"{run_id}{ext}")
        if os.path.exists(candidate):
            return candidate
            
    # Default fallback path assuming it will be created as .qmd
    return os.path.join(notebooks_dir, f"{run_id}.qmd")

def main():
    parser = argparse.ArgumentParser(description="LAMMPS Simulation Launcher & Manifest Generator")
    parser.add_argument("-s", "--script", required=True, help="Path to base LAMMPS input script")
    parser.add_argument("-d", "--data-dir", default="./data", help="Target heavy storage directory")
    parser.add_argument("-r", "--run-id", help="Custom Run ID (default: timestamped)")
    parser.add_argument("-p", "--params", nargs="*", help="Parameters passed to LAMMPS as variables (e.g. temp=300 press=1.0)")
    parser.add_argument("--lmp-exec", default="lmp_serial", help="LAMMPS binary execution command")
    parser.add_argument("-nb", "--notebook", help="Path to the Quarto notebook file running/analyzing this sim")
    parser.add_argument("--notebooks-dir", default="./notebooks", help="Directory where Quarto notebooks are stored")
    parser.add_argument("--index-path", default="index_sim.qmd", help="Path to Master Index markdown file")
    
    args = parser.parse_args()

    # 1. Setup metadata & paths
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    run_id = args.run_id if args.run_id else f"run_{timestamp}"
    params = parse_parameters(args.params)
    notebook_path = resolve_notebook_path(run_id, args.notebook, args.notebooks_dir)
    
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
        "notebook": notebook_path,
        "parameters": params,
        "status": "running",
    }
    with open(manifest_path, "w") as f:
        yaml.dump(manifest, f, sort_keys=False)

    # Update index as "Running"
    if update_index:
        update_index(data_dir=args.data_dir, notebooks_dir=args.notebooks_dir, output=args.index_path)

    # 4. Construct LAMMPS command
    lmp_cmd = [args.lmp_exec, "-in", "in.lammps"]
    for k, v in params.items():
        lmp_cmd.extend(["-var", str(k), str(v)])

    print(f"[+] Launching {run_id}")
    print(f"[+] Run folder: {run_dir}")

    # 5. Execute LAMMPS
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
        with open(manifest_path, "w") as f:
            yaml.dump(manifest, f, sort_keys=False)
        if update_index:
            update_index(data_dir=args.data_dir, notebooks_dir=args.notebooks_dir, output=args.index_path)

if __name__ == "__main__":
    main()
