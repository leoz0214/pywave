"""
This module holds the WaveData class, which contains
the audio bytes and corresponding metadata.

The metadata is stored in the WaveMetadata class.
"""
import fractions
import itertools
import math
import sys
from typing import Union, Literal

from . import _utils


class WaveMetadata:
    # Stores data about the raw WAV audio data

    def __init__(
        self, sample_rate: int, bit_depth: int, channels: int) -> None:

        self._sample_rate = sample_rate
        self._bit_depth = bit_depth
        self._channels = channels
    
    @property
    def sample_rate(self) -> int:
        return self._sample_rate
    
    @property
    def bit_depth(self) -> int:
        return self._bit_depth
    
    @property
    def channels(self) -> int:
        return self._channels
    
    @property
    def byte_depth(self) -> int:
        return self.bit_depth // 8
    
    @property
    def bitrate(self) -> int:
        # Number of bits per second of audio.
        return self._sample_rate * self._bit_depth * self._channels
    
    def get_bytes_per_frame(self) -> int:
        """
        Number of bytes for each channel to output one sample.
        """
        return self.byte_depth * self._channels

    def _get_duration(self, byte_count: int) -> float:
        # Seconds of audio.
        return byte_count / self.get_bytes_per_frame() / self.sample_rate


class WaveData:

    def __init__(
        self, temp_file: _utils.tempfile._TemporaryFileWrapper,
        metadata: WaveMetadata, byte_count: int) -> None:

        self._file = temp_file
        self._byte_count = byte_count
        self.info = metadata
    
    @property
    def size(self) -> int:
        return self._byte_count

    def frames(
        self, first: int = 1, last: Union[int, None] = None,
        reversed: bool = False) -> None:
        """
        A generator which yields frames of audio as bytes.
        """
        bytes_per_frame = self.info.get_bytes_per_frame()
        first = (first - 1) * bytes_per_frame + 1
        last = last * bytes_per_frame if last is not None else None
        return self.chunks(bytes_per_frame, first, last, reversed)

    def samples(
        self, first: int = 1, last: Union[int, None] = None,
        reversed: bool = False) -> None:
        """
        A generator which yields samples of audio as bytes.
        """
        byte_depth = self.info.byte_depth
        first = (first - 1) * byte_depth + 1
        last = last * byte_depth if last is not None else None
        return self.chunks(byte_depth, first, last, reversed)
    
    def chunks(self, byte_count: int, first: int = 1,
        last: Union[int, None] = None, reversed: bool = False) -> None:
        """
        A generator which yields audio bytes in chunks.
        """
        if reversed:
            if last is None:
                last = self._byte_count

            count, left = divmod(last - first, byte_count)
            # Cannot file seek a negative number from the start.
            left += 1

            if not count:
                self._file.seek(first - 1)
                yield self._file.read(left)
                return

            self._file.seek(last - byte_count)
            chunk = self._file.read(byte_count)
            yield chunk

            count -= 1
            for _ in range(count):
                self._file.seek(-byte_count * 2, 1)
                chunk = self._file.read(byte_count)
                yield chunk

            self._file.seek(first - 1)
            yield self._file.read(left)
        else:
            self._file.seek(first - 1)

            if last is None:
                chunk = self._file.read(byte_count)
                while chunk:
                    yield chunk
                    chunk = self._file.read(byte_count)
            else:
                count, left = divmod(last - first, byte_count)
                left += 1

                for _ in range(count):
                    yield self._file.read(byte_count)
                yield self._file.read(left)
    
    def copy(self) -> "WaveData":
        """
        Returns a copy of the audio data.
        """
        file = _utils.create_temp_file()
        for chunk in self.chunks(100000):
            file.write(chunk)
        return WaveData(file, self.info, self._byte_count)
    
    def _change_channel_count(self, count: int) -> "WaveData":
        # Changes number of audio channels (internal use only).
        if count == self.info.channels:
            return self.copy()

        channels = self.info.channels
        byte_depth = self.info.byte_depth

        file = _utils.create_temp_file()
        new = []

        # Which channels to get data from each frame.
        # Example 2 -> 3 channels; [0, 1, 0]
        # Example 5 -> 3 channels; [0, 1, 2]
        channel_sequence = [
            n for _, n in
            zip(range(count), itertools.cycle(range(channels)))]
        
        for frame in self.frames():
            for n in channel_sequence:
                new.extend(frame[n * byte_depth:(n + 1) * byte_depth])
            _check_write_new_to_file(file, new)
        
        file.write(bytes(new))
        new_metadata = WaveMetadata(
            self.info.sample_rate, self.info.bit_depth, count)
        new_byte_count = round(self._byte_count * (count / channels))

        return WaveData(file, new_metadata, new_byte_count)

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

        Changing sample rate is much faster (in terms of processing).

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
            return self.copy()
        elif multiplier < 0.01:
            # Processing takes way too long / not possible.
            raise ValueError("Multiplier must be at least 0.01")
        elif multiplier > 100:
            # Processing takes way too long.
            raise ValueError("Multiplier cannot be greater than 100")
        elif change_sample not in ("count", "rate"):
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
        
        for chunk in self.chunks(100000):
            file.write(chunk)

        return WaveData(file, new_metadata, self._byte_count)
    
    def fit_time(
        self, seconds: Union[int, float],
        change_sample: Literal["rate", "count"] = "rate") -> "WaveData":
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
                raise ValueError("'multiplier' must be greater than 0")
            new_sample_rate = self.info.sample_rate * value
        else:
            raise ValueError(
                "'mode' must either be 'absolute' or 'multiplier'")

        new_sample_rate = round(new_sample_rate)
        
        if new_sample_rate < 1:
            raise ValueError("New sample rate too low")
        elif new_sample_rate == self.info.sample_rate:
            return self.copy()
        
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
            return self.copy()

        bytes_per_new_frame = new_bit_depth // 8
        multiplier = 2 ** (new_bit_depth - self.info.bit_depth)

        from_8_bits = self.info.bit_depth == 8
        to_8_bits = new_bit_depth == 8

        file = _utils.create_temp_file()
        new = []

        for sample in self.samples():
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

            _check_write_new_to_file(file, new)
        
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
            return self.copy()

        file = _utils.create_temp_file()
        new = []

        start_index = (channel_number - 1) * self.info.byte_depth
        stop_index = start_index + self.info.byte_depth

        for frame in self.frames():
            new.extend(frame[start_index:stop_index])
            _check_write_new_to_file(file, new)
        
        file.write(bytes(new))

        new_metadata = WaveMetadata(
            self.info.sample_rate, self.info.bit_depth, 1)
        byte_count = self._byte_count // self.info.channels

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
        a sound is (log 10). Therefore, decreasing decibels by 10 would
        make the audio 10 times quieter. And decreasing decibels by 3
        would make the audio about twice as quiet.

        The default mode is 'multiplier'.

        Warning: reducing volume drastically will make 8 bit audio
        quality way worse. 16 bit audio and greater will not
        face this issue to the same extent, however.
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

        for sample in self.samples():
            current_value = int.from_bytes(
                sample, sys.byteorder, signed=signed)
            
            new_value = int(current_value * multiplier)
            new_bytes = new_value.to_bytes(
                self.info.byte_depth, sys.byteorder, signed=signed)

            new.extend(new_bytes)
            _check_write_new_to_file(file, new)
        
        file.write(bytes(new))
        return WaveData(file, self.info, self._byte_count)
    
    def reverse(self) -> "WaveData":
        """
        Reverses the audio data, for whatever reason.
        """
        file = _utils.create_temp_file()
        for frame in self.frames(reversed=True):
            file.write(frame)
        return WaveData(file, self.info, self._byte_count)

    def crop(
        self, seconds_start: Union[int, float, None] = None,
        seconds_stop: Union[int, float, None] = None) -> "WaveData":
        """
        Crops the WAV data, returning audio from a given time interval.

        'seconds_start' - seconds to begin at (from start if None)
        
        'seconds_end' - seconds to end at (from end if None)

        Note: only one of either start or stop can be None, at least
        one of them has to be an actual number.
        """
        duration = self.get_duration()

        if seconds_start is None and seconds_stop is None:
            raise TypeError(
                "A number was expected from either "
                "'seconds_start' or 'seconds_stop'.")
        elif seconds_start is None:
            seconds_start = 0
        elif seconds_stop is None:
            seconds_stop = duration

        if seconds_start >= seconds_stop:
            raise ValueError(
                "'seconds_start' must be less than 'seconds_stop'.")
        elif seconds_start >= duration:
            raise ValueError("'seconds_start' must be less than duration.")
        elif seconds_stop > duration:
            raise ValueError(
                "'seconds_stop' must not be greater than duration.")
        elif seconds_start < 0:
            raise ValueError("'seconds_start' must not be negative.")

        first = (
            1 if seconds_start == 0
            else int(self.info.sample_rate * seconds_start))
        
        last = (
            None if seconds_stop == duration
            else int(self.info.sample_rate * seconds_stop))
        
        file = _utils.create_temp_file()
        new = []

        for frame in self.frames(first, last):
            new.extend(frame)
            _check_write_new_to_file(file, new) 
        file.write(bytes(new))

        bytes_per_frame = self.info.get_bytes_per_frame()
        if last is not None:
            new_byte_count = (last - first + 1) * bytes_per_frame
        else:
            new_byte_count = (
                self._byte_count // bytes_per_frame - first + 1
                * bytes_per_frame)

        return WaveData(file, self.info, new_byte_count)
    
    def prepend_silence(self, seconds: Union[int, float]) -> "WaveData":
        """
        Adds silence to the start of the audio.
        """
        return self.insert_silence(0, seconds)
    
    def append_silence(self, seconds: Union[int, float]) -> "WaveData":
        """
        Adds silence to the end of the audio.
        """
        return self.insert_silence(self.get_duration(), seconds)

    def insert_silence(
        self, timestamp: Union[int, float],
        seconds: Union[int, float]) -> "WaveData":
        """
        Adds silence to the audio at a certain time.

        'timestamp' - the time at which to insert the silence (seconds)

        'seconds' - number of seconds of silence
        """
        duration = self.get_duration()
        bytes_per_frame = self.info.get_bytes_per_frame()
        frame_count = self._byte_count // bytes_per_frame

        if timestamp < 0:
            raise ValueError("'timestamp' must be greater than or equal to 0")
        elif timestamp > duration:
            raise ValueError("'timestamp' must not be greater than duration")
        elif seconds <= 0:
            raise ValueError("'seconds' must be greater than 0")
        
        frames_before = int(self.info.sample_rate * timestamp)
        frames_of_silence = int(self.info.sample_rate * seconds)
        frames_after = int(self.info.sample_rate * (duration - timestamp))

        file = _utils.create_temp_file()
        new = []

        for frame in self.frames(last=frames_before + 1):
            new.extend(frame)
            _check_write_new_to_file(file, new)

        for _ in range(frames_of_silence):
            new.extend([0] * bytes_per_frame)
            _check_write_new_to_file(file, new)
        
        for frame in self.frames(first=frame_count - frames_after + 1):
            new.extend(frame)
            _check_write_new_to_file(file, new)
            
        file.write(bytes(new))
        new_byte_count = (
            self._byte_count + frames_of_silence * bytes_per_frame)
        
        return WaveData(file, self.info, new_byte_count)
    
    def repeat(self, count: int = 1) -> "WaveData":
        """
        Repeats the audio data a given number of times.

        For example, to make audio play twice in one file,
        repeat once. This is the default.
        """
        if count < 0:
            raise ValueError("'count' must be at least 0.")

        file = _utils.create_temp_file()
        for _ in range(count + 1):
            for chunk in self.chunks(100000):
                file.write(chunk)
        
        return WaveData(file, self.info, self._byte_count * (count + 1))

    def __mul__(self, n: int) -> "WaveData":
        # Multiplies audio (repeats n-1 times)
        if not isinstance(n, int):
            raise TypeError("Can only multiply WaveData by an integer.")
        elif n < 1:
            raise ValueError(
                "Can only multiply WaveData by a positive integer.")
        
        return self.repeat(n - 1)
    
    def __add__(self, wav: "WaveData") -> "WaveData":
        # Concatenates WAV data (uses this WAV's metadata however).
        if not isinstance(wav, WaveData):
            raise TypeError("Can only concatenate WaveData to WaveData.")
        
        # To prevent circular import at the top.
        from .wavmanip import join
        return join(
            (self, wav), self.info.sample_rate,
            self.info.bit_depth, self.info.channels)
    
    def split(
        self, value: Union[int, float],
        mode: Literal["time", "count"] = "time") -> list["WaveData"]:
        """
        Splits audio into several WaveData objects, either by time or
        count.

        For 'time', the duration of each part is in seconds,
        and the last WaveData object should be the shortest.
        But for 'count' the length of the WaveData objects are made as
        uniform as possible. Be sensible and limit the number of parts
        to about 100 if possible.

        Returns a list of WaveData objects.
        """
        bytes_per_frame = self.info.get_bytes_per_frame()
        frame_count = self._byte_count // bytes_per_frame
        parts = []

        if mode == "time":
            if value <= 0:
                raise ValueError(
                    "'value' must be greater than 0 for mode 'time'.")
            elif value == self.get_duration():
                return [self.copy()]

            frames_per_part = int(self.info.sample_rate * value)
            file = _utils.create_temp_file()
            remaining = frames_per_part

            for frame in self.frames():
                file.write(frame)
                remaining -= 1

                if not remaining:
                    byte_count = frames_per_part * bytes_per_frame
                    parts.append(WaveData(file, self.info, byte_count))
                    file = _utils.create_temp_file()
                    remaining = frames_per_part
            
            # Leftover
            if remaining < frames_per_part:
                byte_count = (frames_per_part - remaining) * bytes_per_frame
                parts.append(WaveData(file, self.info, byte_count))
            
            return parts

        elif mode == "count":
            if not isinstance(value, int):
                raise TypeError(
                    "'value' must be an integer for mode 'count'.")
            if value < 1:
                raise ValueError(
                    "'value' must be at least 1 for mode 'count'.")
            elif value == 1:
                return [self.copy()]

            base, one_more = divmod(frame_count, value)

            file = _utils.create_temp_file()
            remaining = base
            still_one_more = bool(one_more)
            if still_one_more:
                remaining += 1
                one_more -= 1
            
            for frame in self.frames():
                file.write(frame)
                remaining -= 1

                if not remaining:
                    byte_count = (base + still_one_more) * bytes_per_frame
                    parts.append(WaveData(file, self.info, byte_count))

                    file = _utils.create_temp_file()
                    remaining = base
                    still_one_more = bool(one_more)
                    if still_one_more:
                        remaining += 1
                        one_more -= 1
            
            return parts

        raise ValueError("'mode' must either be 'time' or 'count'.")
    
    def accelerate(
        self, start_speed: Union[int, float], stop_speed: Union[int, float],
        parts_count: int = 1000) -> "WaveData":
        """
        Uniformly increases speed of audio, from a start speed to a
        higher final speed.

        The more parts, the smoother the acceleration is.
        However, the maximum number of parts is 1000.
        """
        if start_speed >= stop_speed:
            raise ValueError("'start_speed' must be less than 'stop_speed'")
        elif start_speed <= 0:
            raise ValueError("'start_speed' must be greater than 0")
        elif parts_count < 2:
            raise ValueError("'parts_count' must be at least 2")
        elif parts_count > 1000:
            raise ValueError("'parts_count' must be less than 1000")
        
        return _change_speed(self, start_speed, stop_speed, parts_count)
    
    def decelerate(
        self, start_speed: Union[int, float], stop_speed: Union[int, float],
        parts_count: int = 1000) -> "WaveData":
        """
        Uniformly decreases speed of audio, from a start speed to a
        lower final speed.

        The more parts, the smoother the deceleration is.
        However, the maximum number of parts is 1000.
        """
        if start_speed <= stop_speed:
            raise ValueError(
                "'start_speed' must be greater than 'stop_speed'")
        elif stop_speed <= 0:
            raise ValueError("'stop_speed' must be greater than 0")
        elif parts_count < 2:
            raise ValueError("'parts_count' must be at least 2")
        elif parts_count > 1000:
            raise ValueError("'parts_count' must be less than 1000")
        
        return _change_speed(self, start_speed, stop_speed, parts_count)


def _change_speed(
    wav: WaveData, start_speed: Union[int, float],
    stop_speed: Union[int, float], parts_count: int) -> WaveData:
    # Accelerates/decelearates audio speed.
    current_speed = start_speed
    rate_of_change = (stop_speed - start_speed) / (parts_count - 1)

    parts = wav.split(parts_count, "count")
    new = []
    for part in parts:
        new.append(part.change_speed(current_speed, "count"))
        current_speed += rate_of_change

    # To prevent circular import at the top.
    from .wavmanip import join
    return join(
        new, wav.info.sample_rate,
        wav.info.bit_depth, wav.info.channels)


def _check_write_new_to_file(
    file: _utils.tempfile._TemporaryFileWrapper, new: list[int],
    n: int = 100000) -> None:
    # Writes new bytes to temp file if long enough (memory efficiency).
    if len(new) > n:
        file.write(bytes(new))
        new.clear()


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

            for frame in wave_data.frames():
                new.extend(frame * multiplier)
                frame_count += multiplier

                _check_write_new_to_file(file, new)       
        else:
            upper = math.ceil(multiplier)
            lower = math.floor(multiplier)

            fraction = fractions.Fraction(
                decimal_part).limit_denominator(10 ** 10)
            numerator, denominator = fraction.as_integer_ratio()

            for i, frame in enumerate(wave_data.frames()):
                frames_to_add = (upper if
                    (i * numerator) % denominator < numerator else lower)
                
                new.extend(frame * frames_to_add)
                frame_count += frames_to_add

                _check_write_new_to_file(file, new)

        file.write(bytes(new))
        new_byte_count = frame_count * wave_data.info.get_bytes_per_frame()

        return file, new_byte_count