#!/usr/bin/env python3
"""
Enhanced error capture for pytp backup operations.
This fix addresses:
1. Stderr not being captured to file
2. mbuffer summary not being saved
3. Unit conversion errors (GiB vs GB)
4. Tape unloading detection
"""

import subprocess
import os
import re
from datetime import datetime

def backup_directories_direct_enhanced(self, directories: list):
    """
    Enhanced version with proper error capture and logging.
    """
    for index, directory in enumerate(directories):
        # Generate log file paths
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stderr_log = os.path.join(self.tar_dir, f"stderr_{timestamp}_{directory.replace('/', '_')}.log")
        mbuffer_log = os.path.join(self.tar_dir, f"mbuffer_{timestamp}_{directory.replace('/', '_')}.log")
        combined_log = os.path.join(self.tar_dir, f"backup_{timestamp}_{directory.replace('/', '_')}.log")
        
        # Prepare backup command with better logging
        tar_command = f"tar -cvf - -T {backup_files_list_path} -b {self.block_size}"
        
        # Enhanced mbuffer command with summary capture
        mbuffer_command = f"mbuffer -P {self.memory_buffer_percent} -m {self.memory_buffer} -s {self.block_size} -v 1 -o {self.device_path} 2>&1 | tee {mbuffer_log}"
        
        # Combined command with proper error capture
        backup_command = f"({tar_command} 2>{stderr_log}) | ({mbuffer_command})"
        
        print(f"Backing up {directory} to {self.device_path}...")
        print(f"Logs: stderr={stderr_log}, mbuffer={mbuffer_log}")
        
        # Execute with full output capture
        with open(combined_log, 'w') as log_file:
            process = subprocess.Popen(
                backup_command, 
                shell=True, 
                stdout=log_file,
                stderr=subprocess.STDOUT,  # Combine stderr into stdout
                text=True
            )
            
            # Monitor process
            return_code = process.wait()
            
            # Check for tape errors
            check_tape_status = subprocess.run(
                ['mt', '-f', self.device_path, 'status'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            # Parse mbuffer summary
            mbuffer_summary = parse_mbuffer_output(mbuffer_log)
            
            # Log results
            with open(combined_log, 'a') as f:
                f.write(f"\n=== BACKUP COMPLETED ===\n")
                f.write(f"Return code: {return_code}\n")
                f.write(f"Tape status: {check_tape_status.stdout}\n")
                if mbuffer_summary:
                    f.write(f"mbuffer summary:\n")
                    f.write(f"  Total data: {mbuffer_summary['total_data']}\n")
                    f.write(f"  Average speed: {mbuffer_summary['avg_speed']}\n")
                    f.write(f"  Buffer empty count: {mbuffer_summary['empty_count']}\n")
                
            if return_code != 0:
                print(f"ERROR: Backup failed with code {return_code}")
                print(f"Check logs: {combined_log}")
                
                # Check if tape was unloaded
                if "DR_OPEN" in check_tape_status.stdout:
                    print("WARNING: Tape was unloaded during backup!")
                    
def parse_mbuffer_output(log_file):
    """
    Parse mbuffer log to extract summary statistics.
    Handles GiB vs GB conversion correctly.
    """
    if not os.path.exists(log_file):
        return None
        
    with open(log_file, 'r') as f:
        content = f.read()
        
    # Look for summary line: "summary: 5134 GiByte in 8h 02min 15,3sec - average of 182 MiB/s, 1266x empty"
    summary_match = re.search(
        r'summary:\s+(\d+(?:\.\d+)?)\s+(GiByte|MiByte|KiByte|Byte).*average of\s+(\d+(?:\.\d+)?)\s+(MiB|KiB|B)/s.*?(\d+)x\s+empty',
        content
    )
    
    if summary_match:
        size_val = float(summary_match.group(1))
        size_unit = summary_match.group(2)
        speed_val = float(summary_match.group(3))
        speed_unit = summary_match.group(4)
        empty_count = int(summary_match.group(5))
        
        # Convert to consistent units (GB)
        if size_unit == 'GiByte':
            total_gb = size_val * 1.073741824  # GiB to GB
        elif size_unit == 'MiByte':
            total_gb = size_val * 0.001073741824
        else:
            total_gb = size_val / 1000000000
            
        return {
            'total_data': f"{total_gb:.2f} GB",
            'avg_speed': f"{speed_val} {speed_unit}/s",
            'empty_count': empty_count
        }
    
    return None

def detect_tape_unload_error(device_path):
    """
    Check if tape was unexpectedly unloaded.
    """
    try:
        result = subprocess.run(
            ['mt', '-f', device_path, 'status'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if "DR_OPEN" in result.stdout:
            return True, "Tape drive is empty (DR_OPEN)"
        elif "Device or resource busy" in result.stdout:
            return True, "Tape drive busy or inaccessible"
        elif result.returncode != 0:
            return True, f"mt status failed: {result.stderr}"
            
        return False, "Tape appears operational"
        
    except subprocess.TimeoutExpired:
        return True, "mt status command timed out"
    except Exception as e:
        return True, f"Error checking tape status: {e}"

# Additional monitoring function
def monitor_backup_realtime(process, device_path, log_file):
    """
    Monitor backup in real-time and detect issues.
    """
    import select
    import time
    
    last_check = time.time()
    
    while process.poll() is None:
        # Check every 30 seconds
        if time.time() - last_check > 30:
            unloaded, msg = detect_tape_unload_error(device_path)
            if unloaded:
                with open(log_file, 'a') as f:
                    f.write(f"\n!!! TAPE ERROR DETECTED: {msg} !!!\n")
                print(f"TAPE ERROR: {msg}")
                process.terminate()
                return False
            last_check = time.time()
            
        time.sleep(1)
    
    return True