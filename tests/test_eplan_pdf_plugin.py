"""
Tests for the EplanPDFPlugin module.

This module tests the EplanPDFPlugin class and its PDF processing functionality.
"""

import pytest
import tempfile
import os
from unittest.mock import MagicMock, patch, AsyncMock

from indu_doc.plugins.eplan_pdfs.eplan_pdf_plugin import EplanPDFPlugin
from indu_doc.configs import AspectsConfig
from indu_doc.plugins.eplan_pdfs.page_settings import PageSettings
from indu_doc.plugins.events import ProcessingProgressEvent


class TestEplanPDFPlugin:
    """Test EplanPDFPlugin class."""

    @pytest.fixture
    def mock_configs(self):
        """Create mock AspectsConfig."""
        configs = MagicMock(spec=AspectsConfig)
        return configs

    @pytest.fixture
    def mock_page_settings(self):
        """Create mock PageSettings."""
        settings = MagicMock(spec=PageSettings)
        return settings

    @pytest.fixture
    def plugin(self, mock_configs, mock_page_settings):
        """Create EplanPDFPlugin instance."""
        return EplanPDFPlugin(mock_configs, mock_page_settings)

    def test_init(self, plugin, mock_configs, mock_page_settings):
        """Test plugin initialization."""
        assert plugin.page_settings == mock_page_settings
        assert plugin.page_processor is not None

    def test_from_config_files(self):
        """Test creating plugin from config files."""
        config_data = {"aspects": [{"Aspect": "Test", "Separator": "="}]}
        page_data = {"test": "settings"}

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as config_file:
            import json
            json.dump(config_data, config_file)
            config_path = config_file.name

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as page_file:
            json.dump(page_data, page_file)
            page_path = page_file.name

        try:
            with patch('indu_doc.configs.AspectsConfig.init_from_file') as mock_config_init:
                with patch('indu_doc.plugins.eplan_pdfs.page_settings.PageSettings.init_from_file') as mock_page_init:
                    mock_configs = MagicMock()
                    mock_settings = MagicMock()
                    mock_config_init.return_value = mock_configs
                    mock_page_init.return_value = mock_settings

                    plugin = EplanPDFPlugin.from_config_files(config_path, page_path)

                    assert isinstance(plugin, EplanPDFPlugin)
                    mock_config_init.assert_called_once_with(config_path)
                    mock_page_init.assert_called_once_with(page_path)
        finally:
            os.unlink(config_path)
            os.unlink(page_path)

    @patch('indu_doc.plugins.eplan_pdfs.eplan_pdf_plugin.pymupdf')
    @pytest.mark.asyncio
    async def test_process_files_async_single_file(self, mock_pymupdf, plugin):
        """Test processing a single PDF file."""
        # Mock PDF document
        mock_doc = MagicMock()
        mock_doc.__len__ = lambda self: 3  # 3 pages
        mock_page = MagicMock()
        mock_doc.__getitem__ = lambda self, idx: mock_page
        mock_doc.close = MagicMock()

        mock_pymupdf.open.return_value = mock_doc

        # Mock page processor
        plugin.page_processor.run = MagicMock()

        # Mock event emitter
        plugin.event_emitter.emit = AsyncMock()

        file_paths = ("test.pdf",)

        result = await plugin.process_files_async(file_paths)

        # Verify PDF was opened
        mock_pymupdf.open.assert_called_once_with("test.pdf")

        # Verify progress events were emitted (1 per page = 3 total)
        assert plugin.event_emitter.emit.call_count == 3

        # Verify page processor was called for each page
        assert plugin.page_processor.run.call_count == 3

        # Verify result is the sub_god
        assert result == plugin.sub_god

    @patch('indu_doc.plugins.eplan_pdfs.eplan_pdf_plugin.pymupdf')
    @pytest.mark.asyncio
    async def test_process_files_async_multiple_files(self, mock_pymupdf, plugin):
        """Test processing multiple PDF files."""
        # Mock PDF documents
        mock_doc1 = MagicMock()
        mock_doc1.__len__ = lambda self: 2
        mock_doc1.__getitem__ = lambda self, idx: MagicMock()
        mock_doc1.close = MagicMock()

        mock_doc2 = MagicMock()
        mock_doc2.__len__ = lambda self: 1
        mock_doc2.__getitem__ = lambda self, idx: MagicMock()
        mock_doc2.close = MagicMock()

        mock_pymupdf.open.side_effect = [mock_doc1, mock_doc2]

        # Mock page processor
        plugin.page_processor.run = MagicMock()

        # Mock event emitter
        plugin.event_emitter.emit = AsyncMock()

        file_paths = ("test1.pdf", "test2.pdf")

        result = await plugin.process_files_async(file_paths)

        # Verify both PDFs were opened
        assert mock_pymupdf.open.call_count == 2

        # Verify page processor was called for total pages (2 + 1 = 3)
        assert plugin.page_processor.run.call_count == 3

        # Verify processing completed
        assert result == plugin.sub_god

    @patch('indu_doc.plugins.eplan_pdfs.eplan_pdf_plugin.pymupdf')
    @pytest.mark.asyncio
    async def test_process_files_async_with_exception(self, mock_pymupdf, plugin):
        """Test processing handles exceptions properly."""
        mock_pymupdf.open.side_effect = Exception("PDF error")

        with pytest.raises(Exception, match="PDF error"):
            await plugin.process_files_async(("test.pdf",))

        assert plugin._error_message == "PDF error"

    @patch('indu_doc.plugins.eplan_pdfs.eplan_pdf_plugin.pymupdf')
    @pytest.mark.asyncio
    async def test_process_files_async_empty_tuple(self, mock_pymupdf, plugin):
        """Test processing with empty file tuple."""
        file_paths = ()

        result = await plugin.process_files_async(file_paths)

        # Should not open any PDFs
        mock_pymupdf.open.assert_not_called()
        assert result == plugin.sub_god

    def test_get_supported_file_extensions(self, plugin):
        """Test getting supported file extensions."""
        extensions = plugin.get_supported_file_extensions()
        assert extensions == ("pdf",)

    @patch('indu_doc.plugins.eplan_pdfs.eplan_pdf_plugin.pymupdf')
    @pytest.mark.asyncio
    async def test_progress_tracking(self, mock_pymupdf, plugin):
        """Test progress tracking during processing."""
        # Mock PDF document with 2 pages
        mock_doc = MagicMock()
        mock_doc.__len__ = lambda self: 2
        mock_page = MagicMock()
        mock_doc.__getitem__ = lambda self, idx: mock_page
        mock_doc.close = MagicMock()

        mock_pymupdf.open.return_value = mock_doc

        # Mock page processor
        plugin.page_processor.run = MagicMock()

        # Mock event emitter to capture progress events
        plugin.event_emitter.emit = AsyncMock()

        await plugin.process_files_async(("test.pdf",))

        # Check that progress events were emitted
        calls = plugin.event_emitter.emit.call_args_list

        # Should have progress events for pages 1 and 2
        progress_events = [call for call in calls if isinstance(call[0][0], ProcessingProgressEvent)]

        assert len(progress_events) == 2  # page 1 + page 2

        # Check first progress event (page 1)
        first_event = progress_events[0][0][0]
        assert first_event.current_page == 1
        assert first_event.total_pages == 2
        assert first_event.current_file == "test.pdf"

        # Check second progress event (page 2)
        second_event = progress_events[1][0][0]
        assert second_event.current_page == 2
        assert second_event.total_pages == 2
        assert second_event.current_file == "test.pdf"

    @patch('indu_doc.plugins.eplan_pdfs.eplan_pdf_plugin.pymupdf')
    @pytest.mark.asyncio
    async def test_file_processing_state(self, mock_pymupdf, plugin):
        """Test that current file is tracked during processing."""
        # Mock PDF documents
        mock_doc1 = MagicMock()
        mock_doc1.__len__ = lambda self: 1
        mock_doc1.__getitem__ = lambda self, idx: MagicMock()
        mock_doc1.close = MagicMock()

        mock_doc2 = MagicMock()
        mock_doc2.__len__ = lambda self: 1
        mock_doc2.__getitem__ = lambda self, idx: MagicMock()
        mock_doc2.close = MagicMock()

        mock_pymupdf.open.side_effect = [mock_doc1, mock_doc2]

        # Mock page processor
        plugin.page_processor.run = MagicMock()

        # Mock event emitter
        plugin.event_emitter.emit = AsyncMock()

        await plugin.process_files_async(("file1.pdf", "file2.pdf"))

        # Check that current_file was set appropriately
        # This is tested indirectly through the progress events
        progress_calls = [call for call in plugin.event_emitter.emit.call_args_list
                         if isinstance(call[0][0], ProcessingProgressEvent)]

        # Should have progress events for both files
        file1_events = [call for call in progress_calls if call[0][0].current_file == "file1.pdf"]
        file2_events = [call for call in progress_calls if call[0][0].current_file == "file2.pdf"]

        assert len(file1_events) > 0
        assert len(file2_events) > 0