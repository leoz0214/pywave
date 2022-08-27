"""
This module allows WAV files to be read and saved - the skeleton
of the package.
"""
import os
import wave

from . import _data
from . import _utils


def read(file_location: str) -> _data.WaveData:
    """
    Reads a WAV file from a given file location.

    Returns a WaveData object.
    """
    if not os.path.isfile(file_location):
        raise FileNotFoundError(f"Not a file - '{file_location}'")

    with wave.open(file_location, "rb") as f:
        frame_count = f.getnframes()
        sample_rate = f.getframerate()
        bit_depth = f.getsampwidth() * 8 # Bytes to bits.
        channels = f.getnchannels()
        byte_count = frame_count * bit_depth // 8 * channels

        metadata = _data.WaveMetadata(sample_rate, bit_depth, channels)
        file = _utils.create_temp_file()

        count, remainder = divmod(frame_count, 100000)
        for _ in range(count):
            file.write(f.readframes(100000))
        file.write(f.readframes(remainder))

        return _data.WaveData(file, metadata, byte_count)


def write(
    wave_data: _data.WaveData, file_location: str,
    replace_existing_file: bool = True) -> None:
    """
    Writes WAV data to a given file.

    Warning: Existing file will be overwritten,
    unless specified otherwise.
    """
    if not isinstance(wave_data, _data.WaveData):
        raise TypeError("'wave_data' must be a WaveData object.")
    elif not replace_existing_file and os.path.isfile(file_location):
        raise FileExistsError(f"File already exists: '{file_location}'")

    with wave.open(file_location, "wb") as f:
        f.setframerate(wave_data.info.sample_rate)
        f.setsampwidth(wave_data.info.byte_depth)
        f.setnchannels(wave_data.info.channels)

        for chunk in wave_data.chunks(100000):
            f.writeframes(bytes(chunk))


# Aliases (convenience).
load = read
save = export = write