import math
import fractions
from typing import Union

import _utils

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
        self, sample_rate: Union[int, float], bit_depth: int, channels: int,
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
        Number of bits of data per second of audio.
        Found by sample rate * bit depth * channel count
        """
        return self.sample_rate * self.bit_depth * self.channels
    
    def get_bytes_per_frame(self) -> int:
        """
        Number of bytes for each channel to output one sample.
        """
        return self.bit_depth // 8 * self.channels

    def _get_duration(self, byte_count: int) -> float:
        # Seconds of audio.
        return byte_count / self.get_bytes_per_frame() / self.sample_rate


class WaveData:

    def __init__(self, data, metadata: WaveMetadata, byte_count: int) -> None:
        """
        NOT TO BE INITIALISED INTERNALLY.

        'data' - the bytes of the raw audio in a temporary file;
        'metadata' - information about the audio.
        A WaveMetadata object is passed in.
        """
        self.data = data
        self._byte_count = byte_count
        self.info = metadata

    def _frames(self) -> None:
        # Internal generator to get frames of audio.
        return self._chunks(self.info.get_bytes_per_frame())
    
    def _chunks(self, byte_count: int) -> None:
        # Internal generator to get audio in chunks.
        self.data.seek(0)
        chunk = self.data.read(byte_count)

        while chunk != b"":
            yield chunk
            chunk = self.data.read(byte_count)

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

        Changing sample rate is much faster.

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
            return WaveData(self.data, self.info, self._byte_count)
        elif multiplier <= 0:
            # Not possible.
            raise ValueError("Multiplier must be greater than 0.")

        if change_sample not in ("count", "rate"):
            # Invalid mode.
            raise ValueError(
                "change_sample must either be 'count' or 'rate'.")

        file = _utils.create_temp_file()
        
        if change_sample == "count":
            new = []
            sample_multiplier = round(1 / multiplier, 8)
            frame_count = 0

            decimal_part = round(sample_multiplier % 1, 8)
            if not decimal_part:
                sample_multiplier = int(sample_multiplier)

                for frame in self._frames():
                    new.extend(frame * sample_multiplier)
                    frame_count += sample_multiplier
                    
                    if len(new) > 100000:
                        file.write(bytes(new))
                        new.clear()
            else:
                # Any decimal parts are dealt with.
                # For example if the multiplier is set to 0.8,
                # The new sample count would be x1.25.
                # 1.25 = 1 1/4
                # So 1/4 of cycles will be doubled, whilst the
                # remaining 3/4 of cycles will stay as one.
                upper = math.ceil(sample_multiplier)
                lower = math.floor(sample_multiplier)

                fraction = fractions.Fraction(
                    decimal_part).limit_denominator(10 ** 8)
                numerator, denominator = fraction.as_integer_ratio()

                for i, frame in enumerate(self._frames()):
                    frames_to_add = (upper if (
                        (i * numerator) % (denominator) < numerator)
                        else lower)

                    new.extend(frame * frames_to_add)
                    frame_count += frames_to_add

                    if len(new) > 100000:
                        file.write(bytes(new))
                        new.clear()
            
            file.write(bytes(new))
            byte_count = frame_count * self.info.get_bytes_per_frame()
            print(byte_count)

            return WaveData(file, self.info, byte_count)
        
        new_sample_rate = self.info.sample_rate * multiplier
        new_metadata = WaveMetadata(
            new_sample_rate, self.info.bit_depth, self.info.channels)
        
        for chunk in self._chunks(100000):
            file.write(chunk)

        return WaveData(file, new_metadata, self._byte_count)
    
    def fit_time(
        self, seconds: Union[int, float], change_sample: str = "rate"
    ) -> "WaveData":
        """
        Changes audio duration to a certain number of seconds, by
        changing the speed of audio playback. For example, if a 50
        second audio file is converted into a 25 second audio file,
        the speed would double.

        The speed (and thus duration) can be changed either
        by changing the sample count, or the sample rate (default).

        Changing sample rate is much faster, but this is not necessary.

        If you are increasing duration, it is best to change by sample
        rate to avoid issues. But you can still keep the same sample
        rate and change the number of samples instead. But this could
        damage the audio playback.

        To change by sample count, pass in change_sample as 'count',
        and to change by sample rate, pass in change_sample as 'rate'.
        The default is to change by sample rate.

        A new WaveData object is returned with the duration changed
        successfully, and the audio fit to the time specified.
        """
        if seconds <= 0:
            raise ValueError("seconds must be greater than 0.")

        multiplier = round(self.get_duration() / seconds, 8)
        return self.change_speed_by_multiplier(multiplier, change_sample)
    
    def get_duration(self) -> float:
        """
        Number of seconds of audio.
        """
        return self.info._get_duration(self._byte_count)