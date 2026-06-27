from dataclasses import dataclass, field


@dataclass
class RenderConfig:
    canvas_w: int = 1280
    canvas_h: int = 720
    fps: int = 30
    crf: int = 30
    video_preset: str = "veryfast"
    audio_bitrate: str = "92k"
    padding_ms: int = 2000
    gpu: str = "cpu"  # "cpu" | "nvidia" | "amd" | "intel"


@dataclass
class DownloadConfig:
    verify_ssl: bool = True
    chunk_size: int = 2 * 1024 * 1024
    timeout: int = 60
    headers: dict = field(
        default_factory=lambda: {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "fa,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
    )
