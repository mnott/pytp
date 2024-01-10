# tape_metadata.py
import json
import os
from datetime import datetime

class TapeMetadata:
    """
    Manages and maintains the backup metadata for directories backed up to tape.

    This class handles the creation, updating, and saving of backup history for each
    directory backed up. It includes the functionality to track the state of backups,
    including incremental changes and the position on the tape where each backup starts.

    Attributes:
    - tape_operations: An instance of a class managing low-level tape operations.
    - progress: A Progress instance from Rich library for displaying progress bars.
    - snapshot_dir: The directory where backup metadata (JSON files) will be stored.
    - label: An optional tape label to prefix to backup metadata files.
    - job: An optional job name to prefix to backup metadata files.
    - backup_histories: A dictionary mapping directories to their backup histories.
    """    

    def __init__(self, tape_operations, progress, snapshot_dir, label=None, job=None):
        """
        Initializes the TapeMetadata class.

        Args:
            tape_operations: The tape operations handler.
            progress       : A Progress instance for managing progress displays.
            snapshot_dir   : Directory where backup histories are stored.
            label          : Optional tape label for backup files.
            job            : Optional job name for backup files.
        """        
        self.tape_operations  = tape_operations
        self.progress         = progress
        self.snapshot_dir     = snapshot_dir
        self.label            = label
        self.job              = job
        self.backup_histories = {}  # key: directory, value: backup history


    def load_backup_history(self, directory):
        """
        Loads the backup history for a specific directory from its JSON file.

        Args:
            directory (str): The directory for which to load backup history.

        Note:
            - If the JSON file does not exist, initializes an empty history.
        """
        backup_json = self.get_json_filename(directory)
        if os.path.exists(backup_json):
            with open(backup_json, 'r') as file:
                print(f"Loading backup history for {backup_json}")
                self.backup_histories[directory] = json.load(file)
        else:
            self.backup_histories[directory] = []


    def prepare_backup_entry(self, directory, incremental):
        """
        Prepares a backup entry for the given directory. This does not include the tape position.

        Args:
            directory (str): Directory to prepare the backup entry for.
            incremental (bool): Whether to perform an incremental backup.

        Returns:
            tuple: (bool, dict) - A boolean indicating if backup is needed, and the backup entry.
        """        
        self.load_backup_history(directory)
        history = self.backup_histories.get(directory, [])
        task_id = self.progress.add_task(f"Scanning {directory}", total=self.count_files(directory))

        current_state = self.scan_directory(directory, task_id)
        current_timestamp = datetime.now().isoformat()  # Get current timestamp as an ISO format string

        with self.progress:

            if incremental:
                changed_files = self.get_changed_files_list(directory, history)
                if not changed_files:
                    return False, {}
                incremental_files = {filepath: current_state[filepath] for filepath in changed_files}
                backup_entry = {
                    'type': 'incremental',
                    'label': self.label,
                    'timestamp': current_timestamp,
                    'files': incremental_files
                }
            else:
                backup_entry = {
                    'type': 'full',
                    'label': self.label,
                    'timestamp': current_timestamp,
                    'files': current_state
                }
                self.backup_histories[directory] = []  # Reset history for a full backup

        self.progress.remove_task(task_id)


        self.update_backup_entry(directory, backup_entry)
        return True, backup_entry


    def update_tape_position_and_save(self, directory, tape_position):
        """
        Updates the last backup entry with the current tape position and saves the history.

        Args:
            directory (str): The directory whose backup entry is to be updated.
            tape_position (int): The position on the tape where the backup starts.
        """
        if directory in self.backup_histories and self.backup_histories[directory]:
            self.backup_histories[directory][-1]['tape_position'] = tape_position
            self.save_backup_histories()


    def update_backup_entry(self, directory, backup_entry):
        """
        Updates the last backup entry with the current tape position and saves the history.

        Args:
            directory (str): The directory whose backup entry is to be updated.
            tape_position (int): The position on the tape where the backup starts.
        """
        self.backup_histories[directory].append(backup_entry)


    def save_backup_histories(self):
        """
        Saves all updated backup histories to their respective JSON files in the snapshot directory.
        """
        for directory, history in self.backup_histories.items():
            backup_json = self.get_json_filename(directory)
            with open(backup_json, 'w') as file:
                json.dump(history, file)


    def get_json_filename(self, directory, job=None):
        """
        Generates the filename for the JSON file that stores the backup history for a given directory.

        This method creates a filename for a JSON file that keeps a record of the backup history, 
        including details of both full and incremental backups for a specific directory. 
        The filename can be prefixed with a job name for additional context or identification.

        Parameters:
        - directory (str): The directory path for which the backup history is maintained.
        - job (str, optional): An optional job name that can be prefixed to the filename for 
                                easier identification of the backup set. Defaults to None.

        Returns:
        - str: The fully qualified path of the JSON file used to store the backup history.

        Note:
        - The JSON file is essential for managing incremental backups, as it contains information 
          about the files backed up in each session. It is used to determine the changes since 
          the last backup, enabling efficient incremental backup processes.
        """
        dir_name = os.path.basename(directory)
        job_prefix = f"{self.job}_" if self.job else ""
        return os.path.join(self.snapshot_dir, f"{job_prefix}{dir_name}_backup.json")



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


    def scan_directory(self, directory, task_id = None):
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
        file_data = {}
        #expected_files = self.count_files(directory)

        for root, dirs, files in os.walk(directory, followlinks=False):
            for filename in files:
                if task_id is not None:
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

