# confg_manager.py

import os
import json
from typing import Dict, Any

# Calculate the absolute path to the configs directory
script_dir = os.path.dirname(os.path.realpath(__file__))
config_dir = os.path.join(script_dir, '../configs')
config_path = os.path.join(config_dir, 'tapes.json')
default_config_path = os.path.join(config_dir, 'default_config.json')

def load_config(file_path: str) -> Dict[str, Any]:
    try:
        with open(file_path, 'r') as file:
            return json.load(file)
    except Exception as e:
        print(f"Error loading config: {e}")
        return {}

def load_default_config(file_path: str) -> Dict[str, Any]:
    try:
        with open(file_path, 'r') as file:
            return json.load(file)
    except Exception as e:
        print(f"Error loading default config: {e}")
        return {}

def get_tape_drive_config(config, drive_name=None) -> str:
    if drive_name:
        for drive in config.get('tape_drives', []):
            if drive['name'] == drive_name:
                return drive['device_path']
    else:
        # Return the default drive if no name is provided
        return config.get('tape_drives', [{}])[0].get('device_path', '/dev/nst0')


def get_tape_drive_details(config, drive_name=None):
    if drive_name:
        for drive in config.get('tape_drives', []):
            if drive['name'] == drive_name:
                return drive
    else:
        # Return the default drive details if no name is provided
        return config.get('tape_drives', [{}])[0]

def get_temp_dir():
    return default_config.get('temp_dir', '.')

# Load the configuration when the module is imported
config = load_config(config_path)

# Load the default configuration
default_config = load_default_config(default_config_path)
