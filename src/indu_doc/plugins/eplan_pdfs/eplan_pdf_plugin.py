import asyncio
from typing import Any
from indu_doc.configs import AspectsConfig
from indu_doc.plugins.eplan_pdfs.page_settings import PageSettings
from indu_doc.plugins.eplan_pdfs.page_processor import PageProcessor
from indu_doc.plugins.plugin import InduDocPlugin
from indu_doc.plugins.events import ProcessingProgressEvent
import logging
import pymupdf  # type: ignore
logger = logging.getLogger(__name__)


class EplanPDFPlugin(InduDocPlugin):

    def __init__(self, configs: AspectsConfig, page_settings: PageSettings):
        super().__init__(configs)

        self.page_settings: PageSettings = page_settings
        self.page_processor: PageProcessor = PageProcessor(self.sub_god, self.page_settings)

    @classmethod
    def from_config_files(cls, config_path: str, page_setup_path: str) -> "EplanPDFPlugin":
        page_settings = PageSettings.init_from_file(page_setup_path)
        configs = AspectsConfig.init_from_file(config_path)
        return cls(configs, page_settings)

    async def process_files_async(self, paths: tuple[str, ...]) -> Any:
        """Async method to process PDF files and emit progress events."""
        if not isinstance(paths, tuple):
            paths = (paths,)

        docs = [pymupdf.open(p) for p in paths]

        # Calculate total pages
        total_pages = sum(len(doc) for doc in docs)
        current_page = 0

        # Update progress tracking
        self._total_pages = total_pages
        self._current_page = 0

        try:
            for doc, file_path in zip(docs, paths):
                logger.info(f"Processing file: {file_path}")
                self._current_file = file_path

                for page_idx in range(len(doc)):
                    page = doc[page_idx]
                    current_page += 1
                    self._current_page = current_page

                    # Emit progress event
                    await self.event_emitter.emit(
                        ProcessingProgressEvent(
                            self.__class__.__name__, self, current_page, total_pages, file_path
                        )
                    )

                    logger.info(f"Processing page {page_idx + 1}")
                    self.page_processor.run(page)

                    # Allow other tasks to run
                    await asyncio.sleep(0)

                doc.close()

            logger.info("PDF processing completed successfully")
            self._current_file = None
            return self.sub_god  # Return the extracted data

        except Exception as e:
            logger.error(f"Error during PDF processing: {str(e)}")
            self._error_message = str(e)
            raise
        finally:
            # Close any remaining documents
            for doc in docs:
                try:
                    doc.close()
                except Exception:
                    pass

    def get_supported_file_extensions(self) -> tuple[str]:
        """
        Get the list of supported file extensions for this plugin.

        :returns: List of supported file extensions (e.g., ['pdf', 'docx']).
        :rtype: list[str]
        """
        return ("pdf",)