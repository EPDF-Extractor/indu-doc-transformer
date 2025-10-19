from enum import Enum


class ProcessingState(Enum):
    IDLE = "idle"
    PROCESSING = "processing"
    STOPPING = "stopping"
    ERROR = "error"
