"""
Tests for the CLI module.

This module tests CLI functions including logging setup, file validation,
statistics formatting, data export, and PDF processing.
"""

import pytest
import tempfile
import os
import logging
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

from indu_doc.cli import (
    setup_logging,
    validate_file_path,
    format_stats,
    export_data,
    monitor_processing,
    process_pdf,
    main
)


class TestSetupLogging:
    """Test logging setup functionality."""

    def test_setup_logging_valid_level(self):
        """Test setup_logging with valid log level."""
        with patch('logging.basicConfig') as mock_config:
            setup_logging("INFO")
            mock_config.assert_called_once()
            args, kwargs = mock_config.call_args
            assert kwargs['level'] == logging.INFO

    def test_setup_logging_invalid_level(self):
        """Test setup_logging with invalid log level raises ValueError."""
        with pytest.raises(ValueError, match="Invalid log level"):
            setup_logging("INVALID")

    def test_setup_logging_with_stdout(self):
        """Test setup_logging with stdout enabled."""
        with patch('logging.basicConfig') as mock_config:
            setup_logging("DEBUG", enable_stdout=True)
            mock_config.assert_called_once()
            args, kwargs = mock_config.call_args
            assert len(kwargs['handlers']) == 1
            assert isinstance(kwargs['handlers'][0], logging.StreamHandler)

    def test_setup_logging_with_file(self):
        """Test setup_logging with log file."""
        with patch('logging.basicConfig') as mock_config:
            setup_logging("WARNING", log_file="test.log")
            mock_config.assert_called_once()
            args, kwargs = mock_config.call_args
            assert len(kwargs['handlers']) == 1
            assert isinstance(kwargs['handlers'][0], logging.FileHandler)

    def test_setup_logging_no_handlers(self):
        """Test setup_logging with no handlers uses NullHandler."""
        with patch('logging.basicConfig') as mock_config:
            setup_logging("ERROR")
            mock_config.assert_called_once()
            args, kwargs = mock_config.call_args
            assert len(kwargs['handlers']) == 1
            assert isinstance(kwargs['handlers'][0], logging.NullHandler)


class TestValidateFilePath:
    """Test file path validation."""

    def test_validate_existing_file(self):
        """Test validation of existing file."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = f.name

        try:
            result = validate_file_path(temp_path)
            assert isinstance(result, Path)
            assert str(result) == temp_path
        finally:
            os.unlink(temp_path)

    def test_validate_nonexistent_file_must_exist(self):
        """Test validation fails for nonexistent file when must_exist=True."""
        from click.exceptions import BadParameter
        with pytest.raises(BadParameter):
            validate_file_path("/nonexistent/file.txt", must_exist=True)

    def test_validate_nonexistent_file_must_not_exist(self):
        """Test validation succeeds for nonexistent file when must_exist=False."""
        result = validate_file_path("/nonexistent/file.txt", must_exist=False)
        # On Windows, Path converts / to \
        expected_path = str(Path("/nonexistent/file.txt"))
        assert str(result) == expected_path

    def test_validate_directory_as_file(self):
        """Test validation fails when path is directory but file required."""
        from click.exceptions import BadParameter
        with tempfile.TemporaryDirectory() as temp_dir:
            with pytest.raises(BadParameter):
                validate_file_path(temp_dir, must_exist=True)


class TestFormatStats:
    """Test statistics formatting."""

    def test_format_stats_basic(self):
        """Test basic statistics formatting."""
        stats = {
            "num_xtargets": 10,
            "num_connections": 5,
            "processing_time": 120.5
        }
        result = format_stats(stats)
        assert "Processing Statistics:" in result
        assert "Xtargets: 10" in result
        assert "Connections: 5" in result
        assert "processing_time" not in result  # Should be filtered out

    def test_format_stats_empty(self):
        """Test formatting with empty stats."""
        stats = {}
        result = format_stats(stats)
        assert "Processing Statistics:" in result
        assert "=" * 20 in result


class TestExportData:
    """Test data export functionality."""

    @patch('indu_doc.cli.json.dump')
    @patch('builtins.open', new_callable=mock_open)
    def test_export_data_json(self, mock_file, mock_json_dump):
        """Test exporting data as JSON."""
        mock_manager = MagicMock()
        mock_manager.get_stats.return_value = {"num_xtargets": 5}
        mock_manager.get_xtargets.return_value = ["target1"]
        mock_manager.get_connections.return_value = ["conn1"]
        mock_manager.get_attributes.return_value = ["attr1"]
        mock_manager.get_links.return_value = ["link1"]
        mock_manager.get_pins.return_value = ["pin1"]

        export_data(mock_manager, "output.json", "json")

        mock_file.assert_called_once_with(Path("output.json"), 'w')
        mock_json_dump.assert_called_once()

    def test_export_data_invalid_format(self):
        """Test exporting with invalid format raises ValueError."""
        mock_manager = MagicMock()
        with pytest.raises(ValueError, match="Unsupported export format"):
            export_data(mock_manager, "output.txt", "invalid")


class TestMonitorProcessing:
    """Test processing monitoring."""

    @patch('indu_doc.cli.time.sleep')
    @patch('indu_doc.cli.click.echo')
    def test_monitor_processing_success(self, mock_echo, mock_sleep):
        """Test successful processing monitoring."""
        mock_manager = MagicMock()
        mock_manager.is_processing.side_effect = [True, True, False]
        mock_manager.get_file_progress.return_value = {"file1.pdf": 100.0}
        mock_manager.has_errors.return_value = False

        result = monitor_processing(mock_manager)
        assert result is True
        mock_echo.assert_called()

    @patch('indu_doc.cli.time.sleep')
    @patch('indu_doc.cli.click.echo')
    def test_monitor_processing_keyboard_interrupt(self, mock_echo, mock_sleep):
        """Test processing monitoring with keyboard interrupt."""
        mock_manager = MagicMock()
        mock_manager.is_processing.side_effect = [True, KeyboardInterrupt, False]
        mock_manager.stop_processing = MagicMock()

        result = monitor_processing(mock_manager)
        assert result is False
        mock_manager.stop_processing.assert_called_once()

    @patch('indu_doc.cli.time.sleep')
    @patch('indu_doc.cli.click.echo')
    def test_monitor_processing_error(self, mock_echo, mock_sleep):
        """Test processing monitoring with errors."""
        mock_manager = MagicMock()
        mock_manager.is_processing.side_effect = [True, False]
        mock_manager.has_errors.return_value = True
        mock_manager.get_processing_state.return_value = [
            {"state": "error", "error_message": "Test error"}
        ]

        result = monitor_processing(mock_manager)
        assert result is False


class TestProcessPDF:
    """Test PDF processing function."""

    @patch('indu_doc.cli.Manager.from_config_files')
    @patch('indu_doc.plugins.eplan_pdfs.eplan_pdf_plugin.EplanPDFPlugin.from_config_files')
    @patch('indu_doc.cli.click.echo')
    @patch('indu_doc.cli.monitor_processing')
    def test_process_pdf_success(self, mock_monitor, mock_echo, mock_plugin_class, mock_manager_class):
        """Test successful PDF processing."""
        mock_manager = MagicMock()
        mock_manager_class.return_value = mock_manager
        mock_plugin = MagicMock()
        mock_plugin_class.return_value = mock_plugin
        mock_manager.has_errors.return_value = False
        mock_monitor.return_value = True

        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as pdf_file:
            pdf_path = pdf_file.name
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as config_file:
            config_path = config_file.name
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as extraction_file:
            extraction_path = extraction_file.name

        try:
            process_pdf(Path(pdf_path), Path(config_path), Path(extraction_path),
                       show_stats=True, export=None, export_format="json", show_progress=True)

            mock_manager.register_plugin.assert_called_once_with(mock_plugin)
            mock_manager.process_files.assert_called_once()
        finally:
            os.unlink(pdf_path)
            os.unlink(config_path)
            os.unlink(extraction_path)

    @patch('indu_doc.cli.Manager.from_config_files')
    @patch('indu_doc.cli.click.echo')
    def test_process_pdf_with_errors(self, mock_echo, mock_manager_class):
        """Test PDF processing with errors."""
        mock_manager = MagicMock()
        mock_manager_class.return_value = mock_manager
        mock_manager.has_errors.return_value = True
        mock_manager.get_processing_state.return_value = [
            {"state": "error", "error_message": "Processing failed"}
        ]

        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as pdf_file:
            pdf_path = pdf_file.name
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as config_file:
            config_path = config_file.name
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as extraction_file:
            extraction_path = extraction_file.name

        try:
            with pytest.raises(SystemExit):
                process_pdf(Path(pdf_path), Path(config_path), Path(extraction_path),
                           show_stats=True, export=None, export_format="json", show_progress=True)
        finally:
            os.unlink(pdf_path)
            os.unlink(config_path)
            os.unlink(extraction_path)


class TestMainFunction:
    """Test the main CLI function."""

    @patch('indu_doc.cli.process_pdf')
    @patch('indu_doc.cli.setup_logging')
    @patch('indu_doc.cli.click.echo')
    def test_main_basic(self, mock_echo, mock_setup_logging, mock_process_pdf):
        """Test main function with basic arguments."""
        # Create temporary files
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as pdf_file:
            pdf_path = pdf_file.name
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as config_file:
            config_path = config_file.name
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as extraction_file:
            extraction_path = extraction_file.name

        try:
            with patch('sys.argv', ['indu-doc', pdf_path, '-c', config_path, '-e', extraction_path]):
                with pytest.raises(SystemExit):
                    main()
                mock_setup_logging.assert_called_once()
                mock_process_pdf.assert_called_once()
        finally:
            os.unlink(pdf_path)
            os.unlink(config_path)
            os.unlink(extraction_path)

    @patch('indu_doc.cli.setup_logging')
    def test_main_verbose_flag(self, mock_setup_logging):
        """Test main function with verbose flag."""
        # Create temporary files
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as pdf_file:
            pdf_path = pdf_file.name
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as config_file:
            config_path = config_file.name
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as extraction_file:
            extraction_path = extraction_file.name

        try:
            with patch('sys.argv', ['indu-doc', pdf_path, '-c', config_path, '-e', extraction_path, '--verbose']):
                with patch('indu_doc.cli.process_pdf'):
                    with pytest.raises(SystemExit):
                        main()
                    # Should be called with DEBUG level due to verbose flag
                    args = mock_setup_logging.call_args[0]
                    assert args[0] == "DEBUG"
        finally:
            os.unlink(pdf_path)
            os.unlink(config_path)
            os.unlink(extraction_path)