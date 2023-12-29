#!/usr/bin/env python
# encoding: utf-8

# summarize.py

#
# Defaults
#
DEFAULTS = ["pytp.py", "pytp"]

import os
import typer
from typing import List

app = typer.Typer(
    add_completion = False,                   # Disables shell completion setup prompt
    rich_markup_mode = "rich",                # Enables rich text formatting in help messages
    no_args_is_help=True,                     # Displays help message when no arguments are provided
    help="PyTP: Code Summarizer",             # General description of the CLI utility
    epilog=""" 
    To get help about the cli, call it with the --help option.
    """  # Additional information displayed at the end of the help message    
)

#
# Summarize the code
#
@app.command()
def summarize(
    paths: List[str] = typer.Argument(None, help="Paths to Python files or directories to summarize")
) -> None:
    """
    This command summarizes the Python files at the given paths, stripping out all docstrings.
    """
    # Check if no paths are provided
    if paths is None or len(paths) == 0:
        paths = DEFAULTS
        
    code_summary = strip_docstrings_and_copy_code(paths)
    print(code_summary)

def strip_docstrings_and_copy_code(paths: List[str]):
    code_summary = ""

    for path in paths:
        if os.path.isfile(path) and path.endswith(".py"):
            # Handle single Python file
            code_summary += process_file(path)
        elif os.path.isdir(path):
            # Handle directory
            for root, dirs, files in os.walk(path):
                for file in files:
                    if file.endswith(".py"):
                        filepath = os.path.join(root, file)
                        code_summary += process_file(filepath)
        else:
            print(f"Skipping non-Python file: {path}")

    return code_summary


def process_file(filepath):
    summary = f"\n\n# {filepath}\n"
    with open(filepath, 'r') as f:
        code = f.read()

    # Removing docstrings
    stripped_code = ""
    lines = code.split('\n')
    in_docstring = False
    for line in lines:
        if '"""' in line or "'''" in line:
            in_docstring = not in_docstring
            continue
        if not in_docstring and not line.strip().startswith('#'):
            stripped_code += line + '\n'

    summary += stripped_code + '\n'
    return summary



#
# Entry Point
#
if __name__ == '__main__':
    try:
        app()
    except SystemExit as e:
        if e.code != 0:
            raise
