#!/usr/bin/env python3
"""
CLI tool for the Industrial Document Transformer.

This module provides a command-line interface for processing PDF documents
and extracting industrial documentation components.
"""

import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

import click

from indu_doc.manager import Manager


def setup_logging(level: str = "INFO", log_file: Optional[str] = None, enable_stdout: bool = False) -> None:
    """Setup logging configuration."""
    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f'Invalid log level: {level}')

    format_str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    handlers = []

    # Only add stdout handler if explicitly enabled
    if enable_stdout:
        handlers.append(logging.StreamHandler(sys.stdout))

    # Always add file handler if specified
    if log_file:
        handlers.append(logging.FileHandler(log_file))

    # If no handlers are specified, use NullHandler to disable logging
    if not handlers:
        handlers.append(logging.NullHandler())

    logging.basicConfig(
        level=numeric_level,
        format=format_str,
        handlers=handlers
    )


def validate_file_path(path: str, must_exist: bool = True) -> Path:
    """Validate and return a Path object."""
    file_path = Path(path)
    if must_exist and not file_path.exists():
        raise click.BadParameter(f"File does not exist: {path}")
    if must_exist and not file_path.is_file():
        raise click.BadParameter(f"Path is not a file: {path}")
    return file_path


def format_stats(stats: Dict[str, Any]) -> str:
    """Format statistics for display."""
    output = ["Processing Statistics:", "=" * 20]
    for key, value in stats.items():
        if key.startswith("processing_"):
            continue  # Skip processing state info in stats display
        formatted_key = key.replace('_', ' ').replace('num ', '').title()
        output.append(f"{formatted_key}: {value}")
    return '\n'.join(output)


def export_data(manager: Manager, output_file: str, format_type: str) -> None:
    """Export extracted data to file."""
    output_path = Path(output_file)

    data = {
        "stats": manager.get_stats(),
        "xtargets": [str(xt) for xt in manager.get_xtargets()],
        "connections": [str(conn) for conn in manager.get_connections()],
        "attributes": [str(attr) for attr in manager.get_attributes()],
        "links": [str(link) for link in manager.get_links()],
        "pins": [str(pin) for pin in manager.get_pins()]
    }

    if format_type.lower() == 'json':
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)
    else:
        raise ValueError(f"Unsupported export format: {format_type}")

    click.echo(f"Data exported to: {output_path}")


def monitor_processing(manager: Manager, show_progress: bool = True) -> bool:
    """
    Monitor the processing state and display progress.
    Returns True if processing completed successfully, False otherwise.
    """
    last_progress = -1

    while True:
        state_info = manager.get_processing_state()
        state = state_info["state"]
        progress = state_info["progress"]

        if state == "idle":
            return True
        elif state == "error":
            click.echo(
                f"\nProcessing failed: {state_info['error_message']}", err=True)
            return False
        elif state in ["processing", "stopping"]:
            if show_progress and progress["total_pages"] > 0:
                current_progress = int(progress["percentage"] * 100)
                if current_progress != last_progress:
                    current_file = progress.get("current_file", "")
                    file_name = Path(current_file).name if current_file else ""
                    click.echo(
                        f"\rProgress: {current_progress:3d}% ({progress['current_page']}/{progress['total_pages']}) - {file_name}", nl=False)
                    last_progress = current_progress

            time.sleep(0.1)  # Small delay to avoid excessive CPU usage

        # Handle Ctrl+C gracefully
        try:
            time.sleep(0.1)
        except KeyboardInterrupt:
            click.echo("\n\nStopping processing...")
            manager.stop_processing()
            # Wait for graceful shutdown
            while manager.is_processing():
                time.sleep(0.1)
            click.echo("Processing stopped.")
            return False


def process_pdf(pdf_file: Path, config: Path, show_stats: bool, export: Optional[str],
                export_format: str, show_progress: bool = True) -> None:
    """Process a PDF file using the async manager."""
    try:
        manager = Manager.from_config_file(str(config))
        click.echo(f"Processing PDF: {pdf_file}")

        # Start processing (this returns immediately)
        manager.process_pdfs(str(pdf_file))

        # Monitor processing with progress display
        success = monitor_processing(manager, show_progress)

        if not success:
            sys.exit(1)

        click.echo("\n")  # New line after progress display

        # Display statistics if requested (default: True)
        if show_stats:
            stats = manager.get_stats()
            click.echo(format_stats(stats))

        # Export data if requested
        if export:
            export_data(manager, export, export_format)

        click.echo("Processing completed successfully!")

    except Exception as e:
        logging.error(f"Processing failed: {e}")
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@click.command()
@click.argument('pdf_file', type=click.Path(exists=True, file_okay=True, dir_okay=False, path_type=Path))
@click.option('-c', '--config', 'config_file', required=True,
              type=click.Path(exists=True, file_okay=True,
                              dir_okay=False, path_type=Path),
              help='Path to configuration file (required)')
@click.option('--no-stats', is_flag=True,
              help='Disable processing statistics display')
@click.option('--no-progress', is_flag=True,
              help='Disable progress display during processing')
@click.option('--export', type=str,
              help='Export results to file')
@click.option('--export-format', type=click.Choice(['json']), default='json',
              help='Export format (default: json)')
@click.option('-v', '--verbose', is_flag=True,
              help='Enable verbose logging (equivalent to --log-level DEBUG)')
@click.option('--log-level', type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']),
              default='INFO', help='Set the logging level (default: INFO)')
@click.option('--log-file', type=str,
              help='Write logs to file')
@click.option('--out-to-std', is_flag=True,
              help='Enable logging output to stdout (disabled by default)')
def main(pdf_file: Path, config_file: Path, no_stats: bool, no_progress: bool,
         export: Optional[str], export_format: str, verbose: bool, log_level: str,
         log_file: Optional[str], out_to_std: bool) -> None:
    """Industrial Document Transformer CLI - Process PDF files and extract industrial documentation components."""

    # Determine logging level (verbose flag overrides log-level)
    actual_log_level = "DEBUG" if verbose else log_level

    # Setup logging (only to stdout if --out-to-std is specified)
    setup_logging(actual_log_level, log_file, out_to_std)

    # Execute the processing (show_stats is opposite of no_stats, show_progress is opposite of no_progress)
    process_pdf(pdf_file, config_file, not no_stats,
                export, export_format, not no_progress)


if __name__ == "__main__":
    main()
