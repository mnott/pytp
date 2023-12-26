#!/usr/bin/env python
# encoding: utf-8

# ptp.py

#
# Imports
#
import warnings
import json
import datetime

from os import path
from sqlalchemy import create_engine, text, update, MetaData, Table, Column, Numeric, Integer, VARCHAR, bindparam, insert, select, and_
from sqlalchemy.sql import update
from sqlalchemy.orm import sessionmaker

#
# More Beautiful Tracebacks and Pretty Printing
#
from rich import print
#from rich import traceback
import traceback
from rich.traceback import Traceback
from rich import pretty
from rich.progress import Progress
from rich.console import Console
from rich.color import Color
from rich.style import Style
import rich.table # used to print a table
pretty.install()
#traceback.install()

#
# Our Modules
#
from pytp import tape_operations

#
# Command Line Interface
#
from typing import List, Optional
import typer

app = typer.Typer(
    add_completion = False,
    rich_markup_mode = "rich",
    no_args_is_help=True,
    help="CCEM EOB Tracker CLI",
    epilog="""
    To get help about the cli, call it with the --help option.
    """
)


@app.command(
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True}
)


#
# Initialize the Tape
#
@app.command()
def init(
    drive_name:  str  = typer.Option("lto9", "--drive", "-d", help="Name of the tape drive"),
) -> None:
    """Sets the block size for the specified tape drive."""
    result = tape_operations.init(drive_name)
    typer.echo(result)


#
# Show Tape Status
#
@app.command()
def status(
    drive_name: str = typer.Option("lto9", "--drive", "-d", help="Name of the tape drive"),
) -> None:
    """Shows the current position of the tape."""
    result = tape_operations.show_tape_status(drive_name)
    typer.echo(result)

# Alias for the status command
app.command(name="stat")(status)


#
# Show Tape Position
#
@app.command()
def position(
    drive_name: str = typer.Option("lto9", "--drive", "-d", help="Name of the tape drive"),
) -> None:
    """Shows the current position of the tape."""
    result = tape_operations.show_tape_position(drive_name)
    typer.echo(result)

# Alias for the rewind command
app.command(name="pos")(position)


#
# Rewind the Tape
#
@app.command()
def rewind(
    drive_name:  str  = typer.Option("lto9", "--drive", "-d", help="Name of the tape drive"),
) -> None:
    """Rewinds the tape."""
    result = tape_operations.rewind_tape(drive_name)
    typer.echo(result)

# Alias for the rewind command
app.command(name="rew")(rewind)


#
# Skip File Markers
#
@app.command()
def ff(
    count     : Optional[int] = typer.Argument(1, help="Number of file markers to skip forward"),
    drive_name: str = typer.Option("lto9", "--drive", "-d", help="Name of the tape drive"),
) -> None:
    """Skips file markers forward or backward on the tape."""
    result = tape_operations.skip_file_markers(drive_name, count)
    typer.echo(result)

@app.command()
def bb(
    count     : Optional[int] = typer.Argument(1, help="Number of file markers to skip backward"),
    drive_name: str = typer.Option("lto9", "--drive", "-d", help="Name of the tape drive"),
) -> None:
    """Skips file markers forward or backward on the tape."""
    result = tape_operations.skip_file_markers(drive_name, -count)
    typer.echo(result)


#
# List Files
#
@app.command()
def ls(
    drive_name: str = typer.Option("lto9", "--drive", "-d", help="Name of the tape drive"),
    sample: Optional[int] = typer.Option(None, help="Number of files to sample from the list"),
) -> None:
    """Lists files at the current tape marker."""
    tape_operations.list_files(drive_name, sample)  # Output is printed directly within the function


#
# Backup Directories
#
@app.command()
def backup(
    drive_name: str = typer.Option("lto9", "--drive", "-d", help="Name of the tape drive"),
    directories: List[str] = typer.Argument(..., help="List of directories (or files) to backup"),
):
    """Backup directories (or files) to tape."""
    result = tape_operations.backup_directories(drive_name, directories)
    typer.echo(result)

# Alias for the backup command
app.command(name="b")(backup)


#
# Restore Files
#
@app.command()
def restore(
    drive_name: str = typer.Option("lto9", "--drive", "-d", help="Name of the tape drive"),
    target_dir: str = typer.Argument(".", help="Target directory for restored files"),
):
    """Restores files from tape to a specified directory."""
    result = tape_operations.restore_files(drive_name, target_dir)
    typer.echo(result)

# Alias for the backup command
app.command(name="r")(restore)

#
# Verify
#
@app.command()
def verify(
    drive_name: str = typer.Option("lto9", "--drive", "-d", help="Name of the tape drive"),
    directories: List[str] = typer.Argument(..., help="List of directories (or files) that were backed up"),
):
    """Verify backup."""
    result = tape_operations.verify_backup(drive_name, directories)
    typer.echo(result)

# Alias for the backup command
app.command(name="v")(verify)


#
# Entry Point
#
if __name__ == '__main__':
    try:
        app()
    except SystemExit as e:
        if e.code != 0:
            raise