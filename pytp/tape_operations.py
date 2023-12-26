# tape_operations.py
import os
import subprocess
import time
import shutil
import tempfile
import typer
import hashlib
from pytp import config_manager
from concurrent.futures import ThreadPoolExecutor, as_completed


def run_command(command: list):
    try:
        result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr}"

def get_device_path(drive_name: str):
    device_path  = config_manager.get_tape_drive_config(config_manager.config, drive_name)

    if not device_path:
        typer.echo("Tape drive not found.")
        raise typer.Exit(1)

    return device_path

def is_tape_ready(drive_name: str) -> bool:
    """
    Check if the tape drive is ready for the next operation.
    """
    device_path = get_device_path(drive_name)
    status_output = run_command(["mt", "-f", device_path, "status"])

    # Example checks (you will need to adjust these based on your tape drive's specific responses)
    if "ONLINE" in status_output:
        return True  # Drive is ready
    elif "DRIVE NOT READY" in status_output or "ERROR" in status_output:
        return False  # Drive is not ready or has encountered an error

    return False  # Default to not ready if none of the conditions match


def show_tape_status(drive_name: str):
    device_path  = get_device_path(drive_name)    
    status_output = run_command(["mt", "-f", device_path, "status"])
    status_output += run_command(["mt", "-f", device_path, "tell"])
    return status_output

def show_tape_position(drive_name: str):
    device_path  = get_device_path(drive_name)    
    status_output = run_command(["mt", "-f", device_path, "status"])
    file_number_line = next((line for line in status_output.split('\n') if "File number" in line), None)
    if file_number_line:
        file_number = file_number_line.split('=')[1].split(',')[0].strip()
        return int(file_number)
    else:
        return 0  # Default to 0 if file number is not found

def show_tape_block(drive_name: str):
    device_path  = get_device_path(drive_name)    
    status_output = run_command(["mt", "-f", device_path, "status"])
    block_number_line = next((line for line in status_output.split('\n') if "Block number" in line), None)
    if block_number_line:
        block_number = block_number_line.split('=')[1].split(',')[0].strip()
        return int(block_number)
    else:
        return 0  # Default to 0 if block number is not found

def set_tape_position(drive_name: str, block: int):
    device_path  = get_device_path(drive_name)    
    status_output = run_command(["mt", "-f", device_path, "seek", str(block)])
    position = show_tape_position(drive_name)
    return position


def rewind_tape(drive_name: str, verbose: bool = True):
    device_path  = get_device_path(drive_name)

    if verbose:
        typer.echo(f"Rewinding {device_path}...")

    return run_command(["mt", "-f", device_path, "rewind"])


def init(drive_name: str):
    tape_details = config_manager.get_tape_drive_details(config_manager.config, drive_name)
    device_path  = tape_details.get('device_path', None)
    block_size   = tape_details.get('block_size', 524288)  # Default block size if not specified

    # Rewind the tape first
    rewind_result = rewind_tape(drive_name)
    if "Error" in rewind_result:
        return rewind_result  # Return error message if rewind fails

    typer.echo(f"Initializing tape drive {device_path} with block size {block_size}...")

    # Set the block size
    return run_command(["mt", "-f", device_path, "setblk", str(block_size)])


def skip_file_markers(drive_name: str, count: int, verbose: bool = True):
    device_path  = get_device_path(drive_name)

    current_position = show_tape_position(drive_name)  # Assume this function returns the current file number

    
    # Calculate the new position after the skip
    new_position = current_position + count

    real_count = count

    if count < 0:
        # If skipping backward, subtract 1 from the count to account for the current position
        new_position -= 1
        real_count -= 1

    # If new position is less than 1, perform a rewind instead of a backward skip
    if new_position < 0:
        return rewind_tape(drive_name)
    else:
        if verbose:
            typer.echo(f"Skipping {count} file markers from position {current_position} on {device_path}...")


    if real_count > 0:
        # Skip forward
        command = ["mt", "-f", device_path, "fsf", str(real_count)]
    elif real_count < 0:
        # Skip backward
        command = ["mt", "-f", device_path, "bsfm", str(abs(real_count))]
    else:
        return "No movement required."

    return run_command(command)


def list_files(drive_name: str, sample: int = None):
    tape_details = config_manager.get_tape_drive_details(config_manager.config, drive_name)
    device_path  = tape_details.get('device_path', None)
    block_size   = tape_details.get('block_size', 524288)  # Default block size if not specified

    command = ["tar", "-b", str(block_size), "-tvf", device_path]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    line_count = 0
    try:
        for line in process.stdout:
            print(line, end='')  # Print each line immediately
            line_count += 1
            if sample and line_count >= sample:
                skip_file_markers(drive_name, -1, False)
                break  # Stop after printing the specified number of sample lines
                
    except Exception as e:
        print(f"Error while reading tape: {e}")
    finally:
        process.stdout.close()
        if not sample:
            skip_file_markers(drive_name, 1, False)


import queue
import threading

def backup_directories(drive_name: str, directories: list):
    tape_details = config_manager.get_tape_drive_details(config_manager.config, drive_name)
    device_path = tape_details.get('device_path', None)
    block_size = tape_details.get('block_size', 524288)  # Default block size

    # Use temp_dir from the default_config
    temp_dir_root = config_manager.default_config.get('temp_dir', '/tmp')

    tar_queue = queue.Queue()
    stop_signal = object()

    def create_tar():
        for directory in directories:
            dir_name = os.path.basename(directory)
            temp_tar_path = os.path.join(temp_dir_root, f"{dir_name}.tar")
            create_tar_command = f"tar -cvf {temp_tar_path} -b {block_size} {directory}"
            subprocess.run(create_tar_command, shell=True, check=True)
            tar_queue.put(temp_tar_path)

        tar_queue.put(stop_signal)  # Signal that all tars are created

    def write_to_tape():
        while True:
            temp_tar_path = tar_queue.get()
            if temp_tar_path == stop_signal:
                break  # All tars are processed

            write_to_tape_command = f"mbuffer -P 80 -m 8G -s {block_size} -i {temp_tar_path} -o {device_path}"
            process = subprocess.Popen(write_to_tape_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            for line in process.stderr:
                print(line, end='')
            process.wait()
            if process.returncode != 0:
                typer.echo(f"Error occurred during writing {temp_tar_path} to tape. Error code: {process.returncode}")

            os.remove(temp_tar_path)  # Clean up the tar file

    # Start tar creation and writing in separate threads
    create_tar_thread = threading.Thread(target=create_tar)
    write_to_tape_thread = threading.Thread(target=write_to_tape)

    create_tar_thread.start()
    write_to_tape_thread.start()

    create_tar_thread.join()
    write_to_tape_thread.join()

    return "All backups completed."





def restore_files(drive_name: str, target_dir: str):
    tape_details = config_manager.get_tape_drive_details(config_manager.config, drive_name)
    device_path  = tape_details.get('device_path', None)
    block_size   = tape_details.get('block_size', 524288)  # Default block size if not specified

    # Create the target directory if it does not exist
    if not os.path.exists(target_dir):
        os.makedirs(target_dir, exist_ok=True)

    typer.echo(f"Restoring files from {device_path} to {target_dir}...")
    command = ["tar", "-xvf", device_path, "-b", str(block_size), "-C", target_dir]

    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    line_count = 0
    try:
        for line in process.stdout:
            print(line, end='')  # Print each line immediately
            line_count += 1
    except Exception as e:
        typer.echo(f"Error occurred during restore of {target_dir}: {backup_result}")
    finally:
        process.stdout.close()
        skip_file_markers(drive_name, 1, False)
        typer.echo(f"Restore of {target_dir} completed successfully.")


def generate_checksum(file_path):
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

