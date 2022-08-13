import wave

import wavdata

"""
This module allows WAV files to be read and saved.
"""


def read(file_location: str) -> wavdata.WaveData:
    """
    Reads a WAV file from a given file location.
    Currently, only 8-bit and 16-bit WAV files are supported.

    Returns a WaveData object.
    """
    with wave.open(file_location, "rb") as f:
        frames = f.readframes(f.getnframes())
        sample_rate = f.getframerate()
        bit_depth = f.getsampwidth() * 8 # Bytes to bits.
        channels = f.getnchannels()

    metadata = wavdata.WaveMetadata(sample_rate, bit_depth, channels)

    return wavdata.WaveData(frames, metadata)


def write(wave_data: wavdata.WaveData, file_location: str) -> None:
    """
    Writes WAV data to a given file.

    Warning: Existing file will be overwritten.
    """
    with wave.open(file_location, "wb") as f:
        f.setframerate(wave_data.info.sample_rate)
        f.setsampwidth(wave_data.info.bit_depth // 8) # Bits to bytes.
        f.setnchannels(wave_data.info.channels)
        f.writeframes(wave_data.data)


save = write # Alias