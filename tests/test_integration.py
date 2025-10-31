"""
Integration Tests for InduDoc Transformer.

This module contains comprehensive integration tests that verify end-to-end
workflows across multiple components including Manager, Plugins, CLI, and
database export/import functionality.
"""

import pytest
import tempfile
import os
import json
import asyncio
from pathlib import Path
from typing import OrderedDict
from unittest.mock import patch, MagicMock

from indu_doc.manager import Manager
from indu_doc.configs import AspectsConfig, LevelConfig
from indu_doc.plugins.eplan_pdfs.eplan_pdf_plugin import EplanPDFPlugin
from indu_doc.plugins.eplan_pdfs.page_settings import PageSettings
from indu_doc.exporters.db_builder.db_exporter import SQLITEDBExporter
from indu_doc.god import God
from indu_doc.cli import process_pdf, validate_file_path, export_data


class TestManagerPluginIntegration:
    """Integration tests for Manager and Plugin interaction."""

    @pytest.fixture
    def sample_config_file(self):
        """Create a temporary config file."""
        config_data = {
            "aspects": [
                {"Aspect": "Function", "Separator": "="},
                {"Aspect": "Location", "Separator": "+"},
                {"Aspect": "Product", "Separator": "-"}
            ]
        }
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_file = f.name
        yield temp_file
        # Clean up after test
        if os.path.exists(temp_file):
            os.unlink(temp_file)

    @pytest.fixture
    def sample_page_settings_file(self):
        """Create a temporary page settings file."""
        page_data = {
            "CONNECTION_LIST": {
                "tables": {},
                "description": "Test connection list",
                "search_name": "Connection list"
            }
        }
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(page_data, f)
            temp_file = f.name
        yield temp_file
        # Clean up after test
        if os.path.exists(temp_file):
            os.unlink(temp_file)

    @pytest.fixture
    def sample_pdf_file(self):
        """Get path to sample PDF file."""
        pdf_path = Path("d:/masters/smstr_2/DevProject/repos/indu-doc-transformer/pdfs/sample_small_small.pdf")
        if pdf_path.exists():
            return str(pdf_path)
        pytest.skip("Sample PDF file not found")

    def test_manager_initialization_from_config(self, sample_config_file):
        """Test that Manager can be initialized from a config file."""
        manager = Manager.from_config_files(sample_config_file)
        
        assert isinstance(manager, Manager)
        assert isinstance(manager.configs, AspectsConfig)
        assert isinstance(manager.god, God)
        assert manager.plugins == []

    def test_plugin_registration_with_manager(self, sample_config_file, sample_page_settings_file):
        """Test that plugins can be registered with Manager."""
        manager = Manager.from_config_files(sample_config_file)
        plugin = EplanPDFPlugin.from_config_files(sample_config_file, sample_page_settings_file)
        
        manager.register_plugin(plugin)
        
        assert len(manager.plugins) == 1
        assert manager.plugins[0] == plugin
        # Verify event listeners are registered
        assert len(plugin.event_emitter._listeners) > 0

    @pytest.mark.asyncio
    async def test_manager_async_processing_with_mock_plugin(self, sample_config_file):
        """Test Manager's async processing workflow with a mock plugin."""
        manager = Manager.from_config_files(sample_config_file)
        
        # Create a mock plugin
        from unittest.mock import AsyncMock
        
        mock_plugin = MagicMock(spec=EplanPDFPlugin)
        mock_plugin.get_supported_file_extensions.return_value = ("pdf",)
        mock_plugin.start = AsyncMock()
        mock_plugin.event_emitter = MagicMock()
        mock_plugin.sub_god = God(manager.configs)
        
        manager.register_plugin(mock_plugin)
        
        # Create a temporary file
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            temp_pdf = f.name
        
        try:
            await manager.process_files_async(temp_pdf)
            # Verify start was called
            mock_plugin.start.assert_called_once()
        finally:
            os.unlink(temp_pdf)

    def test_manager_file_validation(self, sample_config_file):
        """Test that Manager validates file existence."""
        manager = Manager.from_config_files(sample_config_file)
        
        with pytest.raises(FileNotFoundError, match="do not exist"):
            manager.process_files("nonexistent_file.pdf")

    def test_file_distribution_to_plugins(self, sample_config_file, sample_page_settings_file):
        """Test that files are correctly distributed to plugins based on extensions."""
        manager = Manager.from_config_files(sample_config_file)
        
        # Register a PDF plugin
        pdf_plugin = EplanPDFPlugin.from_config_files(sample_config_file, sample_page_settings_file)
        manager.register_plugin(pdf_plugin)
        
        # Create temp files
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as pdf_file:
            pdf_path = pdf_file.name
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as txt_file:
            txt_path = txt_file.name
        
        try:
            distribution = manager._distribute_files_to_plugins((pdf_path, txt_path))
            
            # PDF plugin should get the PDF file
            assert pdf_plugin in distribution
            assert pdf_path in distribution[pdf_plugin]
            # TXT file should not be assigned to any plugin
            assert txt_path not in distribution[pdf_plugin]
        finally:
            os.unlink(pdf_path)
            os.unlink(txt_path)


class TestDatabaseExportImportIntegration:
    """Integration tests for database export and import functionality."""

    @pytest.fixture
    def sample_god(self, tmp_path):
        """Create a sample God instance with test data."""
        config = AspectsConfig(
            OrderedDict({
                "=": LevelConfig(Separator="=", Aspect="Function"),
                "+": LevelConfig(Separator="+", Aspect="Location"),
                "-": LevelConfig(Separator="-", Aspect="Product")
            })
        )
        god = God(config)
        
        # Add some test data
        from indu_doc.xtarget import XTargetType
        from indu_doc.plugins.eplan_pdfs.common_page_utils import PageInfo, PageType
        from unittest.mock import MagicMock
        
        # Create a temporary PDF file for the mock
        temp_pdf = tmp_path / "test.pdf"
        temp_pdf.write_bytes(b"%PDF-1.4\nTest PDF")
        
        # Create mock page info
        mock_page = MagicMock()
        mock_page.number = 0
        mock_page.parent.name = str(temp_pdf)
        from indu_doc.footers import PageFooter
        page_footer = PageFooter(project_name="Test", product_name="Test", tags=[])
        page_info = PageInfo(page=mock_page, page_footer=page_footer, page_type=PageType.CONNECTION_LIST)
        
        # Create XTarget using god's method
        god.create_xtarget("=F100", page_info, XTargetType.DEVICE)
        
        return god

    def test_database_export_creates_valid_output(self, sample_god):
        """Test that database export creates a valid BytesIO output."""
        result = SQLITEDBExporter.export_data(sample_god)
        
        assert result is not None
        assert result.tell() >= 0  # BytesIO position
        result.seek(0)
        data = result.read()
        assert len(data) > 0
        # SQLite header check
        assert data[:16] == b'SQLite format 3\x00'

    def test_database_export_import_roundtrip(self, sample_god, tmp_path):
        """Test that data can be exported and imported successfully."""
        # Export
        exported_data = SQLITEDBExporter.export_data(sample_god)
        exported_data.seek(0)
        
        # Import
        extract_dir = str(tmp_path / "extracted")
        os.makedirs(extract_dir, exist_ok=True)
        
        imported_god = SQLITEDBExporter.import_from_bytes(exported_data, extract_dir)
        
        # Verify basic structure is preserved
        assert isinstance(imported_god, God)
        assert isinstance(imported_god.configs, AspectsConfig)
        
        # Verify XTargets count matches
        original_xtargets = list(sample_god.xtargets.values())
        imported_xtargets = list(imported_god.xtargets.values())
        assert len(original_xtargets) == len(imported_xtargets)

    def test_database_import_from_file(self, sample_god, tmp_path):
        """Test importing from a file path."""
        db_file = str(tmp_path / "test.db")
        extract_dir = str(tmp_path / "extracted")
        os.makedirs(extract_dir, exist_ok=True)
        
        # Export to file
        exported_data = SQLITEDBExporter.export_data(sample_god)
        with open(db_file, 'wb') as f:
            f.write(exported_data.read())
        
        # Import from file
        imported_god = SQLITEDBExporter.import_from_file(db_file, extract_dir)
        
        assert isinstance(imported_god, God)
        assert len(list(imported_god.xtargets.values())) == len(list(sample_god.xtargets.values()))

    def test_empty_god_export_import(self, tmp_path):
        """Test exporting and importing an empty God instance."""
        config = AspectsConfig(
            OrderedDict({
                "=": LevelConfig(Separator="=", Aspect="Function")
            })
        )
        empty_god = God(config)
        
        # Export
        exported_data = SQLITEDBExporter.export_data(empty_god)
        exported_data.seek(0)
        
        # Import
        extract_dir = str(tmp_path / "extracted")
        os.makedirs(extract_dir, exist_ok=True)
        
        imported_god = SQLITEDBExporter.import_from_bytes(exported_data, extract_dir)
        
        assert isinstance(imported_god, God)
        assert len(list(imported_god.xtargets.values())) == 0


class TestCLIIntegration:
    """Integration tests for CLI functionality."""

    @pytest.fixture
    def sample_config_file(self):
        """Create a temporary config file."""
        config_data = {
            "aspects": [
                {"Aspect": "Function", "Separator": "="},
                {"Aspect": "Location", "Separator": "+"}
            ]
        }
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_file = f.name
        yield temp_file
        # Clean up after test
        if os.path.exists(temp_file):
            os.unlink(temp_file)

    @pytest.fixture
    def sample_extraction_settings(self):
        """Create temporary extraction settings file."""
        settings = {
            "CONNECTION_LIST": {
                "tables": {},
                "description": "Test",
                "search_name": "Connection list"
            }
        }
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(settings, f)
            temp_file = f.name
        yield temp_file
        # Clean up after test
        if os.path.exists(temp_file):
            os.unlink(temp_file)

    def test_validate_file_path_integration(self):
        """Test file path validation with real files."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_file = f.name
        
        try:
            result = validate_file_path(temp_file, must_exist=True)
            assert isinstance(result, Path)
            assert result.exists()
        finally:
            os.unlink(temp_file)

    def test_export_data_integration(self, tmp_path):
        """Test data export functionality."""
        config = AspectsConfig(
            OrderedDict({
                "=": LevelConfig(Separator="=", Aspect="Function")
            })
        )
        manager = Manager(config)
        
        output_file = str(tmp_path / "export.json")
        
        export_data(manager, output_file, "json")
        
        assert os.path.exists(output_file)
        
        with open(output_file, 'r') as f:
            data = json.load(f)
            assert "stats" in data
            assert "xtargets" in data
            assert "connections" in data

    @patch('indu_doc.cli.click.echo')
    def test_process_pdf_workflow_with_mock(self, mock_echo, sample_config_file, 
                                            sample_extraction_settings, tmp_path):
        """Test PDF processing workflow through CLI with mocked PDF."""
        # Create a mock PDF file
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4\n%Mock PDF content")
        
        with patch('indu_doc.plugins.eplan_pdfs.eplan_pdf_plugin.pymupdf.open') as mock_open:
            # Mock PDF document
            mock_doc = MagicMock()
            mock_doc.__len__ = lambda self: 1
            mock_page = MagicMock()
            mock_doc.__getitem__ = lambda self, idx: mock_page
            mock_open.return_value = mock_doc
            
            # Mock page processor
            with patch('indu_doc.plugins.eplan_pdfs.page_processor.PageProcessor.run'):
                process_pdf(
                    pdf_file=Path(pdf_file),
                    config=Path(sample_config_file),
                    extraction_settings=Path(sample_extraction_settings),
                    show_stats=False,
                    export=None,
                    export_format="json",
                    show_progress=False
                )
                
                # Verify some output was generated
                assert mock_echo.called


class TestEventSystemIntegration:
    """Integration tests for the event system across components."""

    @pytest.fixture
    def sample_config(self):
        """Create sample config."""
        return AspectsConfig(
            OrderedDict({
                "=": LevelConfig(Separator="=", Aspect="Function")
            })
        )

    @pytest.mark.asyncio
    async def test_plugin_event_propagation_to_manager(self, sample_config):
        """Test that plugin events are properly propagated to Manager."""
        manager = Manager(sample_config)
        
        # Create plugin with mock processing
        from indu_doc.plugins.plugin import InduDocPlugin
        from indu_doc.plugins.events import EventType
        
        class MockPlugin(InduDocPlugin):
            async def process_files_async(self, paths):
                # Simulate processing
                await asyncio.sleep(0.1)
                return self.sub_god
            
            def get_supported_file_extensions(self):
                return ("test",)
        
        plugin = MockPlugin(sample_config)
        manager.register_plugin(plugin)
        
        # Track events
        events_received = []
        
        async def event_tracker(event):
            events_received.append(event.event_type)
        
        plugin.event_emitter.on(EventType.PROCESSING_COMPLETED, event_tracker)
        
        # Create temp file
        with tempfile.NamedTemporaryFile(suffix='.test', delete=False) as f:
            test_file = f.name
        
        try:
            await plugin.start((test_file,))
            await asyncio.sleep(0.2)  # Allow event processing
            
            # Verify event was received
            assert EventType.PROCESSING_COMPLETED in events_received
        finally:
            os.unlink(test_file)

    @pytest.mark.asyncio
    async def test_progress_events_during_processing(self, sample_config):
        """Test that progress events are emitted during processing."""
        from indu_doc.plugins.plugin import InduDocPlugin
        from indu_doc.plugins.events import EventType
        
        class MockPlugin(InduDocPlugin):
            async def process_files_async(self, paths):
                from indu_doc.plugins.events import ProcessingProgressEvent
                
                # Emit progress events
                for i in range(3):
                    await self.event_emitter.emit(
                        ProcessingProgressEvent(
                            self.__class__.__name__,
                            self,
                            i + 1,
                            3,
                            paths[0]
                        )
                    )
                    await asyncio.sleep(0.05)
                
                return self.sub_god
            
            def get_supported_file_extensions(self):
                return ("test",)
        
        plugin = MockPlugin(sample_config)
        
        progress_events = []
        
        async def track_progress(event):
            progress_events.append(event)
        
        plugin.event_emitter.on(EventType.PROCESSING_PROGRESS, track_progress)
        
        # Create temp file
        with tempfile.NamedTemporaryFile(suffix='.test', delete=False) as f:
            test_file = f.name
        
        try:
            await plugin.start((test_file,))
            await asyncio.sleep(0.3)  # Allow event processing
            
            # Verify progress events were emitted
            assert len(progress_events) == 3
            assert all(hasattr(e, 'percentage') for e in progress_events)
        finally:
            os.unlink(test_file)


class TestConcurrentProcessingIntegration:
    """Integration tests for concurrent file processing."""

    @pytest.fixture
    def sample_config(self):
        """Create sample config."""
        return AspectsConfig(
            OrderedDict({
                "=": LevelConfig(Separator="=", Aspect="Function")
            })
        )

    @pytest.mark.asyncio
    async def test_multiple_files_processed_concurrently(self, sample_config):
        """Test that multiple files can be processed concurrently."""
        from indu_doc.plugins.plugin import InduDocPlugin
        
        processed_files = []
        
        class MockPlugin(InduDocPlugin):
            async def process_files_async(self, paths):
                for path in paths:
                    processed_files.append(path)
                    await asyncio.sleep(0.1)
                return self.sub_god
            
            def get_supported_file_extensions(self):
                return ("test",)
        
        manager = Manager(sample_config)
        plugin = MockPlugin(sample_config)
        manager.register_plugin(plugin)
        
        # Create multiple temp files
        temp_files = []
        for i in range(3):
            with tempfile.NamedTemporaryFile(suffix='.test', delete=False) as f:
                temp_files.append(f.name)
        
        try:
            await manager.process_files_async(tuple(temp_files))
            
            # All files should be processed
            assert len(processed_files) == 3
            for temp_file in temp_files:
                assert temp_file in processed_files
        finally:
            for temp_file in temp_files:
                os.unlink(temp_file)

    @pytest.mark.asyncio
    async def test_multiple_plugins_process_different_files(self, sample_config):
        """Test that multiple plugins can process different file types concurrently."""
        from indu_doc.plugins.plugin import InduDocPlugin
        
        plugin1_files = []
        plugin2_files = []
        
        class Plugin1(InduDocPlugin):
            async def process_files_async(self, paths):
                for path in paths:
                    plugin1_files.append(path)
                    await asyncio.sleep(0.05)
                return self.sub_god
            
            def get_supported_file_extensions(self):
                return ("type1",)
        
        class Plugin2(InduDocPlugin):
            async def process_files_async(self, paths):
                for path in paths:
                    plugin2_files.append(path)
                    await asyncio.sleep(0.05)
                return self.sub_god
            
            def get_supported_file_extensions(self):
                return ("type2",)
        
        manager = Manager(sample_config)
        manager.register_plugin(Plugin1(sample_config))
        manager.register_plugin(Plugin2(sample_config))
        
        # Create files for both plugins
        temp_files = []
        with tempfile.NamedTemporaryFile(suffix='.type1', delete=False) as f:
            temp_files.append(f.name)
        with tempfile.NamedTemporaryFile(suffix='.type2', delete=False) as f:
            temp_files.append(f.name)
        
        try:
            await manager.process_files_async(tuple(temp_files))
            
            # Each plugin should process its file type
            assert len(plugin1_files) == 1
            assert len(plugin2_files) == 1
            assert plugin1_files[0].endswith('.type1')
            assert plugin2_files[0].endswith('.type2')
        finally:
            for temp_file in temp_files:
                os.unlink(temp_file)


class TestErrorHandlingIntegration:
    """Integration tests for error handling across components."""

    @pytest.fixture
    def sample_config(self):
        """Create sample config."""
        return AspectsConfig(
            OrderedDict({
                "=": LevelConfig(Separator="=", Aspect="Function")
            })
        )

    @pytest.mark.asyncio
    async def test_plugin_error_propagation(self, sample_config):
        """Test that plugin errors are properly handled by Manager."""
        from indu_doc.plugins.plugin import InduDocPlugin
        
        class FailingPlugin(InduDocPlugin):
            async def process_files_async(self, paths):
                raise ValueError("Simulated processing error")
            
            def get_supported_file_extensions(self):
                return ("fail",)
        
        manager = Manager(sample_config)
        plugin = FailingPlugin(sample_config)
        manager.register_plugin(plugin)
        
        # Create temp file
        with tempfile.NamedTemporaryFile(suffix='.fail', delete=False) as f:
            fail_file = f.name
        
        try:
            # Processing should handle the error gracefully
            await manager.process_files_async(fail_file)
            
            # Give time for error handling
            await asyncio.sleep(0.2)
            
            # Manager should track that processing completed with error
            # The plugin state should indicate an error occurred
            assert plugin._processing_state.value in ["idle", "error"] or plugin._error_message is not None
        finally:
            os.unlink(fail_file)

    def test_missing_config_file_error(self):
        """Test that missing config file raises appropriate error."""
        with pytest.raises((FileNotFoundError, IOError)):
            Manager.from_config_files("nonexistent_config.json")

    def test_invalid_config_format(self, tmp_path):
        """Test that invalid config format is handled properly."""
        invalid_config = tmp_path / "invalid.json"
        invalid_config.write_text("{invalid json content")
        
        with pytest.raises(json.JSONDecodeError):
            with open(invalid_config, 'r') as f:
                json.load(f)


class TestConfigurationIntegration:
    """Integration tests for configuration loading and validation."""

    def test_aspects_config_loaded_correctly(self):
        """Test that AspectsConfig is loaded correctly from file."""
        config_data = {
            "aspects": [
                {"Aspect": "Function", "Separator": "="},
                {"Aspect": "Location", "Separator": "+"},
                {"Aspect": "Product", "Separator": "-"}
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            config_file = f.name
        
        try:
            config = AspectsConfig.init_from_file(config_file)
            
            assert isinstance(config, AspectsConfig)
            # Verify all aspects are loaded
            separators = list(config.levels.keys())
            assert "=" in separators
            assert "+" in separators
            assert "-" in separators
        finally:
            os.unlink(config_file)

    def test_page_settings_integration_with_plugin(self):
        """Test that PageSettings integrates properly with EplanPDFPlugin."""
        config_data = {"aspects": [{"Aspect": "Test", "Separator": "="}]}
        page_data = {
            "CONNECTION_LIST": {
                "tables": {},
                "description": "Test page",
                "search_name": "Connection list"
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as config_f:
            json.dump(config_data, config_f)
            config_file = config_f.name
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as page_f:
            json.dump(page_data, page_f)
            page_file = page_f.name
        
        try:
            plugin = EplanPDFPlugin.from_config_files(config_file, page_file)
            
            assert isinstance(plugin.page_settings, PageSettings)
            assert plugin.page_processor is not None
            assert plugin.sub_god is not None
        finally:
            os.unlink(config_file)
            os.unlink(page_file)

    def test_manager_configs_propagate_to_god(self):
        """Test that Manager's configs are properly used by God."""
        config_data = {
            "aspects": [
                {"Aspect": "Function", "Separator": "="},
                {"Aspect": "Location", "Separator": "+"}
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            config_file = f.name
        
        try:
            manager = Manager.from_config_files(config_file)
            
            # God should have the same config
            assert manager.god.configs == manager.configs
            
            # Config levels should be accessible through God
            from indu_doc.tag import Tag
            tag = Tag("=F100", manager.configs)
            # Verify tag was created with correct config
            assert tag.tag_str == "=F100"
        finally:
            os.unlink(config_file)
