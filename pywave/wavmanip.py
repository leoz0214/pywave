"""
This module provides functions which allow for manipulation of WAV data.
"""
from typing import Iterable

from . import wavdata
from . import _utils


def join(
    wav_objects: Iterable[wavdata.WaveData], sample_rate: int = 44100,
    bit_depth: int = 16, channels: int = 1) -> wavdata.WaveData:
    """
    Concatenates multiple WAV data objects into one object.

    Obviously, sample rate, bit depth, and number of channels must
    be constant for all WAV objects. They will all be converted
    beforehand as necessary.

    Channels are used in order. So if a WAV object has 2 channels and
    joins into a WAV with only one channel, its first channel will be
    used as part of the big WAV.
    """
    new_wav_objects = []
    for wav in wav_objects:
        wav = wav.change_sample_rate(sample_rate)
        wav = wav.change_bit_depth(bit_depth)
        wav = wav._change_channel_count(channels)

        new_wav_objects.append(wav)
    
    file = _utils.create_temp_file()
    new_byte_count = 0

    for wav in new_wav_objects:
        new_byte_count += wav._byte_count
        for chunk in wav._chunks(100000):
            file.write(chunk)
    
    new_metadata = wavdata.WaveMetadata(sample_rate, bit_depth, channels)
    return wavdata.WaveData(file, new_metadata, new_byte_count)