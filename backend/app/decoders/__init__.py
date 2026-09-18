from app.decoders.base import ProbeResult, UnsupportedFormatError, VideoDecoder
from app.decoders.ffmpeg_decoder import FfmpegDecoder
from app.decoders.proprietary_stub import ProprietaryFormatStub

_DECODERS: list[VideoDecoder] = [FfmpegDecoder(), ProprietaryFormatStub()]


def get_decoder(extension: str) -> VideoDecoder:
    for decoder in _DECODERS:
        if decoder.can_handle(extension):
            return decoder
    raise UnsupportedFormatError(f"No decoder registered for format '{extension}'.")


__all__ = ["VideoDecoder", "ProbeResult", "UnsupportedFormatError", "get_decoder"]
