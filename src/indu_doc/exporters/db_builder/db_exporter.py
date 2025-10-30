from io import BytesIO
import tempfile
import os
import time
from indu_doc.exporters.exporter import InduDocExporter
from indu_doc.god import God
from indu_doc.exporters.db_builder.db import load_from_db, save_to_db


class SQLITEDBExporter(InduDocExporter):

    @classmethod
    def export_data(cls, god: God) -> BytesIO:
        """
        Export the God instance to a SQLite database file returned as BytesIO.
        
        Args:
            god: The God instance to export
            
        Returns:
            BytesIO containing the SQLite database file
        """
        # Create a temporary file for the database
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.db', delete=False) as tmp_file:
            tmp_path = tmp_file.name
        
        try:
            # Save to the temporary database file
            save_to_db(god, tmp_path)
            
            # Small delay to ensure file handles are released on Windows
            time.sleep(0.1)
            
            # Read the database file into BytesIO
            with open(tmp_path, 'rb') as f:
                db_bytes = BytesIO(f.read())
            
            return db_bytes
        finally:
            # Clean up the temporary file with retry logic for Windows
            if os.path.exists(tmp_path):
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        os.unlink(tmp_path)
                        break
                    except PermissionError:
                        if attempt < max_retries - 1:
                            time.sleep(0.1)
                        else:
                            # If we still can't delete, log warning but don't fail
                            import logging
                            logging.warning(f"Could not delete temporary file {tmp_path}")

    
    @classmethod
    def import_data(cls) -> God:
        """
        Import method is not directly supported. Use import_from_bytes() instead.
        """
        raise NotImplementedError(
            "Use SQLITEDBExporter.import_from_bytes(db_data, extract_docs_to) instead."
        )
    
    @classmethod
    def import_from_bytes(cls, db_data: BytesIO, extract_docs_to: str) -> God:
        """
        Import a God instance from a SQLite database file.
        
        Args:
            db_data: BytesIO containing the SQLite database file
            extract_docs_to: Directory path where document blobs will be extracted
            
        Returns:
            A God instance reconstructed from the database
        """
        # Create a temporary file for the database
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.db', delete=False) as tmp_file:
            tmp_path = tmp_file.name
            tmp_file.write(db_data.read())
        
        try:
            # Load from the temporary database file
            god = load_from_db(tmp_path, extract_docs_to)
            return god
        finally:
            # Clean up the temporary file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    @classmethod
    def import_from_file(cls, db_file_path: str, extract_docs_to: str) -> God:
        """
        Import a God instance from a SQLite database file path.
        
        Args:
            db_file_path: Path to the SQLite database file
            extract_docs_to: Directory path where document blobs will be extracted
            
        Returns:
            A God instance reconstructed from the database
        """
        return load_from_db(db_file_path, extract_docs_to)

