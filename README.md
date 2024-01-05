# PyTP - Python Tape Backup Utility

PyTP is a comprehensive Python-based CLI utility for tape backup operations. It's designed to interface with various tape drives (tested with HP LTO-6 and LTO-9 drives, and the MSL2024 tape library) and provides a range of functions from basic tape manipulations to complex backup strategies.

## Features

- **Backup and Restore**: Supports backup and restoration of directories and files directly to and from tape drives.
- **Tape Operations**: Includes a variety of tape operations such as rewinding, setting tape positions, listing files on tape, etc.
- **Flexible Backup Strategies**: Offers different backup strategies (direct, tar, dd) for optimal performance based on the user's needs.
- **CLI Interface**: Easy-to-use command-line interface for all tape operations.
- **Configurable**: Customizable settings through JSON configuration files.

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
snapshot files (see the `--label` command line option). If you do a non-incremental
backup for a given label, the previous snapshot file will be overwritten
(obviously this part is still under development...).

- Rewind the tape (if you want to go all the way to the beginning of the tape):

  ```bash
  pytp rewind --drive lto9
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

- Restore files from tape:

  ```bash
  pytp restore /path/to/restore/dir --drive lto9
  ```

### Tape Library Operations

- List the content of the library

  ```bash
  pytp list
  ```

- Load a tape from slot 2 into a given tape

  ```bash
  pytp load --drive lto9 2
  ```

- Unload a tape from a given tape to a given slot

  ```bash
  pytp unload --drive lto9 2
  ```

If you do not specify the target slot (2 in this case), the tape library
will try to use the slot it thinks the tape was loaded from. If you did
some wild moves, this may go wrong.

- Move a tape from one slot to another

  ```bash
  pytp move 2 3
  ```

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
            "block_size": 2048
        },
        {
            "name": "lto6",
            "device_path": "/dev/nst1",
            "block_size": 2048
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

