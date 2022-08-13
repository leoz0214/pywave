import math
import fractions
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
    
    def get_bitrate(self) -> Union[int, float]:
        """
        Number of bits used per second of audio.
        Found by sample rate * bit depth * channel count
        """
        return self.sample_rate * self.bit_depth * self.channels


class WaveData:

    def __init__(self, data: bytes, metadata: WaveMetadata) -> None:
        """
        'data' - the bytes of the raw audio;
        'metadata' - information about the audio.
        A WaveMetadata object must be passed in.
        """
        self.data = data
        self.info = metadata

    def change_speed_by_multiplier(
        self, multiplier: Union[int, float],
        change_sample: str = "rate") -> "WaveData":
        """
        Changes playback speed of the audio by a given multiplier.
        For example, a multiplier of 2 would make the audio play
        twice as fast, whereas a multiplier of 0.25 would make the
        audio play four times slower.

        The speed can be changed either by changing the
        sample count, or the sample rate (default).

        Changing sample rate is much faster, but this is not necessary
        to change audio speed.

        If you are slowing down audio, it is best to change by sample
        rate to avoid issues. But you can still keep the same sample
        rate and change the number of samples instead. But this could
        damage the audio playback.

        To change by sample count, pass in change_sample as 'count',
        and to change by sample rate, pass in change_sample as 'rate'.
        The default is to change by sample rate.

        A new WaveData object is returned with the speed changed
        successfully.
        """
        if multiplier == 1:
            # No change.
            return WaveData(self.data, self.info)
        elif multiplier <= 0:
            raise ValueError("Multiplier must be greater than 0.")

        if change_sample not in ("count", "rate"):
            raise ValueError(
                "change_sample must either be 'count' or 'rate'.")
        
        if change_sample == "count":
            new_sample_count = round(1 / multiplier, 10)
            parts_size = self.info.bit_depth // 8 * self.info.channels

            upper = math.ceil(new_sample_count)
            lower = math.floor(new_sample_count)

            decimal_part = round(new_sample_count - int(new_sample_count), 10)
            if not decimal_part:
                numerator = int(new_sample_count)
                denominator = 1         
            else:
                fraction = fractions.Fraction(
                    decimal_part).limit_denominator(10 ** 10)
                numerator, denominator = fraction.as_integer_ratio()

            new = []
            for i in range(0, len(self.data), parts_size):
                new.extend(self.data[i:i+parts_size] * (
                    upper if (
                        (i * numerator) % (denominator * parts_size)
                        < numerator * parts_size
                    ) else lower))
            
            return WaveData(bytes(new), self.info)
        
        new_sample_rate = self.info.sample_rate * multiplier
        new_metadata = WaveMetadata(
            new_sample_rate, self.info.bit_depth, self.info.channels)

        return WaveData(self.data, new_metadata)

    def get_length(self) -> float:
        """
        Number of seconds of audio.
        """
        return (
            len(self.data)
            / (self.info.bit_depth // 8)
            / self.info.channels
            / self.info.sample_rate)