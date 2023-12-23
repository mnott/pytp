#!/usr/bin/env python
# encoding: utf-8

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
from pytp import tape_operations, config_manager

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
# Rewind the Tape
#
@app.command()
def rewind(
    drive_name:  str  = typer.Option("lto9", "--drive", "-d", help="Name of the tape drive"),
) -> None:
    """Rewinds the tape."""
    device_path = config_manager.get_tape_drive_config(config_manager.config, drive_name)
    result = tape_operations.rewind_tape(device_path)
    typer.echo(result)

#
# Initialize the Tape
#
@app.command()
def init(
    drive_name:  str  = typer.Option("lto9", "--drive", "-d", help="Name of the tape drive"),
) -> None:
    """Sets the block size for the specified tape drive."""
    tape_details = config_manager.get_tape_drive_details(config_manager.config, drive_name)
    device_path = tape_details.get('device_path')
    block_size = tape_details.get('block_size', 524288)  # Default block size if not specified

    if not device_path:
        typer.echo("Tape drive not found.")
        raise typer.Exit(1)

    result = tape_operations.set_block_size(device_path, block_size)
    typer.echo(result)


@app.command()
def skip(
    count: int = typer.Argument(..., help="Number of file markers to skip (positive for forward, negative for backward)"),
    drive_name: str = typer.Option("lto9", "--drive", "-d", help="Name of the tape drive"),
) -> None:
    """Skips file markers forward or backward on the tape."""
    device_path = config_manager.get_tape_drive_config(config_manager.config, drive_name)
    result = tape_operations.skip_file_markers(device_path, count)
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