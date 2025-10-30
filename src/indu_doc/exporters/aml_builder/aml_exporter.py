from io import BytesIO
from indu_doc.exporters.aml_builder.aml_builder import AMLBuilder
from indu_doc.exporters.exporter import InduDocExporter
from indu_doc.god import God


class AMLExporter(InduDocExporter):

    @classmethod
    def export_data(cls, god: God) -> BytesIO:
        builder = AMLBuilder(god)
        builder.process()
        return builder.bytes_output()

    @classmethod
    def import_data(cls) -> God:
        raise NotImplementedError("Importing AML data is not supported.")