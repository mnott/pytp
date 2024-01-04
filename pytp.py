#!/usr/bin/env python
# encoding: utf-8

# ptp.py

#
# Imports
#
# Standard library imports for warnings, OS operations, date and time handling, and JSON processing.
import warnings
import os
import datetime
import json

#
# SQL Alchemy / Database
#
# Importing necessary components from SQLAlchemy for database operations.
from sqlalchemy import create_engine, text, update, MetaData, Table, Column, Numeric, Integer, VARCHAR, bindparam, insert, select, and_
from sqlalchemy.sql import update
from sqlalchemy.orm import sessionmaker

#
# More Beautiful Tracebacks and Pretty Printing
#
# Importing modules for enhancing the display of tracebacks and pretty-printing in terminal.
from rich import print
#from rich import traceback # Uncomment if traceback customization is needed
import traceback
from rich.traceback import Traceback
from rich.progress  import Progress
from rich.console   import Console
from rich.color     import Color
from rich.style     import Style
from rich import pretty
from rich.table import Table

pretty.install()      # Automatically makes built-in Python pretty printer output more readable
#traceback.install()  # Uncomment to use Rich's traceback for better error visibility


#
# Our Modules
#
# Importing our custom module for tape operations.
from pytp.tape_operations import TapeOperations
from pytp.tape_library_operations import TapeLibraryOperations


#
# Command Line Interface
#
# Typer is used for creating a command-line interface. Typing is used for type annotations.
from typing import List, Optional
import typer

app = typer.Typer(
    add_completion = False,                   # Disables shell completion setup prompt
    rich_markup_mode = "rich",                # Enables rich text formatting in help messages
    no_args_is_help=True,                     # Displays help message when no arguments are provided
    help="PyTP: Python Tape Backup Utility",  # General description of the CLI utility
    epilog=""" 
    To get help about the cli, call it with the --help option.
    """  # Additional information displayed at the end of the help message
)


@app.command(
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True}
)


#
# Initialize the Tape
#
@app.command()
def init(
    drive_name: str = typer.Option(os.environ.get('PYTP_DEV', 'lto9'), "--drive", "-d", help="Name of the tape drive"),
) -> None:
    """
    Sets the block size for the specified tape drive.
    
    This function initializes a TapeOperations object with the given drive name and then
    calls its 'init' method to set the tape drive's block size. It outputs the result
    of the operation to the console.
    
    Args:
        drive_name (str): The name of the tape drive to be initialized. This name is used
                          to fetch the drive's configuration details. The default value is taken
                          from the environment variable 'PYTP_DEV' or defaults to 'lto9'.
    """
    result = TapeOperations(drive_name).init()
    typer.echo(result)


#
# Show Tape Status
#
@app.command()
def status(
    drive_name: str = typer.Option(os.environ.get('PYTP_DEV', 'lto9'), "--drive", "-d", help="Name of the tape drive"),
) -> None:
    """
    Shows the current status of the tape drive.
    
    This function creates an instance of the TapeOperations class and invokes its
    'show_tape_status' method to retrieve and display the current status of the tape drive.
    This includes information like the tape's position, online/offline status, and other
    relevant details.

    Args:
        drive_name (str): The name of the tape drive to be initialized. This name is used
                          to fetch the drive's configuration details. The default value is taken
                          from the environment variable 'PYTP_DEV' or defaults to 'lto9'.
    """
    result = TapeOperations(drive_name).show_tape_status()
    typer.echo(result)

# Alias for the status command
app.command(name="stat")(status)


#
# Show Tape Position
#
@app.command()
def position(
    drive_name: str = typer.Option(os.environ.get('PYTP_DEV', 'lto9'), "--drive", "-d", help="Name of the tape drive"),
) -> None:
    """
    Displays the current position of the tape in the specified tape drive.
    
    This function utilizes the TapeOperations class to interact with the tape drive.
    It calls the 'show_tape_position' method of the class, which returns the current position
    of the tape (file number), providing insight into where the tape head is located.

    Args:
        drive_name (str): The name of the tape drive to be initialized. This name is used
                          to fetch the drive's configuration details. The default value is taken
                          from the environment variable 'PYTP_DEV' or defaults to 'lto9'.
    """
    result = TapeOperations(drive_name).show_tape_position()
    typer.echo(result)

# Alias for the rewind command
app.command(name="pos")(position)


#
# Set / Show Tape Block Position
#
@app.command()
def goto(
    block     : Optional[int] = typer.Argument(None, help="Block to go to"),
    drive_name: str = typer.Option(os.environ.get('PYTP_DEV', 'lto9'), "--drive", "-d", help="Name of the tape drive"),
) -> None:
    """
    Sets or shows the current block position of the tape in the specified tape drive.

    If a block number is provided, the tape is moved to that block position.
    If no block number is given, the current block position of the tape is displayed.
    This function uses the TapeOperations class for tape drive interactions.

    Args:
        block (int, optional): The block number to set the tape position to. If None, 
                               the current tape block position is returned instead.
        drive_name      (str): The name of the tape drive to be initialized. This name is used
                               to fetch the drive's configuration details. The default value is taken
                               from the environment variable 'PYTP_DEV' or defaults to 'lto9'.
    """
    if block is not None:
        print(f"Moving to block {block}...")
        result = TapeOperations(drive_name).set_tape_block(block)
    else:
        result = TapeOperations(drive_name).show_tape_block()
    typer.echo(result)

# Alias for the rewind command
app.command(name="g")(goto)


#
# Rewind the Tape
#
@app.command()
def rewind(
    drive_name: str = typer.Option(os.environ.get('PYTP_DEV', 'lto9'), "--drive", "-d", help="Name of the tape drive"),
) -> None:
    """
    Rewinds the tape to the beginning in the specified tape drive.

    This function is responsible for sending the rewind command to the tape drive,
    ensuring that the tape is positioned at the beginning. It uses the TapeOperations
    class to interact with the tape drive.

    Args:
        drive_name (str): The name of the tape drive to be initialized. This name is used
                          to fetch the drive's configuration details. The default value is taken
                          from the environment variable 'PYTP_DEV' or defaults to 'lto9'.
    """
    result = TapeOperations(drive_name).rewind_tape()
    typer.echo(result)

# Alias for the rewind command
app.command(name="rew")(rewind)


#
# Skip File Markers Forward
#
@app.command()
def ff(
    count     : Optional[int] = typer.Argument(1, help="Number of file markers to skip forward"),
    drive_name: str = typer.Option(os.environ.get('PYTP_DEV', 'lto9'), "--drive", "-d", help="Name of the tape drive"),
) -> None:
    """
    Skips a specified number of file markers forward on the tape in the given tape drive.

    This command advances the tape by the specified number of file markers. It leverages the
    TapeOperations class to perform the skip operation on the tape drive.

    Args:
        count (int, optional): The number of file markers to skip forward. Defaults to 1.
        drive_name      (str): The name of the tape drive to be initialized. This name is used
                               to fetch the drive's configuration details. The default value is taken
                               from the environment variable 'PYTP_DEV' or defaults to 'lto9'.
    """
    result = TapeOperations(drive_name).skip_file_markers(count)
    typer.echo(result)


#
# Skip File Markers Backward
#
@app.command()
def bb(
    count     : Optional[int] = typer.Argument(1, help="Number of file markers to skip backward"),
    drive_name: str = typer.Option(os.environ.get('PYTP_DEV', 'lto9'), "--drive", "-d", help="Name of the tape drive"),
) -> None:
    """
    Skips a specified number of file markers backward on the tape in the given tape drive.

    This command rewinds the tape by the specified number of file markers. It leverages the
    TapeOperations class to perform the skip operation on the tape drive. If it would pass
    the beginning of the tape based on the current tape position, it rewinds the tape.

    Args:
        count (int, optional): The number of file markers to skip backward. Defaults to 1.
        drive_name      (str): The name of the tape drive to be initialized. This name is used
                               to fetch the drive's configuration details. The default value is taken
                               from the environment variable 'PYTP_DEV' or defaults to 'lto9'.
    """
    result = TapeOperations(drive_name).skip_file_markers(-count)
    typer.echo(result)


#
# List Files
#
@app.command()
def ls(
    drive_name: str = typer.Option(os.environ.get('PYTP_DEV', 'lto9'), "--drive", "-d", help="Name of the tape drive"),
    sample: Optional[int] = typer.Option(None, help="Number of files to sample from the list"),
) -> None:
    """
    Lists files at the current position on the tape in the given tape drive. 

    This command leverages the TapeOperations class to perform the listing operation on the tape drive.
    It can list all files or a specified number of sample files at the current tape marker.

    Args:
        sample (int, optional): The number of files to sample from the list. If not specified, 
                                all files at the current tape marker are listed.
        drive_name       (str): The name of the tape drive to be initialized. This name is used
                                to fetch the drive's configuration details. The default value is taken
                                from the environment variable 'PYTP_DEV' or defaults to 'lto9'.                                
    """
    TapeOperations(drive_name).list_files(sample)  # Output is printed directly within the function


#
# Backup Directories
#
@app.command()
def backup(
    library_name         : str       = typer.Option(os.environ.get('PYTP_LIB', 'msl2024'), "--library", "-l", help="Name of the tape drive"),
    drive_name           : str       = typer.Option(os.environ.get('PYTP_DEV', 'lto9'), "--drive", "-d", help="Name of the tape drive"),
    job                  : str       = typer.Option(None,     "--job", "-j",                 help="Job Name for the backup"),
    label                : str       = typer.Option(None,     "--label", "-l",               help="Label for the tape (if using a library, it will be ignored)"),
    strategy             : str       = typer.Option("direct", "--strategy", "-s",            help="Backup strategy: direct or tar (via memory buffer), or dd (without memory buffer)"),
    incremental          : bool      = typer.Option(False,    "--incremental", "-i",         help="Perform an incremental backup"),
    max_concurrent_tars  : int       = typer.Option(2,        "--max-concurrent-tars", "-m", help="Maximum number of concurrent tar operations"),      
    memory_buffer        : int       = typer.Option(6,        "--memory_buffer", "-mem",     help="Memory buffer size in GB"),
    memory_buffer_percent: int       = typer.Option(6,        "--memory_buffer_percent", "-memp", help="Fill grade of memory buffer before streaming to tape"),
    directories          : List[str] = typer.Argument(..., help="List of directories (or files) to backup"),
):
    """
    Initiates the backup process for specified directories to the tape drive.

    This function serves as a command line interface to trigger the backup process. It allows users to specify
    the tape drive, backup strategy, maximum number of concurrent tar operations, and the directories to be backed up.

    Args:
        library_name          (str): The name of the tape library as configured in the system. This is used to fetch the
                                     label and other information, if needed.
        drive_name            (str): The name of the tape drive as configured in the system. This is used to fetch the
                                     device path and other details necessary for the backup operation.
        job                   (str): The job name for the backup. This is used to identify the backup metadata.
        label                 (str): The label for the tape. This is used to identify the tape it not using a tape library.
        strategy              (str): Determines the backup strategy to be used. Options are 'direct', 'tar', or 'dd'.
                                      - 'direct' streams files directly to the tape using a memory buffer,
                                      - 'tar'    first creates tar archives then writes them to tape using a memory buffer,
                                      - 'dd'     also creates tar archives first but writes them using the 'dd' command without a memory buffer.
        incremental          (bool): Specifies whether the backup is incremental or not. If True, the backup will only include files that have changed since the last backup.
        max_concurrent_tars   (int): Specifies the maximum number of tar file operations that can run concurrently.
                                     This helps to manage system resources and performance during the backup process.
        memory_buffer         (int): The size of the memory buffer to use for streaming files to tape. This is only
                                     applicable for the 'direct' and 'tar' strategies.
        memory_buffer_percent (int): The percentage the memory buffer needs to be filled before streaming to tape.
        directories     (List[str]): A list of directory paths that need to be backed up. This can include both directories
                                     and individual files.

    The function leverages the TapeOperations class to handle the backup process. It passes the user-specified parameters
    to the class methods to ensure the backup is performed as per the chosen strategy and configurations.

    The result of the backup operation (success message or error information) is printed to the console.
    """
    result = TapeOperations(drive_name).backup_directories(directories, library_name=library_name, label=label, job=job, strategy=strategy, incremental=incremental, max_concurrent_tars=max_concurrent_tars, memory_buffer=memory_buffer, memory_buffer_percent=memory_buffer_percent)
    typer.echo(result)

# Alias for the backup command
app.command(name="b")(backup)


#
# Restore Files
#
@app.command()
def restore(
    drive_name   : str = typer.Option(os.environ.get('PYTP_DEV', 'lto9'), "--drive", "-d", help="Name of the tape drive"),
    target_dir   : str = typer.Argument(".", help="Target directory for restored files"),
):
    """Restores files from tape to a specified directory."""
    result = TapeOperations(drive_name).restore_files(target_dir)
    typer.echo(result)

# Alias for the backup command
app.command(name="r")(restore)


#
# Verify
#
@app.command()
def verify(
    drive_name: str = typer.Option(os.environ.get('PYTP_DEV', 'lto9'), "--drive", "-d", help="Name of the tape drive"),
    directories: List[str] = typer.Argument(..., help="List of directories (or files) that were backed up"),
):
    """Verify backup."""
    result = TapeOperations(drive_name).verify_backup(directories)
    typer.echo(result)

# Alias for the backup command
app.command(name="v")(verify)


#
# Tape Library Operations: List Tapes
#
@app.command()
def list(
    library_name: str = typer.Option(os.environ.get('PYTP_LIB', 'msl2024'), "--library", "-l", help="Name of the tape drive"),
):
    tlo = TapeLibraryOperations(library_name)
    tape_library_contents = tlo.list_tapes()
    tlo.print_tape_library_output(tape_library_contents)


#
# Tape Library Operations: Load Tape
#
@app.command()
def load(
    library_name: str = typer.Option(os.environ.get('PYTP_LIB', 'msl2024'), "--library", "-l", help="Name of the tape drive"),
    drive_name  : str = typer.Option(os.environ.get('PYTP_DEV', 'lto9'), "--drive", "-d", help="Name of the tape drive"),
    slot_number : int = typer.Argument(..., help="Slot number to load")
):
    tlo = TapeLibraryOperations(library_name)
    result = tlo.load_tape(drive_name, slot_number)
    typer.echo(result)


#
# Tape Library Operations: Unload Tape
#
@app.command()
def unload(
    library_name: str = typer.Option(os.environ.get('PYTP_LIB', 'msl2024'), "--library", "-l", help="Name of the tape drive"),
    drive_name  : str = typer.Option(os.environ.get('PYTP_DEV', 'lto9'), "--drive", "-d", help="Name of the tape drive"),
    slot_number : int = typer.Argument(None, help="Slot number to unload into, defaut: original slot")
):
    tlo = TapeLibraryOperations(library_name)
    result = tlo.unload_tape(drive_name, slot_number)
    typer.echo(result)


#
# Tape Library Operations: Move Tape
#
@app.command()
def move(
    library_name: str = typer.Option(os.environ.get('PYTP_LIB', 'msl2024'), "--library", "-l", help="Name of the tape drive"),
    from_slot: str = typer.Argument(..., help="Slot to move from"),
    to_slot  : str = typer.Argument(..., help="Slot to move to"),
):
    tlo = TapeLibraryOperations(library_name)
    result = tlo.move_tape(from_slot, to_slot)
    typer.echo(result)




#
# Entry Point
#
if __name__ == '__main__':
    try:
        app()
    except SystemExit as e:
        if e.code != 0:
            raise