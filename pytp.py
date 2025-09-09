#!/usr/bin/env python
# encoding: utf-8

"""
PyTP - Python Tape Backup Utility

PyTP is a comprehensive Python-based CLI utility for tape backup operations. It's designed to interface with various tape drives (tested with HP LTO-6 and LTO-9 drives, and the MSL2024 tape library) and provides a range of functions from basic tape manipulations to complex backup strategies.

## Features

- **Backup and Restore**: Supports backup and restoration of directories and files directly to and from tape drives.
- **Tape Operations**: Includes a variety of tape operations such as rewinding, setting tape positions, listing files on tape, etc.
- **Flexible Backup Strategies**: Offers different backup strategies (direct, tar, dd) for optimal performance based on the user's needs.
- **Smart Library Detection**: Automatically detects and uses configured tape libraries without manual specification.
- **Enhanced Status Display**: Shows comprehensive tape drive status including label, slot, and library information.
- **Automatic Block Size Management**: Ensures tape drives are always in fixed block mode for reliable operations.
- **Rich Error Reporting**: Detailed error capture and analysis for backup operations with separate tar/mbuffer error tracking.
- **CLI Interface**: Easy-to-use command-line interface for all tape operations.
- **Configurable**: Customizable settings through JSON configuration files with human-readable config display.

## Sample CLI Calls

### Tape Operations

Here are some examples of how PyTP can be used:

- Help Function:

  ```bash
  pytp --help
  pytp backup --help
  ```

- Initialize the tape drive:

  ```bash
  pytp init --drive lto9
  ```

  The tape name used is specified in `tapes.json` (see below).

- Set the default tape to use if you do not want to specify it on the
  command line:

  ```
  export PYTP_DEV=lto9
  ```

- Backup directories to tape:

  ```bash
  pytp backup --drive lto9 --strategy tar /path/to/dir1 /path/to/dir2
  ```

- Backup directories to tape, incremental variant:

  ```bash
  pytp backup --drive lto9 --incremental --label test --strategy tar /path/to/dir1 /path/to/dir2
  ```

This uses status files in the `snapshot_dir` as per `config.json`. You can label those
backups (see the `--label` command line option; if not, and if we have a tape changer, it will use the tape changer to detect the label), and you can also prefix the snapshot files with a job name (see the `--job` command line option). If you do a non-incremental
backup for a given label, the previous snapshot file will be overwritten
(obviously this part is still under development...).

- Rewind the tape (if you want to go all the way to the beginning of the tape):

  ```bash
  pytp rewind --drive lto9
  ```

- Retension the tape for maintenance (ensures optimal tape condition):

  ```bash
  pytp retension --drive lto9
  ```

- Retension a tape from a library slot (loads, retensions, then unloads):

  ```bash
  pytp retension --drive lto9 --slot 5
  ```

- Go back just one file marker:

  ```bash
  pytp bb --drive lto9
  ```

- Go back two file markers:

  ```bash
  pytp bb 2 --drive lto9
  ```

  Note that if you would go back past file marker 0, a rewind will be done instead.

- Go forward one filemarker:

  ```bash
  pytp ff --drive lto9
  ```

- Go forward two file markers:

  ```bash
  pytp ff 2 --drive lto9
  ```

- List files on the tape:

  ```bash
  pytp ls --drive lto9
  ```

- Show comprehensive tape drive status (includes tape label and slot if using library):

  ```bash
  pytp status --drive lto9
  pytp status --drive lto9 --library msl2024  # Explicitly specify library
  pytp status --verbose                        # Show additional diagnostic info
  ```

- Display current configuration in human-readable format:

  ```bash
  pytp config
  ```

- Restore files from tape:

  ```bash
  pytp restore /path/to/restore/dir --drive lto9
  ```

### Tape Library Operations

PyTP features smart library detection - it automatically uses the first configured library, or you can specify one explicitly. Library commands will fail gracefully if no library is configured.

- List the content of the library (auto-detects configured library):

  ```bash
  pytp list                          # Uses first configured library
  pytp list --library msl2024        # Explicitly specify library
  ```

- Load a tape from slot 2 into a given tape:

  ```bash
  pytp load --drive lto9 2           # Auto-detects library
  pytp load --library msl2024 --drive lto9 2  # Explicit library
  ```

- Unload a tape from a given tape to a given slot:

  ```bash
  pytp unload --drive lto9 2         # Auto-detects library
  pytp unload --drive lto9           # Unload to original slot
  ```

If you do not specify the target slot (2 in this case), the tape library
will try to use the slot it thinks the tape was loaded from. If you did
some wild moves, this may go wrong.

- Move a tape from one slot to another:

  ```bash
  pytp move 2 3                      # Auto-detects library
  pytp move --library msl2024 2 3    # Explicit library
  ```

## Tape Retension

Tape retension is a maintenance operation that ensures optimal tape condition by exercising the entire length of the tape. This process helps maintain proper tape tension and prevents issues like media degradation, sticking, or uneven wear.

### When to Retension

- Tapes that have been stored for extended periods
- Tapes showing "media attention" errors in the library
- Before important backup operations on older tapes
- As part of regular maintenance for frequently used tapes

### Retension Examples

```bash
# Retension currently loaded tape
pytp retension

# Show detailed progress output
pytp retension --verbose

# Load tape from slot 5, retension, then unload
pytp retension --slot 5

# Retension with specific library and verbose output
pytp retension --library msl2024 --slot 3 --verbose
```

### Linux Implementation Note

On Linux systems, the native `mt retension` command is often a no-op (unlike FreeBSD). PyTP automatically detects this and performs manual retension by:

1. Rewinding tape to beginning
2. Winding tape to end of reel  
3. Rewinding tape back to beginning

This ensures proper tape tensioning regardless of the underlying mt command behavior.

## Enhanced Features

### Smart Library Detection

PyTP automatically detects and uses configured tape libraries:

1. **Auto-detection**: If no `-l/--library` parameter is provided, uses the first configured library
2. **Explicit selection**: Use `-l library_name` to specify a particular library
3. **Error handling**: Commands fail gracefully with clear messages if library doesn't exist
4. **Status integration**: Status command shows which library is being used

### Enhanced Status Display

The `pytp status` command provides comprehensive information:

- **Tape drive statistics**: Volume stats, error counts, compression ratios
- **Current position**: File number, block number, block size
- **Library information**: Which library is being used (if multiple configured)
- **Tape information**: Tape label/barcode and source slot number
- **Busy detection**: When drive is busy, shows what process is using it

### Automatic Block Size Management

PyTP ensures reliable tape operations by:

- **Auto-initialization**: Automatically sets fixed block mode before tape operations
- **Block size validation**: Checks and corrects block size settings automatically
- **Variable mode prevention**: Prevents unreliable variable block mode (block size 0)
- **Seamless operation**: Works transparently - no user intervention needed

### Enhanced Error Reporting

Backup operations now feature detailed error tracking:

- **Separate error streams**: Distinguishes between TAR errors and MBUFFER errors
- **Error classification**: Tags errors as `[TAR]`, `[MBUFFER]`, `[PERMISSION]`, etc.
- **Failure analysis**: Explains what different return codes mean
- **Pattern detection**: Identifies common failure patterns (broken pipe, I/O errors, etc.)
- **Tape diagnostics**: Captures tape drive state at failure points

## Backup Strategies

### Overview

There are three different backup strategies that `pytp` can use:

1. Direct (default) writes each file to tape directly, using tar and a memory buffer
2. Tar: pre-generates a tar file and then writes it to tape using a memory buffer
3. DD: pre-generates a tar file and then writes it to tape using dd, without using a memory buffer

### Quick Guidance

1. Do you have bigger files or a fast source medium that can match the write speed of the tape drive: Use the STRATEGY_DIRECT.
2. Do you have many, potentially small files and a potentially slow medium from which you write to the tape drive: Use the STRATEGY_TAR.
3. Do you have many, potentially small files and a guaranteed fast medium (e.g., an SSD) from which you write to the tape drive: Use STRATEGY_DD.

Also, whilst `pytp` isn't currently handling out of tape situations (where e.g. a tape loader might load the next tape to continue a backup), those situations will likely only ever be handled with STRATEGY_DIRECT, as in both other strategies, the process writing to tape has no insight into what it is actually writing to tape.

### Analysis

Let's look at the different strategies

1. STRATEGY_DIRECT (`tar -cvf | mbuffer`)
- How it works: This strategy directly streams files to the tape using the tar command; it does use a memory buffer to compensate for running out of data.
- Handling Tape Capacity: This strategy is more flexible in handling tape capacity issues because it deals with individual files. If the tape runs out mid-backup, it's relatively straightforward to pause, switch tapes, and resume the backup from the file where it stopped.
- Pros and Cons: While it's advantageous for handling tape changes, it might be slower for small files due to the overhead of starting and stopping the tar process for each file. In particular, if you have many small files, your source system may not be able to handle the tape drive's write speed, causing the drive to stop and restart frequently. This may lead to usage (shoeshining)

2. STRATEGY_TAR (`tar`, then `cat | mbuffer`)
- How it works: This strategy involves creating a tar file first, then writing it to the tape using mbuffer.
- Handling Tape Capacity: Here, detecting when the tape is full is more challenging because the backup process is dealing with a single large file (the tar archive). The process doesn't inherently know about the individual files within the tar archive.
- Pros and Cons: Efficient for smaller files and slower source mediums, but less flexible in responding to a tape running out.

3. STRATEGY_DD (`tar`, then `dd`)
- How it works: Similar to STRATEGY_TAR but uses dd for writing to tape.
- Handling Tape Capacity: Like STRATEGY_TAR, it faces similar challenges in tape capacity handling. dd writes a large tar file to tape and doesn't have insight into its contents.
- Pros and Cons: Suitable for smaller files and fast source mediums but offers limited flexibility for tape changes.

### What Method to Choose

At this moment, `pytp` does not even handle out of tape situations. It is likely that the only place where we can implement handling such situations is the `DIRECT` strategy. Having said that, and assuming you are able to define which tape to use (which is anyway the default for a single tape drive without an autoloader), here are the considerations to make for the strategy you would use:

1. STRATEGY_DIRECT: The big downside of this method is likely the shoeshining effect that will happen if you do not have very fast media delivering the data that you are backing up. Particularly if you have many small files, this is likely to happen. Therefore:

- Use this method for large files. For example, assume you are having virtual machine disk images, or large video files.
- Monitor the tape drive's behavior. If you see it stopping and starting frequently, then use another method.
- Monitor the behavior of the memory buffer. If it is mostly empty, increase it. If it takes too much time to fill it, reduce the fill grade requirements.

2. STRATEGY_TAR: This pre-generates the tar file(s) to be written to disk. You can actually configure it as to how many tar files to generate in parallel. That means, you are going to have a number of potentially competing processes:

- The tar file generation: If you run too many of them in parallel, your file system will be saturated, and the whole process of generating the tar files will be slowed down
- Writing a tar file to disk: Because of the previous point, with your file system being saturated as it is still generating "the next tar", your read speed may be slow, again causing shoe-shining
- The memory buffer you are using may cause your system to swap, again competing for I/O
- Because of this, you might consider:
  - using this strategy for situations where you have small source files
  - using not too many parallel tar file generations
  - directing the generated tar files to a different file system, and possibly even an SSD
  - limiting the amount of memory to use for the memory buffer
  - monitoring the behavior of the memory buffer. If it is mostly empty, increase it. If it takes too much time to fill it, reduce the fill grade requirements.

3. STRATEGY_DD: This pre-generates the tar file(s) and as such has the same considerations as the STRATEGY_TAR. But as it does not use a memory buffer, this method should be used when you are generating the tar file(s) onto a medium that is guaranteed to be fast - like an SSD.



## Further Development (TODOs)

- Verification: Implement functionality to verify the integrity of backed-up data.
- Database Integration: Develop features to capture file metadata, tape, and position details in a database for easy retrieval.
- Installation Guide: Provide a detailed installation procedure, including prerequisites like mt, mtx, mbuffer, tar, dd.
- Testing: Establish a comprehensive test suite to ensure reliability across different tape drives and systems.

## Installation

Basically, just clone the directory, install mt, mtx, mbuffer, tar, dd, and if you have a missing
Python module like `typer`, try `pip3 install typer`. See also `requirements.txt`. You can also
use the automated ways:

1. Create a virtual environment (recommended):

```bash
python -m venv venv
source venv/bin/activate  # Unix-based
venv\\Scripts\\activate   # Windows
```

2. Install the project using pip:

```bash
pip install .
```

3. If there are additional dependencies listed in requirements.txt, install them:

```bash
pip install -r requirements.txt
```

4. Now you can run the project using the pytp command (or as specified in the project's documentation).




## Configuration

Look at the configs directory. It contains a file `config.json`:

```json
{
    "tar_dir": "/data/temp/tars",
    "snapshot_dir": "/data/temp/snapshots",
    "tape_drives": [
        {
            "name": "lto9",
            "device_path": "/dev/nst0",
            "block_size": 524288
        },
        {
            "name": "lto6",
            "device_path": "/dev/nst1",
            "block_size": 524288
        }
    ],
    "tape_libraries": [
        {
            "name": "msl2024",
            "device_path": "/dev/sch0",
            "slots": 23,
            "drives": [
                "lto6",
                "lto9"
            ]
        }
    ]
}
```

The order of the tape drives in the `tape_libraries` section is important, as the tape library will typically
address its drives by their number.


## License
PyTP is released under the "Do What The F*ck You Want To Public License" (WTFPL), which is a free software license.

## Notes
Users looking to adapt PyTP for different tape drives should inspect the tape operation methods to ensure compatibility. Currently tested with HP LTO-6 and LTO-9 drives, and an MSL2024 tape library.

"""

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
    library_name: str = typer.Option(None, "--library", "-l", help="Name of the tape library (optional)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show verbose output including actual commands executed"),
) -> None:
    """
    Shows the current status of the tape drive.

    This function creates an instance of the TapeOperations class and invokes its
    'show_tape_status' method to retrieve and display the current status of the tape drive.
    This includes information like the tape's position, online/offline status, and if a tape
    library is configured, also shows the tape label and source slot automatically.

    Args:
        drive_name (str): The name of the tape drive to be initialized. This name is used
                          to fetch the drive's configuration details. The default value is taken
                          from the environment variable 'PYTP_DEV' or defaults to 'lto9'.
        library_name (str): Optional library name. If not provided, uses first configured library
                           or 'msl2024' as fallback.
        verbose (bool): If True, shows the actual commands being executed.
    """
    result = TapeOperations(drive_name).show_tape_status(verbose=verbose, library_name=library_name)
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
# Retension the Tape
#
@app.command()
def retension(
    drive_name: str = typer.Option(os.environ.get('PYTP_DEV', 'lto9'), "--drive", "-d", help="Name of the tape drive"),
    library_name: str = typer.Option(os.environ.get('PYTP_LIB', 'msl2024'), "--library", "-l", help="Name of the tape library"),
    slot_number: Optional[int] = typer.Option(None, "--slot", "-s", help="Slot number to load tape from (uses library if specified)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed output including warnings and errors"),
) -> None:
    """
    Retensions the tape for optimal media condition.

    This function performs a tape retensioning operation which is a standard maintenance
    procedure to keep the tape media in optimal condition. The process involves rewinding
    the tape, winding it to the end of the reel, and then rewinding it again. This helps
    ensure even tape tension and prevents issues like tape sticking or uneven wear.

    When slot is specified:
    - Loads the tape from the specified slot using the library
    - Performs the retensioning operation
    - Unloads the tape back to the original slot
    - Clears any media attention errors for that slot

    Args:
        drive_name (str): The name of the tape drive. Defaults to PYTP_DEV env var or 'lto9'.
        library_name (str): Name of the tape library. Defaults to PYTP_LIB env var or 'msl2024'.
                           Only used when slot_number is specified.
        slot_number (int, optional): Slot number to load tape from. If not specified,
                                    retensions the currently loaded tape.
    """
    # Only use library if slot is specified
    if slot_number is not None:
        result = TapeOperations(drive_name).retension_tape(library_name=library_name, slot_number=slot_number, verbose=verbose)
    else:
        # Don't pass library_name if no slot is specified (just retension current tape)
        result = TapeOperations(drive_name).retension_tape(verbose=verbose)
    if result and verbose:  # Show raw result in verbose mode
        typer.echo(f"Raw result: {result}")

# Alias for the retension command
app.command(name="ret")(retension)


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
    memory_buffer        : int       = typer.Option(16,       "--memory_buffer", "-mem",     help="Memory buffer size in GB"),
    memory_buffer_percent: int       = typer.Option(20,       "--memory_buffer_percent", "-memp", help="Fill grade of memory buffer before streaming to tape"),
    use_double_buffer    : bool      = typer.Option(True,     "--double-buffer/--no-double-buffer", help="Use double-buffering with named pipes for better flow control"),
    low_water_mark       : int       = typer.Option(10,       "--low-water-mark", "-lwm",    help="Low water mark percentage for second buffer stage (only used with double-buffer)"),
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
    result = TapeOperations(drive_name).backup_directories(directories, library_name=library_name, label=label, job=job, strategy=strategy, incremental=incremental, max_concurrent_tars=max_concurrent_tars, memory_buffer=memory_buffer, memory_buffer_percent=memory_buffer_percent, use_double_buffer=use_double_buffer, low_water_mark=low_water_mark)
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
    library_name: str = typer.Option(None, "--library", "-l", help="Name of the tape library (optional)"),
):
    """Lists the tapes in the tape library"""
    try:
        from pytp.config_manager import ConfigManager
        config_manager = ConfigManager()
        actual_library_name = config_manager.get_library_name(library_name)
        
        tlo = TapeLibraryOperations(actual_library_name)
        tape_library_contents = tlo.list_tapes()
        tlo.print_tape_library_output(tape_library_contents)
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"Error accessing library '{actual_library_name if 'actual_library_name' in locals() else library_name}': {e}", err=True)
        raise typer.Exit(1)


#
# Tape Library Operations: Load Tape
#
@app.command()
def load(
    library_name: str = typer.Option(None, "--library", "-l", help="Name of the tape library (optional)"),
    drive_name  : str = typer.Option(os.environ.get('PYTP_DEV', 'lto9'), "--drive", "-d", help="Name of the tape drive"),
    slot_number : int = typer.Argument(..., help="Slot number to load")
):
    """Loads a tape into the tape drive"""
    try:
        from pytp.config_manager import ConfigManager
        config_manager = ConfigManager()
        actual_library_name = config_manager.get_library_name(library_name)
        
        tlo = TapeLibraryOperations(actual_library_name)
        result = tlo.load_tape(drive_name, slot_number)
        typer.echo(result)
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"Error accessing library: {e}", err=True)
        raise typer.Exit(1)


#
# Tape Library Operations: Unload Tape
#
@app.command()
def unload(
    library_name: str = typer.Option(None, "--library", "-l", help="Name of the tape library (optional)"),
    drive_name  : str = typer.Option(os.environ.get('PYTP_DEV', 'lto9'), "--drive", "-d", help="Name of the tape drive"),
    slot_number : int = typer.Argument(None, help="Slot number to unload into, default: original slot")
):
    """Unloads a tape from the tape drive"""
    try:
        from pytp.config_manager import ConfigManager
        config_manager = ConfigManager()
        actual_library_name = config_manager.get_library_name(library_name)
        
        tlo = TapeLibraryOperations(actual_library_name)
        result = tlo.unload_tape(drive_name, slot_number)
        typer.echo(result)
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"Error accessing library: {e}", err=True)
        raise typer.Exit(1)


#
# Tape Library Operations: Move Tape
#
@app.command()
def move(
    library_name: str = typer.Option(None, "--library", "-l", help="Name of the tape library (optional)"),
    from_slot: str = typer.Argument(..., help="Slot to move from"),
    to_slot  : str = typer.Argument(..., help="Slot to move to"),
):
    """Moves a tape from one slot to another"""
    try:
        from pytp.config_manager import ConfigManager
        config_manager = ConfigManager()
        actual_library_name = config_manager.get_library_name(library_name)
        
        tlo = TapeLibraryOperations(actual_library_name)
        result = tlo.move_tape(from_slot, to_slot)
        typer.echo(result)
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"Error accessing library: {e}", err=True)
        raise typer.Exit(1)



#
# Command: Config
#
@app.command()
def config():
    """
    Display the current pytp configuration in a human-readable format.
    
    Shows configured tape drives, libraries, and directory settings.
    """
    from pytp.config_manager import ConfigManager
    config_manager = ConfigManager()
    config_manager.display_config()


#
# Command: Doc
#
@app.command()
def doc(
    ctx:        typer.Context,
    title:      str  = typer.Option(None,   help="The title of the document"),
    toc:        bool = typer.Option(False,  help="Whether to create a table of contents"),
) -> None:
    """
    Re-create the documentation and write it to the output file.
    """
    import importlib
    import importlib.util
    import sys
    import os
    import doc2md

    def import_path(path):
        module_name = os.path.basename(path).replace("-", "_")
        spec = importlib.util.spec_from_loader(
            module_name,
            importlib.machinery.SourceFileLoader(module_name, path),
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        sys.modules[module_name] = module
        return module

    mod_name = os.path.basename(__file__)
    if mod_name.endswith(".py"):
        mod_name = mod_name.rsplit(".py", 1)[0]
    atitle = title or mod_name.replace("_", "-")
    module = import_path(__file__)
    docstr = module.__doc__
    result = doc2md.doc2md(docstr, atitle, toc=toc, min_level=0)
    print(result)



#
# Entry Point
#
if __name__ == '__main__':
    try:
        app()
    except SystemExit as e:
        if e.code != 0:
            raise