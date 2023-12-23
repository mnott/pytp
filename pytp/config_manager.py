import json
from typing import Dict, Any

CONFIG_PATH = "configs/tapes.json"

def load_config(file_path: str) -> Dict[str, Any]:
    try:
        with open(file_path, 'r') as file:
            return json.load(file)
    except Exception as e:
        print(f"Error loading config: {e}")
        return {}

def get_tape_drive_config(config, drive_name=None) -> str:
    if drive_name:
        for drive in config.get('tape_drives', []):
            if drive['name'] == drive_name:
                return drive['device_path']
    else:
        # Return the default drive if no name is provided
        return config.get('tape_drives', [{}])[0].get('device_path', '/dev/st0')


def get_tape_drive_details(config, drive_name=None):
    if drive_name:
        for drive in config.get('tape_drives', []):
            if drive['name'] == drive_name:
                return drive
    else:
        # Return the default drive details if no name is provided
        return config.get('tape_drives', [{}])[0]



# Load the configuration when the module is imported
config = load_config(CONFIG_PATH)