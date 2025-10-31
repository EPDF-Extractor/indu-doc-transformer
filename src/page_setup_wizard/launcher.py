#!/usr/bin/env python3
"""
Page Setup Wizard CLI for InduDoc Transformer.

This module provides a command-line interface for interactively setting up
page extraction parameters for PDF documents. It allows users to define
regions of interest and table structures for document processing.
"""

import logging
import sys
import pymupdf # type: ignore
from pathlib import Path
from typing import Optional

import click

from indu_doc.plugins.eplan_pdfs.page_settings import PageSettings
from page_setup_wizard.table_loader import do_main_loop


def setup_logging(level: str = "INFO", log_file: Optional[str] = None, enable_stdout: bool = False) -> None:
    """Setup logging configuration.
    
    :param level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    :type level: str
    :param log_file: Optional log file path
    :type log_file: Optional[str]
    :param enable_stdout: Whether to enable stdout logging
    :type enable_stdout: bool
    """
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
    """Validate and return a Path object.
    
    :param path: File path to validate
    :type path: str
    :param must_exist: Whether the file must exist
    :type must_exist: bool
    :return: Validated Path object
    :rtype: Path
    """
    file_path = Path(path)
    if must_exist and not file_path.exists():
        raise click.BadParameter(f"File does not exist: {path}")
    if must_exist and not file_path.is_file():
        raise click.BadParameter(f"Path is not a file: {path}")
    return file_path


@click.command()
@click.argument('pdf_path', type=click.Path(exists=True, file_okay=True, dir_okay=False, path_type=Path))
@click.option('-o', '--output', type=click.Path(exists=False, file_okay=True, dir_okay=False, path_type=Path),
              help='Filename of the generated settings file',
              default='page_settings.json')
@click.option('-v', '--verbose', is_flag=True,
              help='Enable verbose logging')
def main(pdf_path: Path, output: Path, verbose: bool) -> None:
    """Page Setup Wizard CLI - Interactive page extraction setup.
    
    Launches an interactive wizard for setting up page extraction parameters
    for the specified PDF document.
    
    :param pdf_path: Path to the PDF file to process
    :type pdf_path: Path
    :param output: Path for the output settings file
    :type output: Path
    :param verbose: Enable verbose logging
    :type verbose: bool
    """
    # Determine logging level (verbose flag overrides log-level)
    actual_log_level = "DEBUG" if verbose else "WARNING"

    # Setup logging 
    setup_logging(actual_log_level, "log.txt", False)

    # make settings
    settings = PageSettings(str(output))

    # load PDF
    pdf = pymupdf.open(pdf_path)

    # main loop
    do_main_loop(pdf, settings)


if __name__ == "__main__":
    main()
