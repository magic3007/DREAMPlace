#!/usr/bin/env python3

import os
import sys
import argparse
import glob
import re
import csv
from pathlib import Path

def extract_tns_wns_from_log(log_file_path):
    """
    Extract TNS and WNS values from an OpenROAD evaluation log file.
    
    Args:
        log_file_path (str): Path to the log file
        
    Returns:
        tuple: (case_name, tns, wns) or (case_name, None, None) if extraction fails
    """
    try:
        with open(log_file_path, 'r') as f:
            content = f.read()
        
        # Extract case name from the log file path
        case_name = os.path.basename(log_file_path).replace('.openroad.eval.log', '')
        
        # Extract TNS value
        tns_match = re.search(r'tns\s+([-\d.]+)', content, re.IGNORECASE)
        tns = float(tns_match.group(1)) if tns_match else None
        
        # Extract WNS value
        wns_match = re.search(r'wns\s+([-\d.]+)', content, re.IGNORECASE)
        wns = float(wns_match.group(1)) if wns_match else None
        
        return case_name, tns, wns
        
    except Exception as e:
        print(f"Error reading log file {log_file_path}: {e}", file=sys.stderr)
        case_name = os.path.basename(log_file_path).replace('.openroad.eval.log', '')
        return case_name, None, None

def find_log_files(def_results_root):
    """
    Find all OpenROAD evaluation log files in the DEF results directory.
    
    Args:
        def_results_root (str): Root directory containing DEF results
        
    Returns:
        list: List of paths to log files
    """
    log_files = []
    
    try:
        # Search recursively for all .openroad.eval.log files
        pattern = os.path.join(def_results_root, '**', '*.openroad.eval.log')
        log_files = glob.glob(pattern, recursive=True)
        
        if not log_files:
            print(f"No OpenROAD evaluation log files found in {def_results_root}", file=sys.stderr)
            return []
            
        print(f"Found {len(log_files)} OpenROAD evaluation log files")
        
    except Exception as e:
        print(f"Error searching for log files: {e}", file=sys.stderr)
        return []
    
    return sorted(log_files)

def main():
    """
    Main function to collect TNS and WNS data from OpenROAD evaluation logs.
    """
    parser = argparse.ArgumentParser(
        description='Collect TNS and WNS data from OpenROAD evaluation logs.',
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('def_results_root', help='Root directory for DEF file results of all cases.')
    parser.add_argument('-o', '--output', help='Output CSV file path. (default: openroad_results.csv)')
    parser.add_argument('--no-csv', action='store_true', help='Do not save to CSV file, only print to screen.')
    
    args = parser.parse_args()
    
    def_results_root = os.path.abspath(args.def_results_root)
    
    if not os.path.isdir(def_results_root):
        print(f"Error: DEF results root directory not found at {def_results_root}", file=sys.stderr)
        return 1
    
    # Find all log files
    log_files = find_log_files(def_results_root)
    
    if not log_files:
        return 1
    
    # Extract TNS and WNS data from each log file
    results = []
    successful_extractions = 0
    
    print("\nExtracting TNS and WNS data from log files...")
    
    for log_file in log_files:
        case_name, tns, wns = extract_tns_wns_from_log(log_file)
        
        if tns is not None and wns is not None:
            successful_extractions += 1
            status = "✓"
        else:
            status = "✗"
        
        results.append({
            'case_name': case_name,
            'tns': tns,
            'wns': wns,
            'log_file': log_file
        })
        
        # Print processing status
        if tns is not None and wns is not None:
            print(f"Processing: {log_file} for case '{case_name}' ✓")
        else:
            print(f"Processing: {log_file} for case '{case_name}' ✗")
    
    print(f"\nSuccessfully extracted data from {successful_extractions}/{len(log_files)} log files")
    
    # Save to CSV if requested
    if not args.no_csv:
        output_file = args.output if args.output else os.path.join(def_results_root, 'openroad_results.csv')
        
        try:
            with open(output_file, 'w', newline='') as csvfile:
                fieldnames = ['case_name', 'tns', 'wns', 'log_file']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                for result in results:
                    writer.writerow(result)
            
            print(f"\nResults saved to: {output_file}")
            
        except Exception as e:
            print(f"Error saving CSV file: {e}", file=sys.stderr)
            return 1
    
    # Print summary statistics
    valid_results = [r for r in results if r['tns'] is not None and r['wns'] is not None]
    
    if valid_results:
        tns_values = [r['tns'] for r in valid_results]
        wns_values = [r['wns'] for r in valid_results]
        
        print(f"\n--- Summary ---")
        print(f"Total cases processed: {len(results)}")
        print(f"Successful extractions: {len(valid_results)}")
        print(f"Failed extractions: {len(results) - len(valid_results)}")
        
        if tns_values:
            print(f"\nTNS Statistics:")
            print(f"  Min: {min(tns_values):.2f}")
            print(f"  Max: {max(tns_values):.2f}")
            print(f"  Mean: {sum(tns_values) / len(tns_values):.2f}")
        
        if wns_values:
            print(f"\nWNS Statistics:")
            print(f"  Min: {min(wns_values):.2f}")
            print(f"  Max: {max(wns_values):.2f}")
            print(f"  Mean: {sum(wns_values) / len(wns_values):.2f}")
        
        # Print summary table similar to Innovus script
        print(f"\n--- Results Summary ---")
        print("Case Name".ljust(30) + "WNS".rjust(10) + " " + "TNS".rjust(10))
        print("-" * 51)
        for result in valid_results:
            case_name = result['case_name']
            wns = result['wns']
            tns = result['tns']
            print(f"{case_name[:29].ljust(30)}{wns:10.3f} {tns:10.3f}")
        print("---------------")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
