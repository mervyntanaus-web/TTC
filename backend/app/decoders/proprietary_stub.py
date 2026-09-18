from pathlib import Path

from app.config import get_settings
from app.decoders.base import ProbeResult, UnsupportedFormatError, VideoDecoder

settings = get_settings()

# Documents what each vendor SDK would need to provide, for whoever wires up
# the real integration later.
VENDOR_SDK_NOTES = {
    "cme": (
        "March Networks Command exports .cme container files. Decoding requires "
        "the March Networks Command Enterprise SDK (or their `mnConvert` export "
        "utility) to remux/transcode to a standard container before TTC can "
        "probe or play it."
    ),
    "g64": (
        "Genetec Security Center exports .g64/.g64x archive files. Genetec "
        "provides the Genetec Video Export Player SDK / Security Center SDK "
        "(GenetecSC) with a G64 export API that can convert to a standard "
        "container; that SDK must be licensed and installed to decode these."
    ),
    "g64x": (
        "See g64 above — g64x is Genetec's encrypted/extended archive variant "
        "and additionally requires the originating Security Center's export "
        "key to decrypt before conversion."
    ),
}


class ProprietaryFormatStub(VideoDecoder):
    """Placeholder decoder for TTC's proprietary VMS export formats (CME,
    G64x). Ingestion still accepts and stores these files (so they aren't
    lost/blocked), tagging the Video as `needs_vendor_decoder` rather than
    failing the upload; playback/redaction is unavailable until a real
    vendor-SDK-backed decoder replaces this stub."""

    def can_handle(self, extension: str) -> bool:
        return extension.lower().lstrip(".") in settings.proprietary_formats

    def probe(self, source_path: Path) -> ProbeResult:
        raise UnsupportedFormatError(self._note(source_path.suffix))

    def transcode_to_mp4(self, source_path: Path, dest_path: Path) -> None:
        raise UnsupportedFormatError(self._note(source_path.suffix))

    @staticmethod
    def _note(extension: str) -> str:
        ext = extension.lower().lstrip(".")
        return VENDOR_SDK_NOTES.get(
            ext, f"No vendor SDK integrated yet for proprietary format '{ext}'."
        )
