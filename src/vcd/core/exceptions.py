# Custom Errors
class VCDError(Exception):
    """Base for all tool‑specific errors."""


class ToolNotFoundError(VCDError):
    """ffmpeg or ffprobe is missing."""


class AuthenticationError(VCDError):
    """Could not log in or session is invalid."""


class DownloadError(VCDError):
    """Download failed or archive is corrupt."""


class MediaProcessingError(VCDError):
    """Something went wrong while reading media / XML."""
