"""Tests for the exporter module."""

import pytest
from io import BytesIO, StringIO
from typing import OrderedDict
from indu_doc.exporters.exporter import InduDocExporter
from indu_doc.god import God
from indu_doc.configs import AspectsConfig, LevelConfig


class TestInduDocExporter:
    """Test the InduDocExporter abstract base class."""

    def test_export_data_not_implemented(self):
        """Test that export_data raises NotImplementedError."""
        config = AspectsConfig(
            OrderedDict({
                "=": LevelConfig(Separator="=", Aspect="Product"),
            })
        )
        god = God(config)

        with pytest.raises(NotImplementedError, match="Exporting data is not implemented"):
            InduDocExporter.export_data(god)

    def test_import_data_not_implemented(self):
        """Test that import_data raises NotImplementedError."""
        with pytest.raises(NotImplementedError, match="Importing data is not supported"):
            InduDocExporter.import_data()

    def test_concrete_exporter_can_override_export(self):
        """Test that a concrete exporter can override export_data."""

        class ConcreteExporter(InduDocExporter):
            @classmethod
            def export_data(cls, god: God) -> BytesIO | StringIO:
                return StringIO("exported data")

        config = AspectsConfig(
            OrderedDict({
                "=": LevelConfig(Separator="=", Aspect="Product"),
            })
        )
        god = God(config)
        result = ConcreteExporter.export_data(god)

        assert isinstance(result, StringIO)
        assert result.getvalue() == "exported data"

    def test_concrete_exporter_can_override_import(self):
        """Test that a concrete exporter can override import_data."""

        class ConcreteExporter(InduDocExporter):
            @classmethod
            def import_data(cls) -> God:
                config = AspectsConfig(
                    OrderedDict({
                        "=": LevelConfig(Separator="=", Aspect="Product"),
                    })
                )
                return God(config)

        result = ConcreteExporter.import_data()

        assert isinstance(result, God)

    def test_concrete_exporter_returns_bytesio(self):
        """Test that a concrete exporter can return BytesIO."""

        class ConcreteExporter(InduDocExporter):
            @classmethod
            def export_data(cls, god: God) -> BytesIO | StringIO:
                return BytesIO(b"binary data")

        config = AspectsConfig(
            OrderedDict({
                "=": LevelConfig(Separator="=", Aspect="Product"),
            })
        )
        god = God(config)
        result = ConcreteExporter.export_data(god)

        assert isinstance(result, BytesIO)
        assert result.getvalue() == b"binary data"
