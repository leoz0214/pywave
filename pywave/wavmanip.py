"""
This module provides functions which allow for manipulation of WAV data.
"""
from typing import Iterable, Union

from . import _data
from . import _utils


def join(
    wav_objects: Iterable[_data.WaveData], sample_rate: int = 44100,
    bit_depth: int = 16, channels: int = 1,
    separator: Union[_data.WaveData, int, float, None] = None
) -> _data.WaveData:
    """
    Concatenates multiple WAV data objects into one object.

    Obviously, sample rate, bit depth, and number of channels must
    be constant for all WAV objects. They will all be converted
    beforehand as necessary.

    The WAV objects to join can each be separated by a WaveData object,
    a number representing silence, or nothing.

    Channels are used in order. So if a WAV object has 2 channels and
    joins into a WAV with only one channel, its first channel will be
    used as part of the big WAV.
    """
    new_wav_objects = []
    wav_count = len(wav_objects)

    silence_separate = isinstance(separator, (int, float))
    for i, wav in enumerate(wav_objects):
        wav = wav.change_sample_rate(sample_rate)
        wav = wav.change_bit_depth(bit_depth)
        wav = wav._change_channel_count(channels)

        # Not the last WAV object - possible silence to be added.
        if i != wav_count - 1 and silence_separate:
            wav = wav.append_silence(separator)

        new_wav_objects.append(wav)
    
    file = _utils.create_temp_file()
    new_byte_count = 0
    wav_separate = isinstance(separator, _data.WaveData)

    if wav_separate:
        separator = separator.change_sample_rate(sample_rate)
        separator = separator.change_bit_depth(bit_depth)
        separator = separator._change_channel_count(channels)

    for i, wav in enumerate(new_wav_objects):
        new_byte_count += wav._byte_count
        for chunk in wav.chunks(100000):
            file.write(chunk)
        
        # Not the last WAV object - possible WAV separator to be added.
        if i != wav_count - 1 and wav_separate:
            new_byte_count += separator._byte_count
            for chunk in separator.chunks(100000):
                file.write(chunk)
    
    new_metadata = _data.WaveMetadata(sample_rate, bit_depth, channels)
    return _data.WaveData(file, new_metadata, new_byte_count)