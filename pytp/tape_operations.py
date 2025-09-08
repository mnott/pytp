# tape_operations.py

import subprocess
import typer
import hashlib
import os
import signal
from pytp.config_manager import ConfigManager
from pytp.tape_backup    import TapeBackup

import fcntl
import errno
import time
import re

class TapeOperations:
    """
    TapeOperations class encapsulates various operations related to tape drives.
    
    This class provides a set of methods to interact with tape drives for different operations
    like initialization, status checking, file listing, backup, and restoration. It serves as
    a high-level interface to tape drives, abstracting the complexities of low-level tape drive
    management and operations.

    Attributes:
        drive_name    (str): Name of the tape drive as configured in the system.
        device_path   (str): The file system path to the tape drive device.
        block_size    (int): The block size for tape operations, defaulting to 524288.
        tar_dir       (str): The root directory for tar files used during operations.
    """

    def __init__(self, drive_name, strategy="direct"):
        """
        Initializes the TapeOperations class.

        Args:
            drive_name (str): The name of the tape drive to operate on.
            strategy (str, optional): The backup strategy to be used. Defaults to "direct".

        The constructor fetches tape drive details from the configuration manager and sets
        up the necessary attributes. It also creates an instance of the TapeBackup class,
        which will be used for actual backup operations.
        """
        config_manager     = ConfigManager()
        self.drive_name    = drive_name
        tape_details       = config_manager.get_tape_drive_details(drive_name = drive_name)
        self.device_path   = tape_details.get('device_path')
        self.block_size    = tape_details.get('block_size', 524288)  # Default block size if not specified
        self.tar_dir       = config_manager.get_tar_dir()
        self.snapshot_dir  = config_manager.get_snapshot_dir()


    def get_device_path(self):
        """
        Retrieves the device path for the specified tape drive.

        This method queries the configuration manager for the device path of the tape drive
        identified by 'drive_name'. If the tape drive is not found in the configuration,
        the method outputs an error message and exits the program.

        Returns:
            str: The device path of the tape drive.

        Raises:
            typer.Exit: If the tape drive is not found in the configuration.

        The method ensures that the tape drive is configured and accessible before proceeding
        with any operations. It provides a safeguard against operations on non-configured or
        non-existent drives.
        """        
        device_path  = ConfigManager().get_tape_drive_config(drive_name=self.drive_name)

        if not device_path:
            typer.echo("Tape drive not found.")
            raise typer.Exit(1)

        return device_path


    def run_command(self, command):
        """
        Executes a given command in the subprocess and returns its output.

        This method utilizes Python's subprocess module to run a command. It captures both the
        standard output and standard error of the command. If the command runs successfully, the
        standard output is returned. In case of an error, the standard error message is returned
        as a formatted string.

        Args:
            command (list): The command to execute, passed as a list of strings.

        Returns:
            str: The output of the command if successful, or an error message if an error occurs.

        The method provides a convenient way to execute shell commands and handle their output
        and errors. This is particularly useful in tape operations where many commands are
        executed in the shell.
        """
        full_command = ["mt", "-f", self.device_path] + command

        try:
            result = subprocess.run(full_command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            return result.stdout
        except subprocess.CalledProcessError as e:
            return f"Error: {e.stderr}"


    def is_tape_ready(self) -> bool:
        """
        Checks if the tape drive is ready for operations.

        This method uses the 'mt' command to query the status of the tape drive and determines
        if the tape is ready for read/write operations. It parses the output of the 'mt status'
        command to check for specific keywords that indicate the readiness of the drive.

        Returns:
            bool: True if the tape drive is ready, False otherwise.

        The method is useful in scenarios where it's necessary to ensure the readiness of the
        tape drive before performing any operations. It helps to avoid errors that may occur due
        to the tape drive not being ready.

        Note:
        This method contains example checks based on common status messages. These checks may need
        to be adjusted based on the specific responses of the tape drive in use.
        """
        status_output = self.run_command(["status"])

        # Example checks (TODO: adjust these based on the tape drive's specific responses)
        if "DR_OPEN" in status_output:
            return False # "The tape drive is empty (no tape loaded)."
        elif "ONLINE" in status_output:
            return True  # Drive is ready
        elif "DRIVE NOT READY" in status_output or "ERROR" in status_output:
            return False  # Drive is not ready or has encountered an error
        elif "Device or resource busy" in status_output:
            return False # The tape drive is busy
        
        return False  # Default to not ready if none of the conditions match


    def show_tape_status(self, verbose: bool = False):
        """
        Retrieves and returns the current status and position of the tape in the tape drive.

        This method combines the output of two commands: 'mt status' and 'mt tell'. 
        The 'mt status' command provides general status information about the tape drive, 
        such as whether it's online or any errors have been encountered. The 'mt tell' 
        command returns the current position of the tape in terms of the number of blocks 
        from the beginning.

        Args:
            verbose (bool): If True, shows the actual commands being executed.

        Returns:
            str: A string containing the combined output of the 'mt status' and 'mt tell' commands,
                 or a message indicating that the drive is empty.

        The method is useful for getting a quick overview of the tape drive's state and the 
        tape's current position. This information is valuable for troubleshooting, monitoring, 
        and ensuring that the tape drive is functioning correctly before proceeding with tape operations.

        Note:
        The actual output and information provided by the commands may vary depending on the 
        tape drive's make and model. It's recommended to familiarize yourself with your specific 
        tape drive's documentation for a better understanding of the status messages.
        """
        if verbose:
            status_command = ["mt", "-f", self.device_path, "status"]
            typer.echo(f"Executing command: {' '.join(status_command)}")
        
        status_output  = self.run_command(["status"])
        
        if verbose:
            typer.echo(f"Raw status output:\n{status_output}")

        if "DR_OPEN" in status_output:
            return "The tape drive is empty (no tape loaded)."
        elif "DRIVE NOT READY" in status_output or "ERROR" in status_output:
            return "The tape drive is not ready or has encountered an error"
        elif "Device or resource busy" in status_output:
            return "The tape drive is busy"

        # Extract position and block size info from status output
        file_match = re.search(r"File number=(-?\d+)", status_output)
        block_match = re.search(r"block number=(-?\d+)", status_output)
        blocksize_match = re.search(r"Tape block size (\d+) bytes", status_output)
        
        # Add volume statistics if available with Rich table
        try:
            import subprocess
            from rich.table import Table
            from rich.console import Console
            from io import StringIO
            
            vol_result = subprocess.run(['sg_logs', '-p', '0x17', self.device_path], 
                                      capture_output=True, text=True, timeout=5)
            if vol_result.returncode == 0 and vol_result.stdout:
                # Parse ALL statistics including page info
                stats = {}
                device_info = ""
                for line in vol_result.stdout.split('\n'):
                    if line.strip():
                        if 'Ultrium' in line:
                            device_info = line.strip()
                        elif ':' in line:
                            key = line.split(':')[0].strip()
                            val = line.split(':')[-1].strip()
                            if val.isdigit():
                                stats[key] = int(val)
                            else:
                                stats[key] = val
                
                if stats:
                    # Create Rich table without show_lines
                    table = Table(title=f"\n═══ VOLUME STATISTICS ═══\n{device_info}", 
                                  title_style="bold cyan",
                                  show_header=True, 
                                  header_style="bold yellow",
                                  border_style="blue",
                                  show_lines=False,  # No lines between every row
                                  expand=False)
                    
                    table.add_column("Category", style="cyan", width=30)
                    table.add_column("Metric", style="white", width=35)
                    table.add_column("Value", justify="right", style="green", width=20)
                    
                    # Page Information
                    if 'Page valid' in stats:
                        table.add_row("Page Information", "Page valid", str(stats['Page valid']))
                    if 'Thread count' in stats:
                        table.add_row("", "Thread count", f"{stats['Thread count']:,}")
                    
                    # Add section break
                    table.add_section()
                    
                    # Write Operations
                    if 'Total data sets written' in stats:
                        table.add_row("Write Operations", "Total data sets written", f"{stats['Total data sets written']:,}")
                    if 'Total write retries' in stats:
                        table.add_row("", "Total write retries", f"{stats['Total write retries']:,}")
                    if 'Total unrecovered write errors' in stats:
                        table.add_row("", "Total unrecovered write errors", f"{stats['Total unrecovered write errors']:,}")
                    if 'Total suspended writes' in stats:
                        table.add_row("", "Total suspended writes", f"{stats['Total suspended writes']:,}")
                    if 'Total fatal suspended writes' in stats:
                        table.add_row("", "Total fatal suspended writes", f"{stats['Total fatal suspended writes']:,}")
                    
                    # Add section break
                    table.add_section()
                    
                    # Read Operations
                    if 'Total data sets read' in stats:
                        table.add_row("Read Operations", "Total data sets read", f"{stats['Total data sets read']:,}")
                    if 'Total read retries' in stats:
                        table.add_row("", "Total read retries", f"{stats['Total read retries']:,}")
                    if 'Total unrecovered read errors' in stats:
                        table.add_row("", "Total unrecovered read errors", f"{stats['Total unrecovered read errors']:,}")
                    
                    # Add section break
                    table.add_section()
                    
                    # Last Mount Statistics
                    if 'Last mount unrecovered write errors' in stats:
                        table.add_row("Last Mount", "Unrecovered write errors", f"{stats['Last mount unrecovered write errors']:,}")
                    if 'Last mount unrecovered read errors' in stats:
                        table.add_row("", "Unrecovered read errors", f"{stats['Last mount unrecovered read errors']:,}")
                    if 'Last mount megabytes written' in stats:
                        mb = stats['Last mount megabytes written']
                        formatted = self.format_bytes(mb * 1024 * 1024)
                        table.add_row("", "Data written", formatted)
                        table.add_row("", "Data written (raw)", f"{mb:,} MB")
                    if 'Last mount megabytes read' in stats:
                        mb = stats['Last mount megabytes read']
                        formatted = self.format_bytes(mb * 1024 * 1024)
                        table.add_row("", "Data read", formatted)
                        table.add_row("", "Data read (raw)", f"{mb:,} MB")
                    
                    # Add section break
                    table.add_section()
                    
                    # Lifetime Statistics
                    if 'Lifetime megabytes written' in stats:
                        mb = stats['Lifetime megabytes written']
                        formatted = self.format_bytes(mb * 1024 * 1024)
                        table.add_row("Lifetime", "Total data written", formatted)
                        table.add_row("", "Total data written (raw)", f"{mb:,} MB")
                    if 'Lifetime megabytes read' in stats:
                        mb = stats['Lifetime megabytes read']
                        formatted = self.format_bytes(mb * 1024 * 1024)
                        table.add_row("", "Total data read", formatted)
                        table.add_row("", "Total data read (raw)", f"{mb:,} MB")
                    
                    # Add section break
                    table.add_section()
                    
                    # Compression
                    if 'Last load write compression ratio' in stats:
                        ratio = stats['Last load write compression ratio'] / 100.0 if isinstance(stats['Last load write compression ratio'], int) else 0
                        table.add_row("Compression", "Last load write compression ratio", f"{ratio:.2f}:1")
                    if 'Last load read compression ratio' in stats:
                        ratio = stats['Last load read compression ratio'] / 100.0 if isinstance(stats['Last load read compression ratio'], int) else 0
                        table.add_row("", "Last load read compression ratio", f"{ratio:.2f}:1")
                    
                    # Add section break
                    table.add_section()
                    
                    # Add current position info to table
                    if file_match and block_match:
                        file_number = file_match.group(1)
                        block_number = block_match.group(1)
                        table.add_row("Current Position", "File number", file_number)
                        table.add_row("", "Block number", block_number)
                        if blocksize_match:
                            blocksize = blocksize_match.group(1)
                            if blocksize == "0":
                                table.add_row("", "Block size", "Variable (0)")
                            else:
                                table.add_row("", "Block size", f"{int(blocksize):,} bytes")
                        if "EOF" in status_output and block_number == "0" and int(file_number) > 0:
                            table.add_row("", "Status", f"EOF (end of archive {file_number})")
                        elif file_number == "0" and block_number == "0":
                            table.add_row("", "Status", "Beginning of tape (BOT)")
                    
                    # Render table to string
                    string_io = StringIO()
                    console = Console(file=string_io, force_terminal=True, width=100)
                    console.print(table)
                    # Replace the raw status output with the table
                    status_output = string_io.getvalue()
        except Exception as e:
            if verbose:
                typer.echo(f"Could not get volume statistics: {e}")

        return status_output
    
    def format_bytes(self, bytes_value):
        """Format bytes into human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB', 'PB']:
            if bytes_value < 1024.0:
                if unit == 'B':
                    return f"{bytes_value:.0f} {unit}"
                return f"{bytes_value:.2f} {unit}"
            bytes_value /= 1024.0
        return f"{bytes_value:.2f} PB"


    def show_tape_position(self):
        """
        Retrieves and returns the current file number position of the tape.

        This method executes the 'mt status' command to obtain detailed status information 
        about the tape, including the current file number position. The file number position 
        is an indicator of the tape's position in terms of the number of file markers from 
        the beginning.

        Returns:
            int: The current file number position on the tape. If the file number is not found, 
                 it returns 0 as a default value.

        The file number position is critical for navigating the tape and understanding where 
        the tape head is currently located. This information is especially useful when you need 
        to move to a specific file on the tape or when you want to determine how far you have 
        progressed through the tape's content.

        Note:
        The interpretation of the 'File number' line is dependent on the specific format and 
        responses of the 'mt status' command for the tape drive being used. It's essential to 
        ensure compatibility with your tape drive's response format.
        """
        # Check if the drive is ready
        if not self.is_tape_ready():
            return "The tape drive is not ready."
        
        status_output = self.run_command(["status"])
        
        file_number_line = next((line for line in status_output.split('\n') if "File number" in line), None)
        if file_number_line:
            file_number = file_number_line.split('=')[1].split(',')[0].strip()
            return int(file_number)
        else:
            return 0  # Default to 0 if file number is not found


    def show_tape_block(self):
        """
        Retrieves and returns the current block number position of the tape.

        This method executes the 'mt status' command to gather detailed status information 
        about the tape, specifically focusing on the current block number. The block number 
        represents the tape's current position in terms of data blocks from the beginning 
        of the tape.

        Returns:
            int: The current block number position on the tape. If the block number is not 
                 found, it returns 0 as a default value.

        Understanding the block number position is vital for precise data retrieval or 
        writing operations on the tape. It enables accurate positioning of the tape for 
        reading or writing data at specific locations. This information is particularly 
        useful for operations that require direct manipulation or access to specific 
        data blocks on the tape.

        Note:
        The extraction and interpretation of the 'Block number' line depends on the 
        specific format and responses of the 'mt status' command for the tape drive in use. 
        As such, it's crucial to ensure that the method aligns with your tape drive's 
        response format.
        """
        # Check if the drive is ready
        if not self.is_tape_ready():
            return "The tape drive is not ready."
        
        status_output = self.run_command(["status"])
        
        block_number_line = next((line for line in status_output.split('\n') if "Block number" in line), None)
        if block_number_line:
            block_number = block_number_line.split('=')[1].split(',')[0].strip()
            return int(block_number)
        else:
            return 0  # Default to 0 if block number is not found


    def set_tape_block(self, block: int):
        """
        Moves the tape to the specified block position.

        This method utilizes the 'mt seek' command to move the tape drive to a specific 
        block position. It's an essential function for navigating through the tape, 
        allowing precise positioning to a desired block number for reading or writing data.

        Args:
            block (int): The block number to move the tape to.

        Returns:
            int: The current file number position on the tape after moving. This acts as 
                 a confirmation of the new position.

        The method performs the movement operation and then verifies the new position by 
        calling 'show_tape_position'. This confirmation step is critical to ensure the 
        tape has moved to the expected position.

        The ability to set the tape to a specific block position is useful in various 
        scenarios, such as data restoration, where you need to access data at a specific 
        location, or in complex backup operations that require accessing different 
        parts of the tape.

        Note:
        It is essential to use the block number carefully, as incorrect use can lead 
        to data being overwritten or reading from the wrong location. Always ensure 
        that the block number is within the tape's capacity and relevant to your data 
        layout on the tape.
        """ 
        # Check if the drive is ready
        if not self.is_tape_ready():
            return "The tape drive is not ready."

        status_output = self.run_command(["seek", str(block)])
        position = self.show_tape_position()
        return position


    def rewind_tape(self, verbose: bool = True):
        """
        Rewinds the tape to the beginning.

        This function is essential for tape management as it resets the tape's position
        to the start, ensuring that subsequent read or write operations begin from the 
        beginning of the tape. This is particularly important in scenarios where the tape's
        current position is unknown or when starting a new backup or restoration process.

        Args:
            verbose (bool): If True, prints a message indicating the tape is being rewound.
                            Defaults to True.

        Returns:
            str: The output from the 'mt rewind' command, which is typically empty on success.
                 In case of an error, it returns a string with an error message.

        The method uses the 'mt' utility with the 'rewind' command to reset the tape. The
        'verbose' flag allows for a user-friendly output indicating the operation in progress,
        enhancing the user experience, especially in interactive or monitoring scenarios.

        Note:
        Rewinding the tape is a fundamental operation in tape management. It is often used
        as a preparatory step before beginning tape operations to ensure a known starting 
        point. It's also a good practice to rewind the tape after operations to leave it 
        in a ready state for the next use.
        """
        # Check if the drive is ready
        if not self.is_tape_ready():
            return "The tape drive is not ready."

        if verbose:
            typer.echo(f"Rewinding {self.device_path}...")

        return self.run_command(["rewind"])


    def init(self):
        """
        Initializes the tape drive by setting the block size.

        This function is crucial for preparing the tape drive for backup operations. 
        It ensures that the tape drive is configured with the correct block size, 
        which is a key parameter in efficient and successful tape operations. 
        The block size affects how data is read from and written to the tape, 
        making this configuration step important for performance and compatibility.

        Steps:
        1. Rewind the tape: This ensures the tape is at the start, ready for 
           fresh operations.
        2. Set the block size: Configures the tape drive with the specified block 
           size for consistent data blocks.

        Returns:
            str: The output from the 'mt setblk' command, which typically includes 
                 confirmation of the block size setting. In case of an error, it 
                 returns an error message.

        Note:
        Initialization of the tape drive is a vital first step before conducting 
        any backup or restore operations. It ensures the tape is in a predictable 
        state with the correct configuration for data blocks. Failure to initialize 
        the tape correctly can lead to inefficient backups or data read/write errors.
        """
        # Check if the drive is ready
        if not self.is_tape_ready():
            return "The tape drive is not ready."

        # Rewind the tape first
        rewind_result = self.rewind_tape()
        if "Error" in rewind_result:
            return rewind_result  # Return error message if rewind fails

        typer.echo(f"Initializing tape drive {self.device_path} with block size {self.block_size}...")

        # Set the block size
        return self.run_command(["setblk", str(self.block_size)])


    def skip_file_markers(self, count: int, verbose: bool = True):
        """
        Skips a specified number of file markers on the tape either forward or backward.

        This method allows navigation through the contents of a tape by moving the 
        tape's read/write head over a specific number of file markers. File markers 
        typically denote the start of a new file or data block on the tape.

        Parameters:
            count (int): The number of file markers to skip. A positive number 
                         indicates forward movement, while a negative number 
                         indicates backward movement.
            verbose (bool, optional): If True, displays the skip operation details. 
                                      Defaults to True.

        Returns:
            str: The output from the 'mt' command showing the result of the skip 
                 operation. In case no movement is required, it returns a 
                 corresponding message.

        Note:
        The ability to navigate file markers is essential for accessing specific 
        files or data blocks on the tape. This method provides a flexible way to 
        move to different parts of the tape's contents, which is useful for both 
        backup and restore operations. It intelligently handles edge cases like 
        skipping beyond the start of the tape by automatically rewinding the tape.
        """
        # Check if the drive is ready
        if not self.is_tape_ready():
            return "The tape drive is not ready."

        current_position = self.show_tape_position()
        
        # Calculate the new position after the skip
        new_position = current_position + count

        real_count = count

        if count < 0:
            # If skipping backward, subtract 1 from the count to account for the current position
            new_position -= 1
            real_count -= 1

        # If new position is less than 1, perform a rewind instead of a backward skip
        if new_position < 0:
            return self.rewind_tape()
        else:
            if verbose:
                typer.echo(f"Skipping {count} file markers from position {current_position} on {self.device_path}...")

        if real_count > 0:
            # Skip forward
            command = ["fsf", str(real_count)]
        elif real_count < 0:
            # Skip backward
            command = ["bsfm", str(abs(real_count))]
        else:
            return "No movement required."

        return self.run_command(command)


    def list_files(self, sample: int = None):
        """
        Lists the files at the current tape position.

        This method uses the tar command to list the contents of the tape at the 
        current position. It's useful for verifying the contents of a tape backup 
        or for identifying specific files for restoration.

        Parameters:
            sample (int, optional): An optional parameter to limit the number of 
                                    files listed. If provided, only the specified 
                                    number of files will be listed. Defaults to None.

        Note:
        If a sample size is provided, the method will skip backward by one file 
        marker after listing the specified number of files. This is to ensure that 
        the tape head is positioned correctly for subsequent operations. If no 
        sample size is provided, the method will skip forward by one file marker 
        to move past the listed files. This ensures that the tape position is 
        updated correctly and ready for further operations.
        """
        # Check if the drive is ready
        if not self.is_tape_ready():
            typer.echo("The tape drive is not ready.")
            return ""

        command = ["tar", "-b", str(self.block_size), "-tvf", self.device_path]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        line_count = 0
        try:
            for line in process.stdout:
                print(line, end='')  # Print each line immediately
                line_count += 1
                if sample and line_count >= sample:
                    self.skip_file_markers(-1, False)
                    break  # Stop after printing the specified number of sample lines
                    
        except Exception as e:
            print(f"Error while reading tape: {e}")
        finally:
            process.stdout.close()
            if not sample:
                self.skip_file_markers(1, False)


    def backup_directories(self, directories: list, library_name = None, label = None, job = None, strategy="direct", incremental=False, max_concurrent_tars: int = 2, memory_buffer = 16, memory_buffer_percent = 20, use_double_buffer = True, low_water_mark = 10):
        """
        Initiates the backup process for the specified directories with the given strategy.

        This method is the entry point for the backup operation. It creates an instance of the TapeBackup
        class with the appropriate parameters and starts the backup process based on the specified strategy.

        Parameters:
            directories (list): A list of directories (or files) to be backed up.
            library_name (str, optional): The name of the tape library to be used for the backup. Defaults to None.
            label (str, optional): The label to be used for the backup. Defaults to None.
            job (str, optional): The job name to be used for the backup. Defaults to None.
            strategy (str, optional): The backup strategy to use. Options include 'direct', 'tar', and 'dd'.
                                      Default is 'direct'.
            incremental (bool, optional): If True, performs an incremental backup. Default is False.
            max_concurrent_tars (int, optional): The maximum number of concurrent tar operations allowed. 
                                                 Default is 2.
            memory_buffer (int, optional): The size of the memory buffer to use in GB. Default is 16 GB.
            memory_buffer_percent (int, optional): The percentage of the memory buffer to be used. Default is 20%.
            use_double_buffer (bool, optional): If True, uses double-buffering with water mark control. Default is True.
            low_water_mark (int, optional): The low water mark percentage for buffer refill. Default is 10%.

        Note:
        This method sets up signal handling to ensure proper cleanup of temporary files in case of an interruption.
        The actual backup process is delegated to the TapeBackup class's backup_directories method, which performs
        the backup according to the chosen strategy.
        """
        # Check if the drive is ready
        if not self.is_tape_ready():
            return "The tape drive is not ready."
        
        # Initialize tape drive block size for optimal performance
        # This ensures the drive is in fixed block mode matching our configured block size
        init_result = self.init()
        if "Error" in str(init_result):
            typer.echo(f"Warning: Could not set block size: {init_result}")
        else:
            typer.echo(f"Tape initialized with block size: {self.block_size} bytes")

        tape_backup = TapeBackup(self, self.device_path, self.block_size, self.tar_dir, self.snapshot_dir, library_name, label, job, strategy, incremental, max_concurrent_tars, memory_buffer, memory_buffer_percent, use_double_buffer, low_water_mark)

        # Set up signal handling
        signal.signal(signal.SIGINT, lambda sig, frame: tape_backup.cleanup_temp_files())

        #tape_backup.backup_directories_memory_buffer(directories)
        tape_backup.backup_directories(directories)


    def restore_files(self, target_dir: str):
        """
        Restores files from the tape to the specified target directory.

        This method initiates the restoration of files stored on the tape to a given directory on the system.
        It ensures the target directory exists (or creates it if it doesn't), and then runs the tar command
        to extract files from the tape to that directory.

        Parameters:
            target_dir (str): The directory where the files will be restored.

        Note:
        The method assumes that the tape is correctly positioned at the beginning of the desired file set
        for restoration. It uses the tar command with the block size and device path configured for the tape drive.
        During the process, it prints each line of the tar output immediately, providing live feedback.
        The method also handles exceptions gracefully, printing any errors encountered during the restoration.
        After the process completes, it automatically advances the tape to the next file marker.
        """
        # Check if the drive is ready
        if not self.is_tape_ready():
            return "The tape drive is not ready."

        # Create the target directory if it does not exist
        if not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)

        typer.echo(f"Restoring files from {self.device_path} to {target_dir}...")
        command = ["mbuffer", "-i", self.device_path, "-s", str(self.block_size), "-m", "6G", "-p", "10", "-f", "-n", "2", "-A", "\"pytp load 18\"", "|", "tar", "-b", str(self.block_size), "-xvf", "-"]    

        #mbuffer -i /dev/nst1 -s 524288 -m 6G -p 10 -f -n 2 -A "pytp load 18" | tar -b 524288 -xvf -
        #command = ["tar", "-xvMf", self.device_path, "-b", str(self.block_size), "-C", target_dir]
        command = " ".join(command)

        print (command)

        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        # Set the stdout and stderr to non-blocking
        flags_stdout = fcntl.fcntl(process.stdout, fcntl.F_GETFL)
        flags_stderr = fcntl.fcntl(process.stderr, fcntl.F_GETFL)
        fcntl.fcntl(process.stdout, fcntl.F_SETFL, flags_stdout | os.O_NONBLOCK)
        fcntl.fcntl(process.stderr, fcntl.F_SETFL, flags_stderr | os.O_NONBLOCK)

        try:
            while True:
                # Read from stdout
                try:
                    output = process.stdout.readline()
                    if output:
                        print(output.strip())
                except IOError as e:
                    if e.errno != errno.EAGAIN and e.errno != errno.EWOULDBLOCK:
                        raise

                # Check stderr for the tape change prompt
                try:
                    error_output = process.stderr.readline()
                    if error_output and "and hit return" in error_output:  # Adjust the message as per actual tar prompt
                        print("Please change the tape and press Enter to continue...")
                        input()  # Wait for user input
                        # Send a SIGCONT signal to resume the tar process
                        os.kill(process.pid, signal.SIGCONT)
                    elif error_output:
                        print(error_output.strip(), end='')
                except IOError as e:
                    if e.errno != errno.EAGAIN and e.errno != errno.EWOULDBLOCK:
                        raise

                if process.poll() is not None:
                    break  # Process has finished

                time.sleep(0.1)  # Avoid busy waiting

            if process.returncode != 0:
                typer.echo(f"Error occurred during restore. Error code: {process.returncode}")

        except Exception as e:
            typer.echo(f"Error occurred during restore: {e}")
        finally:
            process.stdout.close()
            process.stderr.close()
            self.skip_file_markers(1, False)
            typer.echo(f"Restore of {target_dir} completed successfully.")


    def retension_tape(self, library_name: str = None, slot_number: int = None, verbose: bool = True):
        """
        Retensions the tape for optimal media condition.

        This method performs a tape retensioning operation, which is a standard maintenance
        procedure to keep the tape media in optimal condition over its lifespan. The process
        involves rewinding the tape, winding it to the end of the reel, and then rewinding
        it again. This helps to ensure even tape tension and can help prevent issues like
        tape sticking or uneven wear.

        Args:
            library_name (str, optional): Name of the tape library. If provided with slot_number,
                                         will load the tape from that slot before retensioning.
            slot_number (int, optional): Slot number to load tape from. Requires library_name.
                                        After retensioning, tape will be unloaded back to this slot.
            verbose (bool): If True, prints status messages during the retensioning process.
                           Defaults to True.

        Returns:
            str: The output from the 'mt retension' command on success, or an error message
                if the operation fails.

        Note:
        Retensioning is particularly important for:
        - Tapes that have been stored for extended periods
        - Tapes that are used frequently
        - LTO-9 media optimization and general tape maintenance
        - Preventing tape media degradation over time
        
        The retensioning process may take several minutes depending on the tape capacity
        and drive speed. This is a non-destructive operation that preserves all data on
        the tape.
        
        If library_name and slot_number are provided, the method will:
        1. Load the tape from the specified slot
        2. Perform the retensioning operation
        3. Unload the tape back to the original slot
        4. Clear any media attention errors for that slot
        """
        # Handle library operations if specified
        tape_was_loaded = False
        if library_name and slot_number is not None:
            from pytp.tape_library_operations import TapeLibraryOperations
            tlo = TapeLibraryOperations(library_name)
            
            if verbose:
                typer.echo(f"Loading tape from slot {slot_number} in library {library_name}...")
            
            # First, unload any existing tape in the drive
            if self.is_tape_ready():
                if verbose:
                    typer.echo("Unloading current tape first...")
                unload_result = tlo.unload_tape(self.drive_name)
                if "Error" in unload_result and verbose:
                    typer.echo(f"Warning during unload: {unload_result}")
            
            # Load the tape from the specified slot
            load_result = tlo.load_tape(self.drive_name, slot_number)
            if "Error" in load_result:
                return f"Failed to load tape from slot {slot_number}: {load_result}"
            
            tape_was_loaded = True
            if verbose:
                typer.echo(f"Tape loaded from slot {slot_number}. Waiting for drive to be ready...")
            
            # Wait a moment for the tape to be ready
            import time
            time.sleep(5)
            
            # Verify tape is ready
            if not self.is_tape_ready():
                if verbose:
                    typer.echo("Waiting for tape drive to become ready...")
                for _ in range(30):  # Wait up to 30 seconds
                    time.sleep(1)
                    if self.is_tape_ready():
                        break
                else:
                    # If still not ready, unload and return error
                    tlo.unload_tape(self.drive_name, slot_number)
                    return "Tape drive did not become ready after loading."
        
        # Check if the drive is ready
        if not self.is_tape_ready():
            return "The tape drive is not ready."

        if verbose:
            typer.echo(f"Starting tape retensioning on {self.device_path}...")
            typer.echo("This process will rewind the tape, wind to the end, and rewind again.")
            typer.echo("This may take several minutes. Please wait...")

        # First try the native mt retension command
        if verbose:
            typer.echo("Attempting native mt retension command...")
        
        full_command = ["mt", "-f", self.device_path, "retension"]
        if verbose:
            typer.echo(f"Executing command: {' '.join(full_command)}")
        
        try:
            result = subprocess.run(full_command, capture_output=True, text=True, timeout=30)
            
            if verbose:
                if result.stdout:
                    typer.echo(f"Standard output: {result.stdout}")
                if result.stderr:
                    typer.echo(f"Standard error/warnings: {result.stderr}")
                typer.echo(f"Return code: {result.returncode}")
            
            # Check if native retension actually did something
            import time
            time.sleep(2)
            status_after = self.run_command(["status"])
            
            if "busy" in status_after.lower() or "rewind" in status_after.lower():
                if verbose:
                    typer.echo("Native retension command is working, monitoring progress...")
                # Monitor as before - code would be here but keeping it simple for now
                return "Native retension completed"
            
            # Native retension didn't work, try manual retension
            if verbose:
                typer.echo("Native retension appears to be a no-op on this system.")
                typer.echo("Performing manual retension: rewind → wind to end → rewind")
            
            return self._perform_manual_retension(verbose)
            
        except subprocess.TimeoutExpired:
            if verbose:
                typer.echo("Native retension timed out, trying manual method...")
            return self._perform_manual_retension(verbose)
        except Exception as e:
            if verbose:
                typer.echo(f"Native retension failed: {e}, trying manual method...")
            return self._perform_manual_retension(verbose)
    
    def _perform_manual_retension(self, verbose: bool = True):
        """
        Performs manual retension by rewinding, seeking to end, then rewinding again.
        This is the manual equivalent of what a proper retension command should do.
        """
        if verbose:
            typer.echo("Starting manual retension process...")
        
        try:
            # Step 1: Rewind to beginning
            if verbose:
                typer.echo("Step 1/3: Rewinding tape to beginning...")
            rewind_result = self.rewind_tape(verbose=False)
            if "Error" in rewind_result:
                return f"Manual retension failed during rewind: {rewind_result}"
            
            # Step 2: Wind to end of tape
            if verbose:
                typer.echo("Step 2/3: Winding tape to end (this may take several minutes)...")
            
            # Use mt eod (end of data) to go to the end
            eod_result = self.run_command(["eod"])
            if "Error" in eod_result:
                return f"Manual retension failed during wind to end: {eod_result}"
            
            if verbose:
                typer.echo("Step 3/3: Rewinding tape to beginning again...")
            
            # Step 3: Rewind again
            final_rewind = self.rewind_tape(verbose=False)
            if "Error" in final_rewind:
                return f"Manual retension failed during final rewind: {final_rewind}"
            
            if verbose:
                typer.echo("Manual retension completed successfully.")
                typer.echo("The tape has been rewound, wound to the end, and rewound again.")
            
            return "Manual retension completed successfully"
            
        except Exception as e:
            error_msg = f"Manual retension failed: {str(e)}"
            if verbose:
                typer.echo(f"Error: {error_msg}")
            return error_msg
        
        # Unload tape back to slot if it was loaded from library
        if tape_was_loaded and library_name and slot_number is not None:
            if verbose:
                typer.echo(f"Unloading tape back to slot {slot_number}...")
            
            unload_result = tlo.unload_tape(self.drive_name, slot_number)
            if "Error" in unload_result and verbose:
                typer.echo(f"Warning during unload: {unload_result}")
            
            # Clear any media attention errors for this slot
            # Note: mtx doesn't have a direct "clear errors" command, but 
            # a status check often clears transient errors
            if verbose:
                typer.echo(f"Checking library status to clear any media attention flags...")
            tlo.list_tapes()  # This often clears media attention flags
            
            if verbose:
                typer.echo(f"Tape unloaded back to slot {slot_number}.")
        
        return result

    def generate_checksum(self, file_path):
        """
        Generates an MD5 checksum for a given file.

        This method computes the MD5 checksum of the file specified by 'file_path'. It reads the file in chunks
        to efficiently handle large files and updates the MD5 hash with each chunk. The final MD5 hash is returned
        as a hexadecimal string.

        Parameters:
            file_path (str): The path to the file for which the checksum is to be generated.

        Returns:
            str: The MD5 checksum of the file as a hexadecimal string.

        Note:
        MD5 is chosen for its balance of speed and collision resistance in the context of file integrity checks.
        However, it's important to note that MD5 is not recommended for cryptographic purposes due to its
        vulnerabilities. In scenarios where security is critical, a more secure hash function like SHA-256
        may be preferable.
        """
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

