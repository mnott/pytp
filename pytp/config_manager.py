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
        config         (Dict[str, Any]): A dictionary holding the loaded configuration.
    """
    def __init__(self):
        """
        Initializes the ConfigManager by setting up paths for configuration files 
        and loading the configurations.
        """        
        # Calculate the absolute path to the configs directory
        script_dir               = os.path.dirname(os.path.realpath(__file__))
        config_dir               = os.path.join(script_dir, '../configs')
        self.config_path         = os.path.join(config_dir, 'config.json')

        # Load the configuration and default configuration
        self.config              = self.load_config(self.config_path)


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


    def get_config_value(self, key_path, default=None):
        """
        Retrieve a configuration value using a key path.

        Args:
            key_path (str): The path to the key in the configuration dictionary.
            default (any): The default value to return if the key is not found.

        Returns:
            any: The value of the configuration key or the default value.
        """
        keys = key_path.split('.')
        value = self.config
        for key in keys:
            value = value.get(key)
            if value is None:
                return default
        return value


    def get_tape_drive_config(self, drive_name=None, device_path=None) -> str:
        """
        Retrieve the device path of a specified tape drive from the configuration.

        Args:
            drive_name (str, optional): The name of the tape drive. Defaults to None.
            device_path (str, optional): The device path of the tape drive. Defaults to None.

        Returns:
            str: The device path of the tape drive.
        """
        if drive_name:
            for drive in self.config.get('tape_drives', []):
                if drive['name'] == drive_name:
                    return drive['device_path']
        elif device_path:
            for drive in self.config.get('tape_drives', []):
                if drive['device_path'] == device_path:
                    return drive['device_path']
        else:
            # Return the default drive if no name is provided
            return self.config.get('tape_drives', [{}])[0].get('device_path', '/dev/nst0')


    def get_tape_drive_details(self, drive_name=None, device_path=None):
        """
        Retrieve the details of a specified tape drive from the configuration.

        Args:
            drive_name (str, optional): The name of the tape drive. Defaults to None.
            device_path (str, optional): The device path of the tape drive. Defaults to None.

        Returns:
            Dict[str, Any]: A dictionary containing the details of the tape drive.
        """
        if drive_name:
            for drive in self.config.get('tape_drives', []):
                if drive['name'] == drive_name:
                    return drive
        elif device_path:
            for drive in self.config.get('tape_drives', []):
                if drive['device_path'] == device_path:
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
        return self.config.get('tar_dir', '.')
    

    def get_snapshot_dir(self):
        """
        Retrieve the snapshot directory path from the default configuration.

        Returns:
            str: The path to the snapshot directory.
        """        
        return self.config.get('snapshot_dir', '.')

    def get_tape_library_details(self, library_name=None):
        """
        Retrieve the details of a specified tape library from the configuration.

        Args:
            library_name (str, optional): The name of the tape library. Defaults to None.

        Returns:
            Dict[str, Any]: A dictionary containing the details of the tape library.
        """
        if library_name:
            for library in self.config.get('tape_libraries', []):
                if library['name'] == library_name:
                    return library
        else:
            # Return the default library details if no name is provided
            return self.config.get('tape_libraries', [{}])[0]
    
    def get_library_name(self, requested_name=None):
        """
        Get the library name using smart selection logic:
        1. If requested_name is provided, use it (fail if not configured)
        2. If not provided, use first library in config (fail if none configured)
        
        Args:
            requested_name (str, optional): Explicitly requested library name
            
        Returns:
            str: The library name to use
            
        Raises:
            ValueError: If requested library doesn't exist or no libraries configured
        """
        libraries = self.config.get('tape_libraries', [])
        
        if requested_name:
            # Case 1: Explicit library requested - must exist
            for library in libraries:
                if library['name'] == requested_name:
                    return requested_name
            raise ValueError(f"Library '{requested_name}' not found in configuration")
        elif libraries:
            # Case 2: Use first configured library
            return libraries[0]['name']
        else:
            # Case 3: No libraries configured - fail
            raise ValueError("No tape libraries configured")
    
    def display_config(self):
        """
        Display the current configuration in a human-readable format using Rich tables.
        """
        from rich.console import Console
        from rich.table import Table
        from rich.panel import Panel
        from rich.columns import Columns
        
        console = Console()
        
        # Main directories
        dirs_table = Table(title="📁 Directories", show_header=True, header_style="bold blue")
        dirs_table.add_column("Setting", style="cyan", width=15)
        dirs_table.add_column("Path", style="white")
        
        dirs_table.add_row("Tar Directory", self.get_tar_dir())
        dirs_table.add_row("Snapshot Directory", self.get_snapshot_dir())
        
        # Tape Drives
        drives_table = Table(title="🎬 Tape Drives", show_header=True, header_style="bold green")
        drives_table.add_column("Name", style="cyan", width=8)
        drives_table.add_column("Device Path", style="white", width=12)
        drives_table.add_column("Block Size", justify="right", style="yellow", width=10)
        
        for drive in self.config.get('tape_drives', []):
            block_size = f"{drive.get('block_size', 0):,}" if drive.get('block_size') else "0"
            drives_table.add_row(
                drive.get('name', 'Unknown'),
                drive.get('device_path', 'Unknown'),
                block_size
            )
        
        # Tape Libraries
        libraries_table = Table(title="📚 Tape Libraries", show_header=True, header_style="bold magenta")
        libraries_table.add_column("Name", style="cyan", width=10)
        libraries_table.add_column("Device Path", style="white", width=12)
        libraries_table.add_column("Slots", justify="right", style="yellow", width=6)
        libraries_table.add_column("Drives", style="green")
        
        for library in self.config.get('tape_libraries', []):
            drives_str = ", ".join(library.get('drives', []))
            libraries_table.add_row(
                library.get('name', 'Unknown'),
                library.get('device_path', 'Unknown'),
                str(library.get('slots', 0)),
                drives_str
            )
        
        # Display all tables
        console.print("\n")
        console.print(Panel.fit("🔧 PYTP Configuration", style="bold white on blue"))
        console.print("")
        console.print(dirs_table)
        console.print("")
        console.print(drives_table)
        console.print("")
        console.print(libraries_table)
        console.print("")
        
