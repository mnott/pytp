# tape_operations.py

import subprocess
import typer
import hashlib
import os
import signal
from pytp.config_manager import ConfigManager
from pytp.tape_backup    import TapeBackup

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
        self.block_size    = tape_details.get('block_size', 2048)  # Default block size if not specified
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


    def show_tape_status(self):
        """
        Retrieves and returns the current status and position of the tape in the tape drive.

        This method combines the output of two commands: 'mt status' and 'mt tell'. 
        The 'mt status' command provides general status information about the tape drive, 
        such as whether it's online or any errors have been encountered. The 'mt tell' 
        command returns the current position of the tape in terms of the number of blocks 
        from the beginning.

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
        status_output  = self.run_command(["status"])

        if "DR_OPEN" in status_output:
            return "The tape drive is empty (no tape loaded)."
        elif "DRIVE NOT READY" in status_output or "ERROR" in status_output:
            return "The tape drive is not ready or has encountered an error"
        elif "Device or resource busy" in status_output:
            return "The tape drive is busy"

        status_output += self.run_command(["tell"])
        return status_output


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


    def backup_directories(self, directories: list, library_name = None, label = None, job = None, strategy="direct", incremental=False, max_concurrent_tars: int = 2, memory_buffer = 6, memory_buffer_percent = 40):
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
            memory_buffer (int, optional): The size of the memory buffer to use in GB. Default is 6 GB.
            memory_buffer_percent (int, optional): The percentage of the memory buffer to be used. Default is 40%.

        Note:
        This method sets up signal handling to ensure proper cleanup of temporary files in case of an interruption.
        The actual backup process is delegated to the TapeBackup class's backup_directories method, which performs
        the backup according to the chosen strategy.
        """
        # Check if the drive is ready
        if not self.is_tape_ready():
            return "The tape drive is not ready."

        tape_backup = TapeBackup(self, self.device_path, self.block_size, self.tar_dir, self.snapshot_dir, library_name, label, job, strategy, incremental, max_concurrent_tars, memory_buffer, memory_buffer_percent)

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
        command = ["tar", "-xvf", self.device_path, "-b", str(self.block_size), "-C", target_dir]

        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        line_count = 0
        try:
            for line in process.stdout:
                print(line, end='')  # Print each line immediately
                line_count += 1
        except Exception as e:
            typer.echo(f"Error occurred during restore of {target_dir}: {e}")
        finally:
            process.stdout.close()
            self.skip_file_markers(1, False)
            typer.echo(f"Restore of {target_dir} completed successfully.")


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

