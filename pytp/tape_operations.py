# tape_operations.py
import subprocess
import typer
from pytp import config_manager

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


def show_tape_position(drive_name: str):
    device_path  = get_device_path(drive_name)    
    status_output = run_command(["mt", "-f", device_path, "status"])
    file_number_line = next((line for line in status_output.split('\n') if "File number" in line), None)
    if file_number_line:
        file_number = file_number_line.split('=')[1].split(',')[0].strip()
        return int(file_number)
    else:
        return 0  # Default to 0 if file number is not found


def rewind_tape(drive_name: str, verbose: bool = True):
    device_path  = get_device_path(drive_name)

    if verbose:
        typer.echo(f"Rewinding {device_path}...")

    return run_command(["mt", "-f", device_path, "rewind"])


def init(drive_name: str):
    tape_details = config_manager.get_tape_drive_details(config_manager.config, drive_name)
    device_path  = tape_details.get('device_path', None)
    block_size   = tape_details.get('block_size', 524288)  # Default block size if not specified

    typer.echo(f"Initializing tape drive {device_path} with block size {block_size}...")

    # Rewind the tape first
    rewind_result = run_command(["mt", "-f", device_path, "rewind"])
    if "Error" in rewind_result:
        return rewind_result  # Return error message if rewind fails

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
                break  # Stop after printing the specified number of sample lines
                
    except Exception as e:
        print(f"Error while reading tape: {e}")
    finally:
        process.stdout.close()
        skip_file_markers(drive_name, 1, False)


def backup_directories(drive_name: str, directories: list):
    tape_details = config_manager.get_tape_drive_details(config_manager.config, drive_name)
    device_path  = tape_details.get('device_path', None)
    block_size   = tape_details.get('block_size', 524288)  # Default block size if not specified

    for directory in directories:
        typer.echo(f"Backing up directory {directory} to {device_path}...")
        command = ["tar", "-cvf", device_path, "-b", str(block_size), directory]

        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        line_count = 0
        try:
            for line in process.stdout:
                print(line, end='')  # Print each line immediately
                line_count += 1
        except Exception as e:
            typer.echo(f"Error occurred during backup of {directory}: {backup_result}")
        finally:
            process.stdout.close()
            typer.echo(f"Backup of {directory} completed successfully.")

    return "All backups completed."