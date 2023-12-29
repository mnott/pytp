# tape_backup.py
import json
import os
import tempfile
import subprocess
import threading
import typer
import time
from rich.progress import Progress

class TapeBackup:
    """
    The TapeBackup class provides functionalities to backup directories to a tape drive.

    This class manages the backup process by generating tar files from specified directories
    and writing them to a tape drive using either direct tar-to-tape streaming or an intermediate
    storage strategy. It supports concurrent tar file generation and ensures that files
    are written to the tape in the specified order.

    Attributes:
        device_path                (str): Stores the device path of the tape drive.
        block_size                 (int): Stores the block size.
        max_concurrent_tars        (int): Stores the maximum number of tar files that can be generated concurrently.
        tar_dir                    (str): Stores the path of the directory for tar files.
        label                      (str): Stores the label of the backup.
        strategy                   (str): Stores the backup strategy to be used (direct or tar (via memory buffer), or dd (without memory buffer)).
        incremental               (bool): Flag to indicate whether incremental backup is enabled.
        max_concurrent_tars        (int): The maximum number of concurrent tar operations.
        memory_buffer              (int): The size of the memory buffer to be used for tar and dd operations.
        memory_buffer_percent      (int): The percentage the memory buffer needs to be filled before streaming to tape.
        all_tars_generated        (bool): Flag to indicate whether all tar files have been generated.
        tars_to_be_generated      (list): List to keep track of tar files that need to be generated.
        tars_generating            (set): Set to keep track of tar files currently being generated.
        tars_generated            (list): List to keep track of generated tar files, maintaining their order.
        tars_to_write             (list): List of tar files that are ready to be written to the tape.
        generating_lock (threading.Lock): Lock to manage concurrent access to tars_generating.
        generated_lock  (threading.Lock): Lock to manage concurrent access to tars_generated.
        to_write_lock   (threading.Lock): Lock to manage concurrent access to tars_to_write.
        running                   (bool): Flag to control the running state of the backup process.
        semaphore  (threading.Semaphore): Semaphore to control the number of concurrent tar file generation operations.

    The class provides various methods to manage the backup process, including tar file generation, writing to tape, and cleanup.
    """    

    # Define backup strategies
    STRATEGY_DIRECT = 'direct' # direct file to tape streaming, using memory buffer
    STRATEGY_TAR    = 'tar'    # creates tar files first, then writes to tape, using memory buffer
    STRATEGY_DD     = 'dd'     # creates tar files first, then writes to tape using dd, without memory buffer

    def __init__(self, device_path, block_size, tar_dir, snapshot_dir, label = None, strategy = "direct", incremental = False, max_concurrent_tars = 2, memory_buffer = 6, memory_buffer_percent = 40):
        """
        Initializes the TapeBackup class.

        Args:
            device_path                (str): The path to the tape drive device.
            block_size                 (int): The block size to be used for tar and dd operations.
            tar_dir                    (str): The root directory where tar files will be stored.
            max_concurrent_tars        (int): The maximum number of concurrent tar operations.
            strategy                   (str): The backup strategy to be used (direct, tar, or dd).
            label                      (str): The label of the backup.
            memory_buffer              (int): The size of the memory buffer to be used for tar and dd operations.
            memory_buffer_percent      (int): The percentage the memory buffer needs to be filled before streaming to tape.
        """        
        self.device_path           = device_path
        self.block_size            = block_size
        self.max_concurrent_tars   = max_concurrent_tars
        self.memory_buffer         = f"{memory_buffer}G"
        self.memory_buffer_percent = memory_buffer_percent
        self.tar_dir               = tar_dir
        self.snapshot_dir          = snapshot_dir
        self.label                 = label
        self.strategy              = strategy
        self.incremental           = incremental
        self.all_tars_generated    = False
        self.tars_to_be_generated  = []
        self.tars_generating       = set()
        self.tars_generated        = []
        self.tars_to_write         = []
        self.generating_lock       = threading.Lock()
        self.generated_lock        = threading.Lock()
        self.to_write_lock         = threading.Lock()
        self.running               = True
        self.semaphore             = threading.Semaphore(max_concurrent_tars)
        self.progress              = Progress()


    def generate_tar_file(self, directory, index):
        """
        Generates a tar file for the specified directory and manages its state in the backup process.

        This method is designed to be run in a separate thread for each directory. It uses a semaphore to limit
        the number of concurrent tar file generation operations, ensuring that the system resources are not
        overwhelmed.

        Args:
            directory (str): The directory path to be archived into a tar file.
            index     (int): The index of the directory in the original list of directories. This is used to maintain
                             the order of tar files consistent with the order of input directories.

        Process:
            1. Acquires a semaphore token to limit concurrent tar operations.
            2. Checks if the backup process is still running; exits if not.
            3. Generates a temporary tar file path and adds it to the tars_generating set.
            4. Executes the tar command to create the tar file.
            5. Once the tar file is created, moves it from tars_generating to tars_generated.
            6. Calls check_and_move_to_write to potentially queue the tar file for writing to tape.
            7. If this is the last tar file to be generated, sets the all_tars_generated flag to True.
        """        
        with self.semaphore:
            if not self.running:
                return

            dir_name = os.path.basename(directory)
            tar_path = os.path.join(self.tar_dir, f"{dir_name}.tar")
            self.tars_generating.add(tar_path)

            backup_json    = self.get_json_filename(directory, label=self.label)
            backup_history = self.load_backup_history(backup_json)

            with self.progress:
                if self.incremental:
                    changed_files = self.get_changed_files_list(directory, backup_history)

                    if not changed_files:
                        typer.echo(f"\nNo changes in {directory}, skipping backup.")
                        return
                    current_state = self.scan_directory(directory)
                    incremental_files = {filepath: current_state[filepath] for filepath in changed_files}
                    backup_entry = {'type': 'incremental', 'files': incremental_files}
                else:
                    current_state = self.scan_directory(directory)
                    backup_entry = {
                        'files': {
                            filepath: (
                                {'mtime': attrs['mtime'], 'size': attrs['size']}
                                if attrs['type'] == 'file' else
                                {'type': 'symlink', 'target': attrs.get('target'), 'valid': attrs.get('valid', False)}
                            )
                            for filepath, attrs in current_state.items()
                        }
                    }
                    backup_history = []  # Reset history for a full backup

            # Update backup history and save JSON
            backup_history.append(backup_entry)
            with open(backup_json, 'w') as file:
                json.dump(backup_history, file)    
                
            # Write files to be backed up to a list file for tar
            files_to_backup = backup_entry['files']

            # Write files to be backed up to a temporary file in self.tar_dir
            with tempfile.NamedTemporaryFile(mode='w+', dir=self.tar_dir, delete=False) as temp_file:
                backup_files_list_path = temp_file.name
                for file in files_to_backup:
                    temp_file.write(f"{file}\n")            

            tar_command = ["tar", "-cvf", tar_path, "-T", backup_files_list_path]
            tar_command.extend(["-b", str(self.block_size)])
            # tar_command = ["tar", "-cvf", tar_path, "-b", str(self.block_size), directory]

            subprocess.run(tar_command)
            os.remove(backup_files_list_path)  # Remove the temporary file after use

            with self.generating_lock:
                self.tars_generating.remove(tar_path)
            with self.generated_lock:
                self.tars_generated.append((index, tar_path))

            self.check_and_move_to_write()

            if len(self.tars_to_be_generated) == 1:
                self.all_tars_generated = True


    def write_tar_files_to_tape(self):
        """
        Writes tar files to the tape drive in the order they were added to the tars_to_write list.

        This method runs in a loop, continuously checking for tar files that are ready to be written.
        It ensures that tar files are written to tape in the correct order.

        Process:
            1. The loop runs as long as there are tar files to write or the backup process is still generating tar files.
            2. Acquires a lock to ensure exclusive access to the tars_to_write list.
            3. Checks if there are any tar files ready to be written.
                - If the list is empty, it continues back to the start of the loop.
            4. Pops the first tar file from the tars_to_write list and writes it to tape.
            5. After writing, it releases the lock and continues to the next iteration.
        """        
        while self.tars_to_write or (self.running and not self.all_tars_generated):
            with self.to_write_lock:
                if not self.tars_to_write:
                    continue
                tar_to_write = self.tars_to_write.pop(0)

                if self.strategy == self.STRATEGY_TAR:
                    self.write_to_tape_tar(tar_to_write)
                elif self.strategy == self.STRATEGY_DD:
                    self.write_to_tape_dd(tar_to_write)


    def write_to_tape_tar(self, tar_path):
        """
        Writes a single tar file to the tape drive and logs the process.

        Parameters:
        - tar_path: The path to the tar file to be written to tape.

        Process:
        1. Opens a log file (dd_log_path) for appending output messages.
        2. Writes a log entry indicating the start of writing the specified tar file.
        3. Constructs a shell command that uses `cat` to read the tar file and pipes it through `mbuffer` to the tape drive.
             - `mbuffer` is used to manage the buffer and ensure efficient writing to the tape drive.
             - The command also redirects `mbuffer`'s verbose output to the log file for monitoring and debugging.
        4. Executes the command using `subprocess.Popen` to allow asynchronous processing and capturing of stderr for logging.
        5. Logs any errors or messages produced by the `mbuffer` process to the log file.
        6. Waits for the command to complete and checks for any non-zero return code, indicating an error.
        7. After writing, sends an 'end-of-file' marker to the tape drive using the `mt` command.
        8. Removes the tar file from the filesystem to free up space.

        This method ensures that each tar file is written securely and efficiently to the tape drive while providing detailed logs of the operation.
        """        
        dd_log_path = os.path.join(self.tar_dir, "dd_output.log")
        with open(dd_log_path, 'a') as dd_log:
            dd_log.write(f"\nWriting {tar_path} to tape...\n")
            dd_log.flush()

            # Use cat to read the tar file and pipe it through mbuffer to the tape drive
            backup_command = f"cat {tar_path} | mbuffer -P {self.memory_buffer_percent} -m {self.memory_buffer} -s {self.block_size} -v 1 -o {self.device_path} -l {dd_log_path} -v 3"
            process = subprocess.Popen(backup_command, shell=True, stdout=subprocess.PIPE, stderr=dd_log, text=True)

            process.wait()
            if process.returncode != 0:
                typer.echo(f"Error occurred during backup of {tar_path}. Error code: {process.returncode}")

        # Write an end of file marker. It appears the device does it automatically, but just in case
        # we want to remember, here is how it would be done manually.
        # subprocess.run(['mt', '-f', self.device_path, 'weof', '1'])
        os.remove(tar_path)


    def write_to_tape_dd(self, tar_path):
        """
        Writes a tar file to the tape drive using the dd command and logs the process.

        Parameters:
        - tar_path: The path to the tar file to be written to tape.

        Process:
        1. Opens or creates a log file (dd_log_path) for appending process messages.
        2. Writes an entry in the log file indicating the initiation of writing the specified tar file to tape.
        3. Constructs and executes a dd command to perform the writing operation.
            - The 'if' parameter specifies the input file (tar file) to read from.
            - The 'of' parameter designates the output file (tape drive) to write to.
            - The 'bs' parameter sets the block size for data transfer.
            - The 'status=progress' option enables real-time progress output.
        4. Captures and logs the standard error output of the dd command for monitoring and troubleshooting.
        5. Upon completion, sends an 'end-of-file' marker to the tape drive using the 'mt' command.
        6. Removes the tar file from the filesystem to conserve space.

        This method offers a straightforward approach to writing tar files to tape using dd. It is suitable for
        situations where mbuffer is not required or preferred, providing a direct and efficient data transfer mechanism.
        """        
        dd_log_path = os.path.join(self.tar_dir, "dd_output.log")
        with open(dd_log_path, 'a') as dd_log:
            dd_log.write(f"\nWriting {tar_path} to tape...\n")
            dd_log.flush()
            dd_command = ["dd", "if={}".format(tar_path), "of={}".format(self.device_path), "bs={}".format(self.block_size), "status=progress"]
            subprocess.run(dd_command, stderr=dd_log)

        # Write an end of file marker. It appears the device does it automatically, but just in case
        # we want to remember, here is how it would be done manually.
        # subprocess.run(['mt', '-f', self.device_path, 'weof', '1'])
        os.remove(tar_path)


    def continuously_check_and_move(self):
        """
        Continuously checks and moves tar files from the generated list to the writing queue.

        Process:
        1. The method enters a loop that runs until all tar files are generated and the list of generated tar files is empty.
        2. Within the loop, it calls the check_and_move_to_write() method.
            - This method is responsible for moving tar files that are ready to be written from the generated list to the writing queue.
        3. The loop includes a sleep interval of 1 second to prevent high CPU usage, allowing other processes to execute.

        This method ensures that as soon as a tar file is ready (i.e., fully generated), it is promptly moved
        to the writing queue. The continuous checking mechanism is crucial for maintaining the flow of the backup process,
        ensuring that tar files are written to tape as soon as they become available. It plays a key role in optimizing
        the tape writing process, especially when dealing with large or numerous files.
        """        
        while not self.all_tars_generated or self.tars_generated:
            self.check_and_move_to_write()
            time.sleep(1)


    def check_and_move_to_write(self):
        """
        Checks and moves tar files from the 'generated' list to the 'to write' queue based on their generation order.

        Process:
        1. The method acquires locks for both the 'generated' and 'to write' lists to ensure thread-safe access.
        2. It checks if there are any tar files left to be generated. If not, the method returns without doing anything.
        3. It retrieves the index and path of the next expected tar file from the 'tars_to_be_generated' list.
        4. The method then iterates over the 'tars_generated' list to find a match for the expected tar file.
        5. Once the matching tar file is found:
            - It is appended to the 'tars_to_write' list, making it ready for writing to tape.
            - The method then removes this tar file from both the 'tars_generated' list and the 'tars_to_be_generated' list.
            - The loop breaks after moving the tar file, ensuring that only the next expected file in order is processed.

        This method ensures that tar files are written to tape in the same order as they were originally planned to
        be generated. It handles the crucial task of synchronizing the generation and writing processes, maintaining
        the integrity and order of the backup data.
        """        
        with self.generated_lock, self.to_write_lock:
            if self.tars_to_be_generated:
                expected_index, expected_tar = self.tars_to_be_generated[0]
                for generated_index, generated_tar in self.tars_generated:
                    if generated_index == expected_index:
                        self.tars_to_write.append(generated_tar)
                        self.tars_generated.remove((generated_index, generated_tar))
                        self.tars_to_be_generated.pop(0)
                        break


    def backup_directories(self, directories):
        """
        Orchestrates the backup process based on the selected strategy.

        This method determines the appropriate backup method to use based on the
        strategy set during initialization. The strategy can be one of the following:
        - STRATEGY_DIRECT: Directly stream files to tape using a memory buffer.
        - STRATEGY_TAR:    Create tar files first, then write to tape using a memory buffer.
        - STRATEGY_DD:     Create tar files first, then write to tape using the dd command.

        Depending on the strategy, this method delegates the backup operation to
        the respective specialized method (backup_directories_direct, 
        backup_directories_tar, etc.).

        Args:
            directories (list): A list of directory paths (or files) to be backed up.

        Raises:
            ValueError: If an invalid backup strategy is specified.

        Note:
        - The STRATEGY_DIRECT approach is generally faster but less flexible, as it
          streams data directly to the tape without intermediate storage.
        - The STRATEGY_TAR approach provides more control and allows for intermediate
          storage and manipulation of data but can be slower due to the additional
          steps involved. It uses the mbuffer command for writing to tape.
        - The STRATEGY_DD approach is similar to STRATEGY_TAR but uses the dd command
          for writing to tape, bypassing the need for a memory buffer.
        """
        if self.strategy == self.STRATEGY_DIRECT:
            self.backup_directories_direct(directories)
        elif self.strategy == self.STRATEGY_TAR:
            self.backup_directories_tar(directories)
        elif self.strategy == self.STRATEGY_DD:
            self.backup_directories_tar(directories)
        else:
            raise ValueError("Invalid backup strategy")


    def backup_directories_tar(self, directories):
        """
        Initiates the backup process for the given list of directories.

        Process:
        1. Generates a list of tar file paths ('tars_to_be_generated') based on the provided directories.
        2. Creates and starts separate threads ('tar_threads') for generating tar files for each directory.
        3. Starts a 'check_thread' to continuously monitor and move generated tar files to the 'to write' list.
        4. Initiates the 'dd_thread' for writing tar files to tape from the 'to write' list.
        5. Waits for all tar generation threads to complete.
        6. Once all tars are generated, sets 'all_tars_generated' to True.
        7. Waits for the 'check_thread' to finish processing all generated tar files.
        8. Waits for the 'dd_thread' to complete writing all tar files to tape.
        9. Finally, calls 'cleanup_temp_files' to remove any temporary files.

        This method orchestrates the entire backup process, ensuring that tar files are generated, queued,
        and written to tape in a controlled and orderly manner. It leverages multithreading to efficiently
        handle the generation and writing of tar files, ensuring optimal utilization of system resources.

        Parameters:
        directories (list): A list of directory paths that need to be backed up.

        Note:
        The method assumes that each directory in the 'directories' list is a valid path and tha
        the tape device and block size have been correctly configured.
        """
        self.tars_to_be_generated = [(index, os.path.join(self.tar_dir, f"{os.path.basename(dir)}.tar")) for index, dir in enumerate(directories)]

        tar_threads = [threading.Thread(target=self.generate_tar_file, args=(directory, index)) for index, directory in enumerate(directories)]
        for thread in tar_threads:
            thread.start()

        check_thread = threading.Thread(target=self.continuously_check_and_move)
        check_thread.start()

        dd_thread = threading.Thread(target=self.write_tar_files_to_tape)
        dd_thread.start()

        for thread in tar_threads:
            thread.join()

        self.all_tars_generated = True
        check_thread.join()
        dd_thread.join()

        self.cleanup_temp_files()


    def backup_directories_direct(self, directories: list):
        """
        Performs direct backup of directories to tape without pre-generating tar files.

        This method offers an alternative backup strategy where directories are directly
        streamed to the tape drive using tar and mbuffer. This approach bypasses the step of
        pre-generating tar files, thus allowing for a more straightforward and potentially
        faster backup process for certain use cases - especially when dealing with large files.

        Process:
        1. Iterates through each directory in the 'directories' list.
        2. For each directory, constructs a backup command that uses 'tar' to create an archive and pipes it directly to 'mbuffer', which then writes it to the tape device.
        3. Executes the command and monitors the process, printing the standard error output to the console for real-time feedback.
        4. Checks for errors upon completion of each backup operation and continues with the next directory.
        5. Completes the backup process for all directories and returns a completion message.

        Parameters:
        directories (list): A list of directory paths that need to be backed up.

        Returns:
        str: A message indicating the completion of all backup operations.

        Note:
        This method is designed for scenarios where the immediate writing of data to tape is preferred over
        the creation of intermediate tar files. It assumes that the tape device and block size have been
        correctly configured and that the directories listed are valid and accessible.
        """
        for directory in directories:
            typer.echo(f"Backing up directory {directory} to {self.device_path}...")

            backup_json    = self.get_json_filename(directory, label=self.label)
            backup_history = self.load_backup_history(backup_json)


            with self.progress:
                if self.incremental:
                    changed_files = self.get_changed_files_list(directory, backup_history)
                    if not changed_files:
                        typer.echo(f"\nNo changes in {directory}, skipping backup.")
                        continue
                    current_state = self.scan_directory(directory)
                    incremental_files = {filepath: current_state[filepath] for filepath in changed_files}
                    backup_entry = {'type': 'incremental', 'files': incremental_files}
                else:
                    current_state = self.scan_directory(directory)
                    backup_entry = {
                        'files': {
                            filepath: (
                                {'mtime': attrs['mtime'], 'size': attrs['size']}
                                if attrs['type'] == 'file' else
                                {'type': 'symlink', 'target': attrs.get('target'), 'valid': attrs.get('valid', False)}
                            )
                            for filepath, attrs in current_state.items()
                        }
                    }
                    backup_history = []  # Reset history for a full backup

            # Update backup history and save JSON
            backup_history.append(backup_entry)
            with open(backup_json, 'w') as file:
                json.dump(backup_history, file)

            # Write files to be backed up to a list file for tar
            files_to_backup = backup_entry['files']

            # Write files to be backed up to a temporary file in self.tar_dir
            with tempfile.NamedTemporaryFile(mode='w+', dir=self.tar_dir, delete=False) as temp_file:
                backup_files_list_path = temp_file.name
                for file in files_to_backup:
                    temp_file.write(f"{file}\n")

            tar_options = ["tar", "-cvf", "-", "-T", backup_files_list_path]
            tar_options.extend(["-b", str(self.block_size)])
            backup_command = " ".join(tar_options) + f" | mbuffer -P {self.memory_buffer_percent} -m {self.memory_buffer} -s {self.block_size} -v 1 -o {self.device_path}"
            print(f"Backup Command: {backup_command}")

            # Execute the backup command
            process = subprocess.Popen(backup_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                for line in process.stderr:
                    print(line, end='\n')  # Printing stderr for monitoring
                process.wait()
                if process.returncode != 0:
                    typer.echo(f"Error occurred during backup of {directory}. Error code: {process.returncode}")
                    continue
            except Exception as e:
                typer.echo(f"Error occurred during backup of {directory}: {e}")
            finally:
                process.stderr.close()
                os.remove(backup_files_list_path)  # Remove the temporary file after use
                typer.echo(f"Backup of {directory} completed successfully.")

        return "All backups completed."


    def count_files(self, directory):
        """
        Counts the number of files in a given directory tree, excluding symlinks to directories.

        This recursive method traverses the directory tree, starting from the specified root directory,
        and counts all the files it encounters. The count does not include directory symlinks to avoid
        potential recursive links and to keep the count focused on actual files.

        Parameters:
        - directory (str): The root directory from which the file counting begins.

        Returns:
        - int: The total number of files present in the directory tree.

        Note:
        - This method is particularly useful for estimating the scope of a backup operation, 
          allowing for accurate progress tracking during scanning or archiving processes.
        - The method uses os.scandir, which is an efficient way to iterate over the entries in a 
          directory. It checks each entry to determine if it's a file or a directory.
        - For directories, the method calls itself recursively to count files in subdirectories.
        - Symlinks that point to directories are intentionally ignored to prevent counting files 
          in potentially unrelated directory trees.
        """
        count = 0
        for entry in os.scandir(directory):
            if entry.is_file():
                count += 1
            elif entry.is_dir():
                if not os.path.islink(entry.path):
                    count += self.count_files(entry.path)
        return count


    def scan_directory(self, directory):
        """
        Scans the given directory, cataloging files and their attributes, including symlinks.

        This method performs a recursive walk through the directory, recording details of each file
        and symlink it encounters. This information is essential for backup processes, particularly
        incremental backups, where changes need to be tracked.

        A progress bar is displayed to provide visual feedback on the scanning process, showing the 
        number of files processed out of the total files in the directory.

        Parameters:
        - directory (str): The path to the directory that needs to be scanned.

        Returns:
        - dict: A dictionary containing the file paths as keys and their attributes as values.
                File attributes include modification time, size, and symlink target (if applicable).

        Note:
        - For symlinks, the method records the target path and whether the symlink is valid (i.e., the 
          target exists).
        - Files that cannot be accessed due to being removed or inaccessible during the scan are 
          noted, but not included in the returned data.
        - This method uses os.walk and handles each file or symlink it encounters. Symlinks are not 
          followed to prevent potential loops or recursive links.
        """        
        task_id = self.progress.add_task(f"Scanning {directory}", total=self.count_files(directory))

        file_data = {}
        #expected_files = self.count_files(directory)

        for root, dirs, files in os.walk(directory, followlinks=False):
            for filename in files:
                self.progress.advance(task_id, advance=1)
                filepath = os.path.join(root, filename)
                if os.path.islink(filepath):
                    # Handle symlink: store it as a symlink with its target
                    try:
                        target = os.readlink(filepath)
                        file_data[filepath] = {
                            'type': 'symlink',
                            'target': target,
                            'valid': os.path.exists(filepath)  # Check if symlink is valid
                        }
                    except OSError:
                        print(f"Warning: Error reading symlink: {filepath}")
                        file_data[filepath] = {
                            'type': 'symlink',
                            'target': None,
                            'valid': False
                        }
                else:
                    # Handle regular file
                    try:
                        stats = os.stat(filepath)
                        file_data[filepath] = {
                            'type': 'file',
                            'mtime': stats.st_mtime,
                            'size': stats.st_size
                        }
                    except FileNotFoundError:
                        print(f"Warning: File not found: {filepath}")
                    continue
        return file_data


    def get_changed_files_list(self, directory, backup_history):
        """
        Determines the list of changed files in a directory based on the last backup history.

        Args:
            directory (str): The directory path to scan for changes.
            backup_history (list): The list of past backup entries.

        Returns:
            list: A list of file paths that have changed since the last backup.
        """
        combined_state = self.get_combined_backup_state(backup_history)
        current_state = self.scan_directory(directory)
        changed_files = []

        for filepath, attrs in current_state.items():
            last_attrs = combined_state.get(filepath)

            if attrs['type'] == 'file':
                if not last_attrs or last_attrs.get('mtime') != attrs['mtime'] or last_attrs.get('size') != attrs['size']:
                    changed_files.append(filepath)
            elif attrs['type'] == 'symlink':
                if not last_attrs or last_attrs.get('target') != attrs['target'] or last_attrs.get('valid') != attrs['valid']:
                    changed_files.append(filepath)

        # Optionally, handle deleted files if required
        # for filepath in last_backup['files']:
        #     if filepath not in current_state:
        #         # Handle the deleted file
        #         pass

        return changed_files


    def get_combined_backup_state(self, backup_history):
        """
        Aggregates the file states from all entries in the backup history into a single combined state.

        This method is used to create a cumulative view of the backup history by merging the file states
        (including metadata like modification time and size) from all previous backup entries. 
        This combined state is essential for determining the changes that need to be included in an 
        incremental backup.

        Parameters:
        - backup_history (list): A list of dictionaries, where each dictionary represents a backup entry 
                                containing the state of files backed up during that session.

        Returns:
        - dict: A dictionary representing the combined state of all files from the provided backup history. 
                The keys are file paths, and the values are dictionaries of file attributes.

        Note:
        - The combined state is crucial for incremental backups, as it allows the system to identify 
          which files have been modified, added, or deleted since the last backup. It helps in creating 
          efficient backup processes by avoiding redundancy and focusing only on changed files.
        """        
        combined_state = {}
        for entry in backup_history:
            combined_state.update(entry['files'])
        return combined_state


    def load_backup_history(self, backup_json):
        """
        Loads the backup history from a JSON file.

        Args:
            backup_json (str): Path to the JSON file containing the backup history.

        Returns:
            list: A list of backup entries, each entry is a dictionary with details about the backup.
                Returns an empty list if the file does not exist.
        """
        if os.path.exists(backup_json):
            with open(backup_json, 'r') as file:
                return json.load(file)
        return []


    def get_json_filename(self, directory, label=None):
        """
        Generates the filename for the JSON file that stores the backup history for a given directory.

        This method creates a filename for a JSON file that keeps a record of the backup history, 
        including details of both full and incremental backups for a specific directory. 
        The filename can be prefixed with a label for additional context or identification.

        Parameters:
        - directory (str): The directory path for which the backup history is maintained.
        - label (str, optional): An optional label that can be prefixed to the filename for 
                                easier identification of the backup set. Defaults to None.

        Returns:
        - str: The fully qualified path of the JSON file used to store the backup history.

        Note:
        - The JSON file is essential for managing incremental backups, as it contains information 
          about the files backed up in each session. It is used to determine the changes since 
          the last backup, enabling efficient incremental backup processes.
        """
        dir_name = os.path.basename(directory)
        label_prefix = f"{label}_" if label else ""
        return os.path.join(self.snapshot_dir, f"{label_prefix}{dir_name}_backup.json")


    def cleanup_temp_files(self):
        """
        Cleans up temporary tar files that were generated during the backup process.

        This method iterates through the sets of tar files that are in different stages of the backup process (generating,
        generated, and to be written) and removes any existing files from the file system. This is crucial for ensuring that
        no residual files are left on the disk after the backup operations, especially in scenarios where the backup
        process is interrupted or encounters errors.

        Note:
        This method should be called as a part of the cleanup process after backup operations are completed or interrupted.
        """        
        for tar_path in self.tars_generating.union(set(self.tars_generated), set(self.tars_to_write)):
            if os.path.exists(tar_path):
                os.remove(tar_path)


    def exit_handler(self, signum, frame):
        """
        Handles graceful exit of the backup process upon receiving a signal.

        This method is intended to be used as a signal handler for signals such as SIGINT (Ctrl+C).
        Upon receiving such a signal, it stops the backup process by setting the 'running' flag to
        False and invokes the cleanup method to remove any temporary files. It then prints a message
        indicating that the process is exiting gracefully.

        Parameters:
        signum (int): The signal number.
        frame (frame object): The current stack frame.

        Note:
        This handler ensures that the program exits in a controlled manner, performing necessary
        cleanup to avoid leaving the system in an inconsistent state.
        """        
        self.running = False
        self.cleanup_temp_files()
        typer.echo("Exiting gracefully...")
