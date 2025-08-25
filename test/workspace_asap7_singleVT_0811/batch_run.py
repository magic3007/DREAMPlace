"""
Usage:

```bash
cd build
python <script_name>
```

The results will be saved in the results_dir directory.

"""

results_dir = '/raid/jingmai/vaults/workspace_asap7_singleVT_0811'


#%%
import os
import glob
import subprocess
import json
import time
import fcntl
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import queue

#%%

def get_available_gpus():
    """Get the number of available GPUs using nvidia-smi"""
    try:
        result = subprocess.run(['nvidia-smi', '--list-gpus'],
                              capture_output=True, text=True, check=True)
        gpu_lines = result.stdout.strip().split('\n')
        num_gpus = len(gpu_lines)
        print(f"Found {num_gpus} available GPUs:")
        for i, line in enumerate(gpu_lines):
            print(f"    GPU {i}: {line}")
        return num_gpus
    except subprocess.CalledProcessError:
        print("Warning: nvidia-smi not available or no GPUs found")
        return 0
    except FileNotFoundError:
        print("Warning: nvidia-smi not found in PATH")
        return 0

def get_gpu_memory_info():
    """Get GPU memory information"""
    try:
        result = subprocess.run(['nvidia-smi', '--query-gpu=index,memory.total,memory.used,memory.free',
                               '--format=csv,noheader,nounits'],
                              capture_output=True, text=True, check=True)
        gpu_info = []
        for line in result.stdout.strip().split('\n'):
            if line.strip():
                parts = line.split(', ')
                if len(parts) >= 4:
                    gpu_info.append({
                        'index': int(parts[0]),
                        'total': int(parts[1]),
                        'used': int(parts[2]),
                        'free': int(parts[3])
                    })
        return gpu_info
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []

class GPUMemoryManager:
    """Dynamic GPU memory manager for task allocation"""

    def __init__(self, num_gpus):
        self.num_gpus = num_gpus
        self.gpu_locks = [threading.Lock() for _ in range(num_gpus)]
        self.gpu_memory_usage = [0] * num_gpus  # Track memory usage per GPU
        self.lock = threading.Lock()

    def get_available_gpu(self, required_memory_mb=1000):
        """Get an available GPU with sufficient memory"""
        with self.lock:
            # Get current GPU memory info
            gpu_info = get_gpu_memory_info()
            if not gpu_info:
                # Fallback: assume all GPUs have enough memory
                for gpu_id in range(self.num_gpus):
                    if self.gpu_locks[gpu_id].acquire(blocking=False):
                        return gpu_id
                return None

            # Find GPU with sufficient free memory
            for gpu in gpu_info:
                gpu_id = gpu['index']
                if gpu_id < self.num_gpus:
                    free_memory = gpu['free']
                    if free_memory >= required_memory_mb:
                        if self.gpu_locks[gpu_id].acquire(blocking=False):
                            return gpu_id

            # If no GPU with sufficient memory, try any available GPU
            for gpu_id in range(self.num_gpus):
                if self.gpu_locks[gpu_id].acquire(blocking=False):
                    return gpu_id

            return None

    def release_gpu(self, gpu_id):
        """Release a GPU back to the pool"""
        if 0 <= gpu_id < self.num_gpus:
            self.gpu_locks[gpu_id].release()

def run_single_case(case_info):
    """Run a single case on any available GPU"""
    json_file, case_name, gpu_manager, unique_result_dir = case_info

    print(f"Starting {case_name} (Thread: {threading.current_thread().name})")

    # Get an available GPU
    gpu_id = gpu_manager.get_available_gpu()
    if gpu_id is None:
        error_msg = f"No available GPU for {case_name}"
        print(error_msg)
        return case_name, False, 0, error_msg

    print(f"Assigned GPU {gpu_id} to {case_name}")

    try:
        # Create case-specific directory under unique_result_dir
        case_dir = os.path.join(unique_result_dir, case_name)
        os.makedirs(case_dir, exist_ok=True)
        print(f"Created case directory: {case_dir}")

        # Read the JSON file
        with open(json_file, 'r') as f:
            json_data = json.load(f)

        # Set the result_dir to case_dir
        json_data['result_dir'] = case_dir

        # Write the modified JSON to the case directory
        case_json_file = os.path.join(case_dir, f"{case_name}.json")
        with open(case_json_file, 'w') as f:
            json.dump(json_data, f, indent=4)

        print(f"Modified JSON saved to: {case_json_file}")

        # Prepare environment variables for GPU assignment
        env = os.environ.copy()
        env['CUDA_VISIBLE_DEVICES'] = str(gpu_id)
        print(f"Set CUDA_VISIBLE_DEVICES={gpu_id}")

        # run the command with timing
        command = f"python ./install/dreamplace/Placer.py {case_json_file}"
        log_file = os.path.join(case_dir, "screen.log")
        print(f"Log file: {log_file}")
        print(f"You can run 'tail -f {log_file}' to view the log in real-time")

        start_time = time.time()

        with open(log_file, 'w') as f:
            f.write(f"Starting execution of {case_name} at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Command: {command}\n")
            f.write(f"GPU assigned: {gpu_id}\n")
            f.write(f"Thread: {threading.current_thread().name}\n")
            f.write("-" * 80 + "\n")
            f.flush()

            subprocess.run(command, shell=True, stdout=f, stderr=f, env=env)

        end_time = time.time()
        execution_time = end_time - start_time

        # Write timing information to log file
        with open(log_file, 'a') as f:
            f.write("-" * 80 + "\n")
            f.write(f"Execution completed at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total execution time: {execution_time:.2f} seconds ({execution_time/60:.2f} minutes)\n")

        print(f"Completed {case_name} in {execution_time:.2f} seconds")
        return case_name, True, execution_time, ""

    finally:
        # Always release the GPU
        gpu_manager.release_gpu(gpu_id)
        print(f"Released GPU {gpu_id} from {case_name}")

#%%
if not os.path.exists(results_dir):
    os.makedirs(results_dir)
    print(f"Created result vault directory: {results_dir}")

# Get available GPUs
num_gpus = get_available_gpus()
gpu_memory_info = get_gpu_memory_info()

if num_gpus == 0:
    raise RuntimeError("No GPUs available. This script requires GPU to run.")

print(f"GPU memory information:")
for gpu in gpu_memory_info:
    print(f"    GPU {gpu['index']}: {gpu['total']}MB total, {gpu['used']}MB used, {gpu['free']}MB free")

#%%
# Get the directory of the current file
current_dir = os.path.dirname(os.path.abspath(__file__))

# Find all JSON files in the same directory
json_files = glob.glob(os.path.join(current_dir, "*.json"))

# Print all JSON files found
print("JSON files found in the current directory:")
for json_file in json_files:
    print(f"    {json_file}")

print(f"Total cases to run: {len(json_files)}")

#%%

def get_git_hash():
    """Get the current git commit hash (first 6 characters)"""
    try:
        result = subprocess.run(['git', 'rev-parse', '--short=8', 'HEAD'],
                              capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        # If git command fails, use a default hash
        return "nogit0"

print(f"Git hash: {get_git_hash()}")
#%%
def create_unique_result_dir(base_dir):
    """Create a unique directory with format: {git_hash}_{count}"""
    git_hash = get_git_hash()
    count = 1

    while True:
        dir_name = f"{git_hash}_{count}"
        full_path = os.path.join(base_dir, dir_name)

        if not os.path.exists(full_path):
            os.makedirs(full_path)
            print(f"Created unique result directory: {full_path}")
            return full_path

        count += 1

# Create unique result directory
unique_result_dir = create_unique_result_dir(results_dir)

print(f"Unique result directory: {unique_result_dir}")

#%%
# Initialize GPU manager
gpu_manager = GPUMemoryManager(num_gpus)

# Prepare case information for concurrent execution
case_info_list = []
# filter_case_name = ['ariane.density0.8', 'des3.density0.8', 'pci_bridge32.density0.8']
for json_file in json_files:
    case_name = os.path.basename(json_file).replace('.json', '')
    # if case_name not in filter_case_name:
    #     continue
    case_info = (json_file, case_name, gpu_manager, unique_result_dir)
    case_info_list.insert(0, case_info)

# Run cases concurrently using ThreadPoolExecutor
print(f"\nStarting concurrent execution with {num_gpus} GPUs...")
start_time = time.time()

# Use ThreadPoolExecutor with max_workers equal to number of GPUs
with ThreadPoolExecutor(max_workers=num_gpus) as executor:
    # Submit all cases to the executor
    future_to_case = {executor.submit(run_single_case, case_info): case_info[1]
                     for case_info in case_info_list}

    # Process completed cases as they finish
    completed_cases = []
    for future in as_completed(future_to_case):
        case_name = future_to_case[future]
        try:
            result = future.result()
            completed_cases.append(result)
            print(f"Case {result[0]} finished with status: {'SUCCESS' if result[1] else 'FAILED'}")
        except Exception as exc:
            print(f"Case {case_name} generated an exception: {exc}")
            completed_cases.append((case_name, False, 0, str(exc)))

end_time = time.time()
total_execution_time = end_time - start_time

# Print summary
print(f"\n" + "="*80)
print(f"EXECUTION SUMMARY")
print(f"="*80)
print(f"Total execution time: {total_execution_time:.2f} seconds ({total_execution_time/60:.2f} minutes)")
print(f"Cases completed: {len(completed_cases)}")

successful_cases = [case for case in completed_cases if case[1]]
failed_cases = [case for case in completed_cases if not case[1]]

print(f"Successful cases: {len(successful_cases)}")
print(f"Failed cases: {len(failed_cases)}")

if successful_cases:
    avg_time = sum(case[2] for case in successful_cases) / len(successful_cases)
    print(f"Average case execution time: {avg_time:.2f} seconds")

if failed_cases:
    print(f"\nFailed cases:")
    for case in failed_cases:
        print(f"  {case[0]}: {case[3]}")

print(f"\nAll cases completed. Results saved in: {unique_result_dir}")





#%%