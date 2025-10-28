from indu_doc.god import God
from io import BytesIO, StringIO
from abc import ABC, abstractmethod

class InduDocExporter(ABC):
    @classmethod
    def export_data(cls, god: God) -> BytesIO | StringIO:
        """Export the God data into a specific format.
        
        :return: A BytesIO or StringIO stream containing the exported data.
        """
        raise NotImplementedError("Exporting data is not implemented.")

    @classmethod
    def import_data(cls) -> God:
        """
        Some Exporters might support importing data back into the system.
        
        :return: God instance reconstructed from the imported data.
        you can add that god to the manager via manager.god += exported_god
        
        """
        raise NotImplementedError("Importing data is not supported by this exporter.")
