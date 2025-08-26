#!/usr/bin/env python3

import os
import sys
import argparse
import glob
import re
import csv
import pandas as pd

def parse_innovus_log(log_path):
    """
    Parses a single Innovus log file to extract evaluation metrics.
    """
    results = {
        'EstWL': 'N/A',
        'all_WNS': 'N/A',
        'all_TNS': 'N/A',
        'reg2reg_WNS': 'N/A',
        'reg2reg_TNS': 'N/A'
    }

    try:
        with open(log_path, 'r') as f:
            lines = f.readlines()
    except IOError:
        print(f"Warning: Could not read file {log_path}", file=sys.stderr)
        return results

    for i, line in enumerate(lines):
        # Extract EstWL
        estwl_match = re.search(r'EstWL:\s*([0-9.eE+-]+)um', line)
        if estwl_match:
            results['EstWL'] = float(estwl_match.group(1))

        # Check for the timing report header
        if "Setup mode" in line and "all" in line and "reg2reg" in line:
            # The next relevant lines should be WNS and TNS
            # Look ahead for WNS and TNS lines
            for j in range(i + 1, min(i + 5, len(lines))):
                future_line = lines[j]
                if "WNS (ns):" in future_line:
                    parts = [p.strip() for p in future_line.split('|')]
                    if len(parts) > 3:
                        results['all_WNS'] = float(parts[2])
                        results['reg2reg_WNS'] = float(parts[3])
                elif "TNS (ns):" in future_line:
                    parts = [p.strip() for p in future_line.split('|')]
                    if len(parts) > 3:
                        results['all_TNS'] = float(parts[2])
                        results['reg2reg_TNS'] = float(parts[3])
    
    return results


def main():
    """
    Main function to collect Innovus evaluation results from log files.
    """
    parser = argparse.ArgumentParser(
        description='Collect Innovus evaluation results from log files and output a CSV.',
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('def_results_root', help='Root directory for DEF file results containing the logs.')
    args = parser.parse_args()

    def_results_root = os.path.abspath(args.def_results_root)

    if not os.path.isdir(def_results_root):
        print(f"Error: DEF results root directory not found at {def_results_root}", file=sys.stderr)
        return 1

    print(f"Scanning for '*.def.eval.log' files in '{def_results_root}'...")
    
    log_files = glob.glob(os.path.join(def_results_root, '**', '*.def.eval.log'), recursive=True)

    if not log_files:
        print("No log files found. Exiting.")
        return 0

    print(f"Found {len(log_files)} log files to process.")

    all_results = []
    for log_path in sorted(log_files):
        case_name_match = re.search(r'([^/]+)\.def\.eval\.log', os.path.basename(log_path))
        if case_name_match:
            case_name = case_name_match.group(1)
        else:
            case_name = os.path.basename(log_path) # Fallback

        print(f"Processing: {log_path} for case '{case_name}'")
        
        result_data = parse_innovus_log(log_path)
        result_data['Case'] = case_name
        all_results.append(result_data)

    if not all_results:
        print("No data was parsed. Exiting.")
        return 0

    # Convert to DataFrame for easier handling and writing
    df = pd.DataFrame(all_results)
    
    # Reorder columns to have 'Case' first
    cols = ['Case', 'EstWL', 'all_WNS', 'all_TNS', 'reg2reg_WNS', 'reg2reg_TNS']
    df = df[cols]

    output_csv_path = os.path.join(def_results_root, 'innovus_evaluation_summary.csv')

    try:
        df.to_csv(output_csv_path, index=False, float_format='%.3f')
        print(f"\nSuccessfully created summary file: {output_csv_path}")
    except IOError as e:
        print(f"\nError writing CSV file: {e}", file=sys.stderr)
        return 1
        
    # Print summary to console
    print("\n--- Summary ---")
    print(df.to_string(index=False))
    print("---------------")

    return 0

if __name__ == "__main__":
    sys.exit(main())
