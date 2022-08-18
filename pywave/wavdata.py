"""
This module holds the WaveData class, which contains
the audio bytes and corresponding metadata.

The metadata is stored in the WaveMetadata class.
"""

import sys
import math
import fractions
import contextlib
from typing import Union, Literal

from . import _utils


class WaveMetadata:
    """
    Stores data about the raw WAV audio data.
    """

    def __init__(
        self, sample_rate: int, bit_depth: int, channels: int) -> None:
        """
        'sample_rate' - number of audio samples per second (Hz);
        'bit_depth' - number of bits to store each sample;
        'channels' - number of audio inputs/outputs
        """
        self.sample_rate = sample_rate
        self.bit_depth = bit_depth
        self.channels = channels
    
    @property
    def byte_depth(self) -> int:
        return self.bit_depth // 8
    
    def get_bitrate(self) -> int:
        """
        Number of bits of data per second of audio.
        Found by sample rate * bit depth * channel count
        """
        return self.sample_rate * self.bit_depth * self.channels
    
    def get_bytes_per_frame(self) -> int:
        """
        Number of bytes for each channel to output one sample.
        """
        return self.byte_depth * self.channels

    def _get_duration(self, byte_count: int) -> float:
        # Seconds of audio.
        return byte_count / self.get_bytes_per_frame() / self.sample_rate


class WaveData:

    def __init__(
        self, temp_file: _utils.tempfile._TemporaryFileWrapper,
        metadata: WaveMetadata, byte_count: int) -> None:
        """
        NOT TO BE INITIALISED EXTERNALLY.

        'data' - the bytes of the raw audio in a temporary file;
        'metadata' - information about the audio.
        A WaveMetadata object is passed in.
        """
        self._file = temp_file
        self._byte_count = byte_count
        self.info = metadata

        self._player = None
        self._playing = False
        self._pass_count = 0

    def _frames(self, reversed: bool = False) -> None:
        # Internal generator to get frames of audio.
        return self._chunks(self.info.get_bytes_per_frame(), reversed)
    
    def _samples(self, reversed: bool = False) -> None:
        # Internal generator to get audio samples.
        return self._chunks(self.info.byte_depth, reversed)
    
    def _chunks(self, byte_count: int, reversed: bool = False) -> None:
        # Internal generator to get audio in chunks.
        if reversed:
            # Cannot access first byte so must make modifications
            # to so. Therefore even if last chunk is full, it still
            # counts as the left.
            count, left = divmod(self._byte_count - 1, byte_count)
            left += 1

            if not count:
                self._file.seek(0)
                yield self._file.read(left)
                return

            self._file.seek(-byte_count, 2)
            chunk = self._file.read(byte_count)

            for _ in range(count):
                yield chunk

                self._file.seek(-byte_count * 2, 1)
                chunk = self._file.read(byte_count)

            self._file.seek(0)
            yield self._file.read(left)
        else:
            self._file.seek(0)
            chunk = self._file.read(byte_count)

            while chunk:
                yield chunk
                chunk = self._file.read(byte_count)
    
    def _copy(self) -> "WaveData":
        # Returns a copy of self.
        file = _utils.create_temp_file()
        for chunk in self._chunks(100000):
            file.write(chunk)
        return WaveData(file, self.info, self._byte_count)

    def change_speed(
        self, multiplier: Union[int, float],
        change_sample: Literal["rate", "count"] = "rate") -> "WaveData":
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
            return self._copy()
        elif multiplier < 0.01:
            # Processing takes way too long / not possible.
            raise ValueError("Multiplier must be at least 0.01")
        elif multiplier > 100:
            # Processing takes way too long.
            raise ValueError("Multiplier cannot be greater than 100")

        if change_sample not in ("count", "rate"):
            # Invalid mode.
            raise ValueError(
                "'change_sample' must either be 'count' or 'rate'.")

        file = _utils.create_temp_file()
        
        if change_sample == "count":
            sample_multiplier = round(1 / multiplier, 8)
            file, byte_count = _multiply_frames(self, sample_multiplier)        

            return WaveData(file, self.info, byte_count)
        
        new_sample_rate = round(self.info.sample_rate * multiplier)
        new_metadata = WaveMetadata(
            new_sample_rate, self.info.bit_depth, self.info.channels)
        
        for chunk in self._chunks(100000):
            file.write(chunk)

        return WaveData(file, new_metadata, self._byte_count)
    
    def fit_time(
        self, seconds: Union[int, float],
        change_sample: Literal["rate", "count"]) -> "WaveData":
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
            raise ValueError("'seconds' must be greater than 0.")

        multiplier = round(self.get_duration() / seconds, 8)
        return self.change_speed(multiplier, change_sample)
    
    def get_duration(self) -> float:
        """
        Number of seconds of audio.
        """
        return self.info._get_duration(self._byte_count)
    
    def change_sample_rate(
        self, value: Union[int, float] = 44100,
        mode: Literal["absolute", "multiplier"] = "absolute") -> "WaveData":
        """
        Changes the number of audio samples per second, without
        noticeably altering the speed of audio playback
        (at most, an extremely small change).

        'value' - the corresponding number to 'mode'.

        'mode' - how the sample rate is modified. It must be either
        the string 'absolute' or 'multiplier'. 'absolute' simply
        allows for the sample rate to be changed to a particular
        value in Hz. 'multiplier' changes the sample rate by
        multiplying the current sample rate to form a new sample rate.

        The default arguments are 44100 for 'value' (44.1 kHz is a
        commonly used sample rate), and 'absolute' for mode.

        Note: A higher sample rate provides better audio quality, up
        to a point when further increases in sample rate result in
        no noticeable difference. However, a low sample rate results
        in poor audio quality.
        """
        if mode == "absolute":
            new_sample_rate = value
        elif mode == "multiplier":
            if value <= 0:
                raise ValueError("'multiplier' must be a whole number")
            new_sample_rate = self.info.sample_rate * value
        else:
            raise ValueError(
                "'mode' must either be 'absolute' or 'multiplier'")

        new_sample_rate = round(new_sample_rate)
        
        if new_sample_rate < 1:
            raise ValueError("New sample rate too low")
        elif new_sample_rate == self.info.sample_rate:
            # No change.
            return self._copy()
        
        multiplier = (
            value if mode == "multiplier"
            else new_sample_rate / self.info.sample_rate)
        
        file, byte_count = _multiply_frames(self, multiplier)

        new_metadata = WaveMetadata(
            new_sample_rate, self.info.bit_depth, self.info.channels)
        
        return WaveData(file, new_metadata, byte_count)
    
    def change_bit_depth(self, new_bit_depth: int) -> "WaveData":
        """
        Changes the number of bits used to store each sample.

        Reducing bit depth reduces file size but also quality.

        Bit depth must either be 8, 16, 24 or 32 bits.
        """
        if new_bit_depth not in (8, 16, 24, 32):
            raise ValueError(
                "New bit depth must be either 8, 16, 24 or 32 bits.")
        
        # In case of valid float / numeric type input.
        new_bit_depth = int(new_bit_depth)

        if new_bit_depth == self.info.bit_depth:
            # No change
            return self._copy()

        bytes_per_new_frame = new_bit_depth // 8
        multiplier = 2 ** (new_bit_depth - self.info.bit_depth)

        from_8_bits = self.info.bit_depth == 8
        to_8_bits = new_bit_depth == 8

        file = _utils.create_temp_file()
        new = []

        for sample in self._samples():
            # 8 bit must be signed, otherwise unsigned.
            # From 8 bit: signed -> unsigned
            # To 8 bit: unsigned -> signed
            int_value = int.from_bytes(
                sample, sys.byteorder, signed=from_8_bits)
        
            new_int_value = (
                int((int_value + 128) * multiplier) if from_8_bits
                else int(int_value * multiplier) - 128 if to_8_bits
                else int(int_value * multiplier))

            new_frame = new_int_value.to_bytes(
                bytes_per_new_frame, sys.byteorder, signed=to_8_bits)
            new.extend(new_frame)

            if len(new) > 100000:
                file.write(bytes(new))
                new.clear()
        
        file.write(bytes(new))
        
        new_metadata = WaveMetadata(
            self.info.sample_rate, new_bit_depth, self.info.channels)

        byte_count = round(
            self._byte_count * (new_bit_depth / self.info.bit_depth))
        
        return WaveData(file, new_metadata, byte_count)
    
    def to_mono(self, channel_number: int = 1) -> "WaveData":
        """
        Converts audio into mono, by changing to only one
        channel of audio.

        To select the channel of audio to be used, pass in its
        number. For the 1st channel, pass in 1; for the 8th channel
        (if there is one), pass in 8. By default, the 1st channel
        is used.

        Warning: once audio is converted to mono, it obviously cannot
        be converted back to its original channels.
        """
        if channel_number < 1:
            raise ValueError("Channel number must be at least 1.")
        elif channel_number > self.info.channels:
            raise ValueError(
                "Channel {} does not exist, there are only {} channels.".
                format(channel_number, self.info.channels))
        
        # In case of valid float / numeric type input.
        channel_number = int(channel_number)
        
        if self.info.channels == 1:
            # Already mono
            return self._copy()

        file = _utils.create_temp_file()
        new = []

        start_index = (channel_number - 1) * self.info.byte_depth
        stop_index = start_index + self.info.byte_depth

        for frame in self._frames():
            new.extend(frame[start_index:stop_index])

            if len(new) > 100000:
                file.write(bytes(new))
                new.clear()
        
        file.write(bytes(new))

        new_metadata = WaveMetadata(
            self.info.sample_rate, self.info.bit_depth, 1)
        
        byte_count = round(self._byte_count / self.info.channels)

        return WaveData(file, new_metadata, byte_count)
    
    def decrease_volume(
        self, value: Union[int, float],
        mode: Literal["multiplier", "decibels"] = "multiplier") -> "WaveData":
        """
        Makes the audio quieter by reducing its amplitude.

        'value' - the corresponding number to the mode.

        'mode' - either the string 'multiplier' or 'decibels'.
        'multiplier' just changes multiplies the audio amplitude
        to decrease it. It must be greater than 0 and less than 1.
        'decibels' indicates how many decibels (dB) to decrease the
        audio volume by. Decibels are a logarithmic scale of how loud
        sound is (log 10). Therefore, decreasing decibels by 10 would
        make the audio 10 times quieter. And decreasing decibels by 3
        would make the audio about 2 times quieter.

        The default mode is 'multiplier'.

        Warning: reducing volume drastically will make 8 bit audio
        quality way worse. 16 bit audio and greater will not
        face the same issues, however.
        """
        if mode == "multiplier":
            if not 0 < value < 1:
                raise ValueError(
                    "Multiplier must be greater than 0 and less than 1.")
            multiplier = value
        elif mode == "decibels":
            if value <= 0:
                raise ValueError(
                    "Decibels decrease must be greater than 0. "
                    "If you are trying to decrease by a negative number, "
                    "use a positive number instead.")
            multiplier = 1 / (10 ** (value / 10))
        else:
            raise ValueError(
                "'mode' must be either 'multiplier' or 'decibels'")
        
        file = _utils.create_temp_file()
        new = []

        # Only 8 bit WAVs are unsigned.
        signed = self.info.bit_depth != 8

        for sample in self._samples():
            current_value = int.from_bytes(
                sample, sys.byteorder, signed=signed)
            
            new_value = int(current_value * multiplier)
            new_bytes = new_value.to_bytes(
                self.info.byte_depth, sys.byteorder, signed=signed)

            new.extend(new_bytes)

            if len(new) > 100000:
                file.write(bytes(new))
                new.clear()
        
        file.write(bytes(new))
        
        return WaveData(file, self.info, self._byte_count)
    
    def reverse(self):
        """
        Reverses the audio data, for whatever reason.
        """
        file = _utils.create_temp_file()

        for frame in self._frames(reversed=True):
            file.write(frame)
                   
        return WaveData(file, self.info, self._byte_count)


def _multiply_frames(
        wave_data: WaveData, multiplier: Union[int, float]
    ) -> tuple[_utils.tempfile._TemporaryFileWrapper, int]:
        # Multiplies the number of frames of audio.
        file = _utils.create_temp_file()
        new = []
        frame_count = 0

        decimal_part = round(multiplier % 1, 10)
        if not decimal_part:
            multiplier = int(multiplier)

            for frame in wave_data._frames():
                new.extend(frame * multiplier)
                frame_count += multiplier

                if len(new) > 100000:
                    file.write(bytes(new))
                    new.clear()
        else:
            upper = math.ceil(multiplier)
            lower = math.floor(multiplier)

            fraction = fractions.Fraction(
                decimal_part).limit_denominator(10 ** 10)
            numerator, denominator = fraction.as_integer_ratio()

            for i, frame in enumerate(wave_data._frames()):
                frames_to_add = (upper if
                    (i * numerator) % denominator < numerator
                    else lower)
                
                new.extend(frame * frames_to_add)
                frame_count += frames_to_add

                if len(new) > 100000:
                    file.write(bytes(new))
                    new.clear()

        file.write(bytes(new))
        byte_count = frame_count * wave_data.info.get_bytes_per_frame()

        return file, byte_count    