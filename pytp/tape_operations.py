import subprocess

def run_command(command: list):
    try:
        result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr}"

def rewind_tape(device_path: str):
    return run_command(["mt", "-f", device_path, "rewind"])


def set_block_size(device_path: str, block_size: int):
    # Rewind the tape first
    rewind_result = run_command(["mt", "-f", device_path, "rewind"])
    if "Error" in rewind_result:
        return rewind_result  # Return error message if rewind fails

    # Set the block size
    return run_command(["mt", "-f", device_path, "setblk", str(block_size)])

