import subprocess
import typer
from pytp.config_manager import ConfigManager

class TapeLibraryOperations:
    """
    TapeLibraryOperations class encapsulates various operations related to tape libraries.

    This class provides methods to interact with tape libraries for operations like
    loading, unloading tapes, and managing slots. It serves as a high-level interface
    to tape libraries, abstracting the complexities of low-level tape library management.
    """

    def __init__(self, library_name):
        """
        Initializes the TapeLibraryOperations class.

        Args:
            library_name (str): The name of the tape library to operate on.
        """
        config_manager = ConfigManager()
        self.library_name = library_name
        library_details = config_manager.get_tape_library_details(library_name)
        self.device_path = library_details.get('device_path')

    def run_mtx_command(self, command):
        """
        Executes a given mtx command and returns its output.

        Args:
            command (list): The mtx command to execute, passed as a list of strings.

        Returns:
            str: The output of the command if successful, or an error message if an error occurs.
        """
        full_command = ["mtx", "-f", self.device_path] + command
        try:
            result = subprocess.run(full_command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            return result.stdout
        except subprocess.CalledProcessError as e:
            return f"Error: {e.stderr}"

    def list_contents(self):
        """
        Lists the contents of the tape library, including slots and tapes.

        Returns:
            str: A string containing information about the slots and tapes in the library.
        """
        return self.run_mtx_command(["status"])

    # Other methods like loading, unloading tapes, etc., can be added here

