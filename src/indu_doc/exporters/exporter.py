"""
Base exporter interface for InduDoc data.

This module defines the abstract base class for all InduDoc exporters.
Exporters are responsible for converting God data structures into various
output formats and optionally importing data back into the system.
"""

from indu_doc.god import God
from io import BytesIO, StringIO
from abc import ABC, abstractmethod


class InduDocExporter(ABC):
    """Abstract base class for InduDoc data exporters.
    
    This class provides the interface that all exporters must implement
    to convert God data structures into various output formats.
    """
    
    @classmethod
    def export_data(cls, god: God) -> BytesIO | StringIO:
        """Export the God data into a specific format.
        
        :param god: The God instance containing all document data
        :type god: God
        :return: A BytesIO or StringIO stream containing the exported data
        :rtype: BytesIO | StringIO
        """
        raise NotImplementedError("Exporting data is not implemented.")

    @classmethod
    def import_data(cls) -> God:
        """Import data back into the system.
        
        Some exporters might support importing data back into the system.
        
        :return: God instance reconstructed from the imported data
        :rtype: God
        :note: You can add the imported god to the manager via manager.god += exported_god
        """
        raise NotImplementedError("Importing data is not supported by this exporter.")
