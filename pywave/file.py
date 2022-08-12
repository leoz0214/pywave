import wave

import data

"""
This module allows WAV files to be read and saved.
"""



def read(file_location: str) -> data.WaveData:
    """
    Reads a WAV file from a given file location.

    Returns a WaveData object.
    """
    with wave.open(file_location, "rb") as f:
        frames = f.readframes(f.getnframes())

        sample_rate = f.getframerate()
        bit_depth = f.getsampwidth() * 8 # Bytes to bits.
        channels = f.getnchannels()

        metadata = data.WaveMetadata(sample_rate, bit_depth, channels)

        return data.WaveData(frames, metadata)


info = read("cna.wav")
print(info.info.get_bitrate())
    
