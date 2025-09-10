#!/usr/bin/env python3
"""
Enhanced status display for pytp with better formatting and command visibility.
Fixes:
1. Icon alignment in tables
2. Shows actual command being executed
3. Better error handling for tape I/O errors
"""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.align import Align
import subprocess
import re

def show_tape_status_enhanced(self):
    """
    Enhanced version with better formatting and error handling.
    """
    console = Console()
    
    # First check if tape is accessible
    try:
        # Try basic status command
        result = subprocess.run(
            ['mt', '-f', self.device_path, 'status'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode != 0:
            if "Input/output error" in result.stderr:
                console.print("[red]⚠️ Tape I/O Error[/red]")
                console.print("The tape may be in an inconsistent state.")
                console.print("\nSuggested fixes:")
                console.print("1. Rewind: [cyan]mt -f /dev/nst0 rewind[/cyan]")
                console.print("2. Reset block size: [cyan]mt -f /dev/nst0 setblk 0[/cyan]")
                console.print("3. Check physical connection")
                return
                
        status_output = result.stdout
        
    except subprocess.TimeoutExpired:
        console.print("[red]⚠️ Tape Status Check Timeout[/red]")
        return
        
    # Check if tape is busy by looking at /dev/nst0 usage
    lsof_result = subprocess.run(
        ['lsof', self.device_path],
        capture_output=True,
        text=True
    )
    
    if lsof_result.stdout:
        # Tape is busy - show what's using it
        show_busy_status(console, lsof_result.stdout, self.device_path)
    else:
        # Tape is available - show normal status
        show_normal_status(console, status_output, self.device_path)


def show_busy_status(console, lsof_output, device_path):
    """
    Display enhanced busy status with actual command information.
    """
    # Parse lsof output to get process details
    lines = lsof_output.strip().split('\n')
    if len(lines) > 1:
        # Parse the actual process line (skip header)
        parts = lines[1].split()
        if len(parts) >= 3:
            command = parts[0]
            pid = parts[1]
            user = parts[2]
            
            # Try to get full command line
            try:
                with open(f'/proc/{pid}/cmdline', 'r') as f:
                    full_command = f.read().replace('\0', ' ').strip()
            except:
                full_command = command
    
    # Create status table with proper alignment
    table = Table(title="TAPE DRIVE STATUS: BUSY 📼", 
                  title_justify="center",
                  show_header=True,
                  header_style="bold magenta")
    
    table.add_column("Operation", style="cyan", no_wrap=True, width=25)
    table.add_column("Details", style="white")
    
    table.add_row("Current Operation", f"⚙️  Tape Control")
    table.add_row("Process", f"{command} (PID {pid})")
    table.add_row("User", user)
    table.add_row("Device", device_path)
    table.add_row("Full Command", full_command or f"{command} {device_path}")
    
    # Center the emoji in the title
    panel = Panel(
        table,
        title="[bold]📼 TAPE DRIVE STATUS: BUSY[/bold]",
        title_align="center"
    )
    
    console.print(panel)
    console.print(f"\n[yellow]To check progress:[/yellow] [cyan]ps aux | grep {pid}[/cyan]")
    console.print(f"[yellow]To kill if stuck:[/yellow] [cyan]kill -9 {pid}[/cyan]")


def show_normal_status(console, status_output, device_path):
    """
    Display normal tape status with enhanced formatting.
    """
    # Parse status output
    file_number = "Unknown"
    block_number = "Unknown"
    block_size = "Unknown"
    status_bits = []
    
    for line in status_output.split('\n'):
        if "File number=" in line:
            match = re.search(r'File number=(\d+), block number=([\d-]+)', line)
            if match:
                file_number = match.group(1)
                block_number = match.group(2)
                if block_number == "-1":
                    block_number = "Invalid (-1) ⚠️"
                    
        elif "Tape block size" in line:
            match = re.search(r'Tape block size (\d+)', line)
            if match:
                size = int(match.group(1))
                if size == 0:
                    block_size = "Variable (0)"
                else:
                    block_size = f"Fixed ({size} bytes)"
                    
        elif "General status bits" in line:
            # Extract status flags
            next_line_idx = status_output.index(line) + len(line) + 1
            if next_line_idx < len(status_output):
                next_line = status_output[next_line_idx:].split('\n')[0]
                status_bits = next_line.strip().split()
    
    # Create status table
    table = Table(title="TAPE DRIVE STATUS 📼",
                  title_justify="center",
                  show_header=True,
                  header_style="bold green")
    
    table.add_column("Property", style="cyan", no_wrap=True, width=25)
    table.add_column("Value", style="white")
    
    table.add_row("Device", device_path)
    table.add_row("File Position", file_number)
    table.add_row("Block Position", block_number)
    table.add_row("Block Size", block_size)
    table.add_row("Status Flags", " ".join(status_bits))
    
    # Add tape position command
    try:
        tell_result = subprocess.run(
            ['mt', '-f', device_path, 'tell'],
            capture_output=True,
            text=True,
            timeout=2
        )
        if tell_result.returncode == 0:
            table.add_row("Absolute Position", tell_result.stdout.strip())
    except:
        pass
    
    # Center align the panel
    panel = Panel(
        table,
        title="[bold]📼 TAPE DRIVE STATUS[/bold]",
        title_align="center"
    )
    
    console.print(panel)
    
    # Show warnings if needed
    if "-1" in str(block_number):
        console.print("\n[red]⚠️ Warning: Invalid block position detected![/red]")
        console.print("Run: [cyan]mt -f /dev/nst0 rewind[/cyan] to reset tape position")
        
    if block_size != "Variable (0)":
        console.print("\n[yellow]Note: Fixed block size set[/yellow]")
        console.print("For variable blocks: [cyan]mt -f /dev/nst0 setblk 0[/cyan]")


# Additional helper to show what command is actually running
def get_tape_process_details(device_path):
    """
    Get detailed information about processes using the tape drive.
    """
    try:
        # Use fuser to get PIDs
        result = subprocess.run(
            ['fuser', '-v', device_path],
            capture_output=True,
            text=True
        )
        
        if result.stderr:  # fuser outputs to stderr
            return parse_fuser_output(result.stderr)
            
        # Fallback to lsof
        result = subprocess.run(
            ['lsof', device_path],
            capture_output=True,
            text=True
        )
        
        if result.stdout:
            return parse_lsof_output(result.stdout)
            
    except Exception as e:
        return None
        
    return None


def parse_fuser_output(output):
    """
    Parse fuser -v output to get process details.
    Example:
                         USER        PID ACCESS COMMAND
    /dev/nst0:           root      12345 f....  mt
    """
    lines = output.strip().split('\n')
    for line in lines:
        if 'PID' in line:
            continue  # Skip header
        parts = line.split()
        if len(parts) >= 4:
            return {
                'user': parts[-3],
                'pid': parts[-2],
                'command': parts[-1]
            }
    return None