import wave

import wavdata
import _utils

"""
This module allows WAV files to be read and saved.
"""


def read(file_location: str) -> wavdata.WaveData:
    """
    Reads a WAV file from a given file location.

    Returns a WaveData object.
    """
    with wave.open(file_location, "rb") as f:
        frame_count = f.getnframes()

        sample_rate = f.getframerate()
        bit_depth = f.getsampwidth() * 8 # Bytes to bits.
        channels = f.getnchannels()

        metadata = wavdata.WaveMetadata(sample_rate, bit_depth, channels)
        file = _utils.create_temp_file()

        count, remainder = divmod(frame_count, 100000)
        for i in range(count):
            file.write(f.readframes(100000))
        file.write(f.readframes(remainder))
        file.seek(0)

        return wavdata.WaveData(
            file, metadata, frame_count * bit_depth // 8 * channels)


def write(wave_data: wavdata.WaveData, file_location: str) -> None:
    """
    Writes WAV data to a given file.

    Warning: Existing file will be overwritten.
    """
    with wave.open(file_location, "wb") as f:
        f.setframerate(wave_data.info.sample_rate)
        f.setsampwidth(wave_data.info.bit_depth // 8) # Bits to bytes.
        f.setnchannels(wave_data.info.channels)

        for chunk in wave_data._chunks(100000):
            f.writeframes(bytes(chunk))


save = write # Alias