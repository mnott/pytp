import subprocess

def run_command(command: list):
    try:
        result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr}"

def rewind_tape(device_path: str):
    return run_command(["mt", "-f", device_path, "rewind"])

