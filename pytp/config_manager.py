# config_manager.py

import os
import json
from typing import Dict, Any

class ConfigManager:
    """
    A class for managing configuration files for the tape backup system.

    This class is responsible for loading, parsing, and providing access to 
    configuration details stored in JSON format. It handles configurations 
    for tape drives and other system settings.

    Attributes:
        config_path               (str): Path to the main configuration file.
        default_config_path       (str): Path to the default configuration file.
        config         (Dict[str, Any]): A dictionary holding the loaded configuration.
        default_config (Dict[str, Any]): A dictionary holding the loaded default configuration.
    """
    def __init__(self):
        """
        Initializes the ConfigManager by setting up paths for configuration files 
        and loading the configurations.
        """        
        # Calculate the absolute path to the configs directory
        script_dir               = os.path.dirname(os.path.realpath(__file__))
        config_dir               = os.path.join(script_dir, '../configs')
        self.config_path         = os.path.join(config_dir, 'tapes.json')
        self.default_config_path = os.path.join(config_dir, 'default_config.json')

        # Load the configuration and default configuration
        self.config              = self.load_config(self.config_path)
        self.default_config      = self.load_config(self.default_config_path)


    def load_config(self, file_path: str) -> Dict[str, Any]:
        """
        Load a configuration file and return its contents as a dictionary.

        Args:
            file_path (str): The path to the configuration file.

        Returns:
            Dict[str, Any]: A dictionary representation of the configuration file.
        """
        try:
            with open(file_path, 'r') as file:
                return json.load(file)
        except Exception as e:
            print(f"Error loading config: {e}")
            return {}


    def get_tape_drive_config(self, drive_name=None) -> str:
        """
        Retrieve the device path of a specified tape drive from the configuration.

        Args:
            drive_name (str, optional): The name of the tape drive. Defaults to None.

        Returns:
            str: The device path of the tape drive.
        """
        if drive_name:
            for drive in self.config.get('tape_drives', []):
                if drive['name'] == drive_name:
                    return drive['device_path']
        else:
            # Return the default drive if no name is provided
            return self.config.get('tape_drives', [{}])[0].get('device_path', '/dev/nst0')


    def get_tape_drive_details(self, drive_name=None):
        """
        Retrieve the details of a specified tape drive from the configuration.

        Args:
            drive_name (str, optional): The name of the tape drive. Defaults to None.

        Returns:
            Dict[str, Any]: A dictionary containing the details of the tape drive.
        """
        if drive_name:
            for drive in self.config.get('tape_drives', []):
                if drive['name'] == drive_name:
                    return drive
        else:
            # Return the default drive details if no name is provided
            return self.config.get('tape_drives', [{}])[0]

    def get_tar_dir(self):
        """
        Retrieve the temporary tar directory path from the default configuration.

        Returns:
            str: The path to the temporary tar directory.
        """
        return self.default_config.get('tar_dir', '.')
    

    def get_snapshot_dir(self):
        """
        Retrieve the snapshot directory path from the default configuration.

        Returns:
            str: The path to the snapshot directory.
        """        
        return self.default_config.get('snapshot_dir', '.')

