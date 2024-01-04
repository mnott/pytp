import errno
import subprocess
import threading
import typer
import json
import os
import pty
import select
from pytp.config_manager import ConfigManager
from rich.console import Console
from rich.table import Table

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
        self.config_manager     = ConfigManager()
        self.library_name       = library_name
        self.library_details    = self.config_manager.get_tape_library_details(library_name)
        self.drive_name_mapping = {str(index): drive_name for index, drive_name in enumerate(self.library_details["drives"])}

        self.device_path        = self.library_details.get('device_path')


    def run_mtx_command(self, command, verbose: bool = False):
        full_command = ["mtx", "-f", self.device_path] + command

        if verbose:
            master, slave = pty.openpty()
            try:
                process = subprocess.Popen(full_command, stdout=slave, stderr=slave, text=True)
                os.close(slave)  # Close the slave part as it is not used

                output_lines = []
                while True:
                    if process.poll() is not None:
                        # Process has finished, no more output expected
                        break

                    r, _, _ = select.select([master], [], [], 0.1)
                    if master in r:
                        try:
                            line = os.read(master, 1024).decode()
                            if not line:
                                break  # End of output
                            print(line, end='', flush=True)
                            output_lines.append(line.strip())
                        except OSError as e:
                            if e.errno != errno.EIO:
                                print(f"Read error: {e}", flush=True)
                                raise
                            break

                process.wait()  # Wait for the process to finish
                # return "\n".join(output_lines) # avoid double output for now, but let's keep this around for a while
                return ""

            finally:
                os.close(master)
                if process and process.poll() is None:
                    process.kill()

        else:
            # Simpler execution for non-verbose mode
            try:
                result = subprocess.run(full_command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                return result.stdout
            except subprocess.CalledProcessError as e:
                return f"Error: {e.stderr}"


    
    def list_tapes(self):
        """
        Lists the contents of the tape library, including slots and tapes.

        Returns:
            str: A string containing information about the slots and tapes in the library.
        """
        status      = self.run_mtx_command(["status"])
        parsed_data = self.parse_tape_library_output(status)
        return parsed_data


    def parse_tape_library_output(self, output):
        """
        Parses the output from the tape library's status command.

        This method processes the raw output from the tape library's status command,
        which includes information about the data transfer elements (drives),
        storage elements (slots), and import/export slots. It organizes this
        information into a structured format, making it easy to access and understand.

        Args:
            output (str): The raw output string from the tape library's status command.

        Returns:
            dict: A dictionary containing parsed data with separate keys for drives,
                slots, and import/export slots.

        The method iterates over each line of the output. For lines that contain
        information about data transfer elements (drives), it extracts details like
        the drive number, status, slot loaded, and volume tag. For storage elements
        (slots), it extracts the slot number, status, and volume tag. The method
        also handles import/export slots similarly. Additionally, it maps the drive
        names from the class's drive_name_mapping attribute to the parsed data.

        Example of output structure:
            {
                "drives": {
                    "0": {"status": "Empty", "slot_loaded": None, "volume_tag": None, "name": "lto6"},
                    "1": {"status": "Full", "slot_loaded": "2", "volume_tag": "P0003SL9", "name": "lto9"}
                },
                "slots": {...},
                "import_export_slots": {...}
            }
        """
        parsed_data = {
            "drives": {},
            "slots": {},
            "import_export_slots": {}
        }
        lines = output.split('\n')
        for line in lines:
            if "Data Transfer Element" in line:
                parts = line.split(':')
                drive_number = parts[0].split()[3]
                status = parts[1].split('(')[0].strip()
                slot_loaded = parts[1].split('(')[1].split(')')[0].replace("Storage Element ", "").strip().split(' ')[0] if '(' in parts[1] else None
                volume_tag = parts[2].split('=')[1].strip() if len(parts) > 2 and '=' in parts[2] else None
                parsed_data["drives"][drive_number] = {"status": status, "slot_loaded": slot_loaded, "volume_tag": volume_tag}
            elif "Storage Element" in line:
                parts = line.split(':')
                slot_number = parts[0].split()[2]
                status = parts[1].split()[0].strip()
                volume_tag = parts[2].split('=')[1].strip() if len(parts) > 2 and '=' in parts[2] else None
                if "IMPORT/EXPORT" in line:
                    parsed_data["import_export_slots"][slot_number] = {"status": status, "volume_tag": volume_tag}
                else:
                    parsed_data["slots"][slot_number] = {"status": status, "volume_tag": volume_tag}

        for drive_number, drive_info in parsed_data["drives"].items():
            drive_name = self.drive_name_mapping.get(drive_number, "Unknown")
            drive_info["name"] = drive_name
        return parsed_data


    def print_tape_library_output(self, output):
        """
        Displays the contents of the tape library in a formatted table.

        Args:
            output (dict): The parsed data from the tape library output, containing
                        information about drives, slots, and import/export slots.

        This function creates a table using the 'rich' library to display the tape library's
        contents in an easy-to-read format. It adds rows to the table for each drive, slot,
        and import/export slot, extracting relevant information from the 'output' dictionary.
        """

        # Create a table with headers and set styles
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Element", style="dim", width=12)
        table.add_column("Status", min_width=10)
        table.add_column("Slot Loaded", justify="right")
        table.add_column("Volume Tag", justify="right")
        table.add_column("Drive Name", justify="right")

        # Add drive information to the table
        for drive_number, drive_info in output['drives'].items():
            table.add_row(
                f"Drive {drive_number}",
                drive_info.get("status", ""),
                drive_info.get("slot_loaded", ""),
                drive_info.get("volume_tag", ""),
                drive_info.get("name", "")
            )

        # Add slot information to the table
        for slot_number, slot_info in output['slots'].items():
            table.add_row(
                f"Slot {slot_number}",
                slot_info.get("status", ""),
                "",
                slot_info.get("volume_tag", ""),
                ""
            )

        # Add import/export slot information to the table
        for slot_number, slot_info in output['import_export_slots'].items():
            table.add_row(
                f"I/E Slot {slot_number}",
                slot_info.get("status", ""),
                "",
            slot_info.get("volume_tag", ""),
            ""
        )

        # Display the table
        console = Console()
        console.print(table)


    def load_tape(self, drive_name, slot_number):
        """
        Loads a tape from a specified slot to a drive.

        Args:
            drive_name (str): The name of the drive to load the tape into.
            slot_number (str): The slot number from which to load the tape.

        Returns:
            str: The output message from the mtx command.
        """
        # Retrieve the current status to map drive names to numbers
        current_status = self.list_tapes()

        # Find the drive number corresponding to the drive name
        drive_number = None
        for num, info in current_status['drives'].items():
            if info.get('name') == drive_name:
                drive_number = num
                break

        if drive_number is None:
            return f"Drive '{drive_name}' not found in the tape library."

        # Execute the mtx command to load the tape
        command = ["load", str(slot_number), drive_number]
        result = self.run_mtx_command(command, verbose=True)
        return result
    

    def unload_tape(self, drive_name, slot_number=None):
        """
        Unloads a tape from a drive to a slot.

        Args:
            drive_name (str): The name of the drive to unload the tape from.
            slot_number (str, optional): The slot number to unload the tape into. 
                                        If None, unloads to the original slot.

        Returns:
            str: The output message from the mtx command.
        """
        # Retrieve the current status to map drive names to numbers and find the original slot
        current_status = self.list_tapes()

        drive_number = None
        original_slot = None
        for num, info in current_status['drives'].items():
            if info.get('name') == drive_name:
                drive_number = num
                original_slot = info.get('slot_loaded')
                break

        if drive_number is None:
            return f"Drive '{drive_name}' not found in the tape library."

        # Determine the slot number to unload the tape into
        target_slot = str(slot_number) if slot_number is not None else original_slot
        if target_slot is None:
            return "No slot number provided and no original slot information available."

        # Execute the mtx command to unload the tape
        command = ["unload", target_slot, drive_number]
        result = self.run_mtx_command(command, verbose=True)
        return result


    def move_tape(self, slot_number_from, slot_number_to):
        """
        Moves a tape from a specified slot to another slot.

        Args:
            slot_number_from (int): The slot number from which to move the tape.
            slot_number_to (int): The slot number to which to move the tape.

        Returns:
            str: The output message from the mtx command.
        """
        # Retrieve the current status to check if the target slot is empty
        current_status = self.list_tapes()

        # Check if the source slot is empty
        source_slot_status = current_status['slots'].get(str(slot_number_from), {}).get('status')
        if source_slot_status == 'Empty':
            return f"Source slot {slot_number_from} is empty. No tape to move."

        # Check if the target slot is empty
        target_slot_status = current_status['slots'].get(str(slot_number_to), {}).get('status')
        if target_slot_status == 'Empty':
            command = ["transfer", str(slot_number_from), str(slot_number_to)]
        else:
            return f"Target slot {slot_number_to} is full. Cannot move tape."

        # Execute the mtx command to move the tape
        print(f"Moving tape from slot {slot_number_from} to slot {slot_number_to}...")
        result = self.run_mtx_command(command, verbose=True)
        return result


    def get_tape_label_from_drive(self, device_path):
        # Fetch the current status of the tape library
        tape_library_contents = self.list_tapes()

        # Find the tape in the drive and return its label
        drive_info = self.config_manager.get_tape_drive_details(device_path = device_path)

        if drive_info is None:
            return None
        
        drive_name = drive_info.get('name')

        for a_drive_info in tape_library_contents['drives'].values():
            if a_drive_info.get('name') == drive_name:
                return a_drive_info.get('volume_tag')

        return None  # Return None if no label is found
    

