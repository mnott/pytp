# PyTP - Python Tape Backup Utility

PyTP is a comprehensive Python-based CLI utility for tape backup operations. It's designed to interface with various tape drives (tested with HP LTO-6 and LTO-9 drives, and the MSL2024 tape library) and provides a range of functions from basic tape manipulations to complex backup strategies.

## Features

- **Backup and Restore**: Supports backup and restoration of directories and files directly to and from tape drives.
- **Tape Operations**: Includes a variety of tape operations such as rewinding, setting tape positions, listing files on tape, etc.
- **Flexible Backup Strategies**: Offers different backup strategies (direct, tar, dd) for optimal performance based on the user's needs.
- **CLI Interface**: Easy-to-use command-line interface for all tape operations.
- **Configurable**: Customizable settings through JSON configuration files.

## Sample CLI Calls

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

- Go back two file markers:

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

## Further Development (TODOs)

- Verification: Implement functionality to verify the integrity of backed-up data.
- Tape Library Operations: Extend support for tape library operations like loading and unloading tapes.
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

### Tapes

Look at the configs directory. It contains a file `tapes.json``:

```json
{
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
    ]
}
```

### Defaults

In the configs directory you will also find a file `default_config.json`:

```json
{
    "temp_dir": "/data/temp"
}
```

## License
PyTP is released under the "Do What The F*ck You Want To Public License" (WTFPL), which is a free software license.

## Notes
Users looking to adapt PyTP for different tape drives should inspect the tape operation methods to ensure compatibility. Currently tested with HP LTO-6 and LTO-9 drives, and an MSL2024 tape library.

