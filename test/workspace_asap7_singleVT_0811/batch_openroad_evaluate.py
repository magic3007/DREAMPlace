#!/usr/bin/env python3

import os
import sys
import argparse
import subprocess
import glob
from multiprocessing import Pool

def run_evaluation(command):
    """
    Worker function to run a single OpenROAD evaluation command.
    """
    case_name = os.path.basename(command[-1]).split('.')[0]
    print(f"Starting OpenROAD evaluation for: {case_name}")
    try:
        # Using subprocess.run and capturing output to keep parallel logs clean.
        result = subprocess.run(
            command,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        if result.returncode != 0:
            print(f"--- Error for case {case_name} ---", file=sys.stderr)
            print(result.stdout, file=sys.stderr)
            print(result.stderr, file=sys.stderr)
            print(f"--- End of error for case {case_name} ---", file=sys.stderr)
            return f"Error in {case_name} (code: {result.returncode})"
        else:
            print(f"Successfully processed {case_name}.")
            # Optionally print stdout on success if needed
            # print(result.stdout)
            return f"Success for {case_name}"
    except FileNotFoundError:
        error_msg = f"Error: '{command[0]}' not found for case {case_name}."
        print(error_msg, file=sys.stderr)
        return error_msg
    except Exception as e:
        error_msg = f"An unexpected error occurred for case {case_name}: {e}"
        print(error_msg, file=sys.stderr)
        return error_msg

def main():
    """
    Main function to batch run OpenROAD evaluation in parallel.
    """
    parser = argparse.ArgumentParser(
        description='Batch run OpenROAD evaluation for multiple cases in parallel.',
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('sdc_root', help='Root directory for SDC files of all cases.')
    parser.add_argument('def_results_root', help='Root directory for DEF file results of all cases.')
    parser.add_argument('-j', '--jobs', type=int, default=8, help='Number of parallel jobs to run. (default: 8)')
    args = parser.parse_args()

    sdc_root = os.path.abspath(args.sdc_root)
    def_results_root = os.path.abspath(args.def_results_root)

    if not os.path.isdir(sdc_root):
        print(f"Error: SDC root directory not found at {sdc_root}", file=sys.stderr)
        return 1

    if not os.path.isdir(def_results_root):
        print(f"Error: DEF results root directory not found at {def_results_root}", file=sys.stderr)
        return 1

    script_dir = os.path.dirname(os.path.realpath(__file__))
    evaluator_script = os.path.join(script_dir, 'openroad_evaluate.py')

    if not os.path.isfile(evaluator_script):
        print(f"Error: openroad_evaluate.py not found at {evaluator_script}", file=sys.stderr)
        return 1
    
    print(f"Using evaluator script: {evaluator_script}")
    print(f"Running with {args.jobs} parallel jobs.")

    try:
        case_dirs = [d for d in os.listdir(def_results_root) if os.path.isdir(os.path.join(def_results_root, d))]
    except OSError as e:
        print(f"Error reading directory {def_results_root}: {e}", file=sys.stderr)
        return 1
    
    commands_to_run = []
    for case_dir_name in sorted(case_dirs):
        case_name = case_dir_name.split('.')[0]
        
        # Look for SDC file in the case directory
        sdc_files = glob.glob(os.path.join(sdc_root, '**', 'pnr', 'build', case_name, 'bookshelf', f'{case_name}.sdc'), recursive=True)
        
        # If no SDC files found in the case directory, try to find them in subdirectories
        if not sdc_files:
            print(f"Warning: No SDC file found for case {case_name} in {sdc_root}. Skipping.", file=sys.stderr)
            continue
        
        if len(sdc_files) > 1:
            print(f"Warning: Multiple SDC files found for case {case_name}. Using the first one: {sdc_files[0]}", file=sys.stderr)

        sdc_file_path = sdc_files[0]
        
        # Look for DEF file in the case directory
        search_dir = os.path.join(def_results_root, case_dir_name)
        def_files = glob.glob(os.path.join(search_dir, '**', f'{case_name}.def'), recursive=True)
        if not def_files:
            print(f"Warning: No '{case_name}.def' file found in {search_dir}. Skipping.", file=sys.stderr)
            continue
        
        if len(def_files) > 1:
            print(f"Warning: Multiple DEF files found for case {case_name}. Using the first one: {def_files[0]}", file=sys.stderr)

        def_file_path = def_files[0]
        
        command = [sys.executable, evaluator_script, sdc_file_path, def_file_path]
        commands_to_run.append(command)
        print(f"Queued OpenROAD evaluation for {case_name}: sdc: {sdc_file_path}, def: {def_file_path}")

    if not commands_to_run:
        print("No valid cases found to evaluate.")
        return 0
        
    print(f"\nStarting parallel OpenROAD evaluation for {len(commands_to_run)} cases...")
    
    with Pool(processes=args.jobs) as pool:
        results = pool.map(run_evaluation, commands_to_run)

    print("\n--- Batch OpenROAD Evaluation Summary ---")
    for res in results:
        print(res)
    print("------------------------------------------")
    
    print("\nBatch OpenROAD evaluation finished.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
