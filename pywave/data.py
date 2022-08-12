from typing import Union

"""
Holds the WaveData class, which contains
the audio bytes and corresponding metadata.

The metadata is stored in the WaveMetadata class.
"""


class WaveMetadata:
    """
    Stores data about the raw WAV audio data.
    """

    def __init__(
        self, sample_rate: Union[int, float], bit_depth: int, channels: int
    ) -> None:
        """
        'sample_rate' - number of audio samples per second (Hz);
        'bit_depth' - number of bits to store each sample;
        'channels' - number of audio inputs/outputs
        """

        self.sample_rate = sample_rate
        self.bit_depth = bit_depth
        self.channels = channels
    
    def get_bitrate(self):
        """
        Number of bits used per second of audio.
        Found by sample rate * bit depth * channel count
        """
        return self.sample_rate * self.bit_depth * self.channels



class WaveData:

    def __init__(self, data: bytes, metadata: WaveMetadata) -> None:
        self.data = data
        self.info = metadata