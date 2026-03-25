class DroneFrameExtractorError(Exception):
    """Base error for the application."""


class ToolMissingError(DroneFrameExtractorError):
    """Raised when an external dependency is missing."""


class VideoInspectionError(DroneFrameExtractorError):
    """Raised when a video cannot be inspected."""


class FrameExtractionError(DroneFrameExtractorError):
    """Raised when a frame cannot be exported."""


class GpxError(DroneFrameExtractorError):
    """Raised for GPX loading or timing errors."""


class SyncConfigurationError(DroneFrameExtractorError):
    """Raised when sync options are incomplete or contradictory."""
