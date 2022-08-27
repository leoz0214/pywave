"""
This module plays WAV audio data one at a time.
The audio can be paused, resumed, and stopped.
It can also be played numerous times, including indefinitely.
"""
import threading
import time
from typing import Union

try:
    import pyaudio
except ImportError:
    raise ImportError(
        "'pyaudio' is required to use this module. "
        "https://pypi.org/project/PyAudio/")

from . import _data
from . import wavfile


class _AudioPlayback:
    # Manages audio playback.

    def __init__(self) -> None:
        # Attributes which can be accessed inside the thread.
        self._playing = False
        self._paused = False
        self._pass_count = 0 # Chunks to skip upon resumption.
        self._to_stop = False
        self._to_pause = False
        self._wav = None
        self._play_count = 0
        self._starting_play_count = None
        self._exception = None

    def _play(self, pass_count: int = 0) -> None:
        # Interal audio playback. Can be threaded.
        pyaudio_object = pyaudio.PyAudio()

        int_type = (
            pyaudio.paUInt8, pyaudio.paInt16,
            pyaudio.paInt24, pyaudio.paInt32
        )[self._wav.info.byte_depth - 1]

        try:
            stream = pyaudio_object.open(
                self._wav.info.sample_rate, self._wav.info.channels,
                int_type, output=True)
        except OSError:
            self._exception = RuntimeError(
                "Unable to play audio - an error occured")
            self._wav = None
            return

        self._playing = True
        self._paused = False

        while self._play_count:
            current_pass_count = 0
            # Chunk size is 1200 because it needs to be a multiple of
            # 1, 2, 3 and 4
            # Otherwise n byte depth will not play properly.
            for chunk in self._wav.chunks(1200):
                if pass_count:
                    pass_count -= 1
                else:
                    if self._to_pause:
                        self._pass_count = current_pass_count
                        break
                    elif self._to_stop:
                        break

                    stream.write(chunk)
                current_pass_count += 1

            # Stop (or pause).
            self._paused = self._to_pause
            if self._paused or self._to_stop:
                break

            self._play_count -= 1

        self._to_pause = False
        self._to_stop = False
        self._playing = False
        stream.close()
        pyaudio_object.terminate()


_playback = _AudioPlayback()


def play(
    wav: Union[_data.WaveData, str], number_of_times: int = 1,
    wait_finish: bool = False) -> None:
    """
    Plays WAV audio a certain number of times, which can be
    asynchronous or waited for.

    'wav' - either a WaveData object or string which represents
    a file name for a WAV file.

    'number_of_times' - how many times to play the audio. Setting this
    to 0 means the audio never plays, and setting this to a negative
    number makes the audio play indefinitely (forever).

    'wait_finish' - determines whether or not to keep on
    executing the program while the audio is playing.
    Note: if this is set to Falseand this function is called at the
    end of a script, the script terminates, and audio will seemingly
    not play.

    The audio must not have an extreme sample rate (way too high or way
    too low), which would cause a RuntimeError to be raised.

    Only one WAV can be played at once, and if this function is called
    while audio is playing or paused, a RuntimeError is raised.
    """
    if is_paused():
        raise RuntimeError("Audio is currently paused.")
    elif is_playing():
        raise RuntimeError("Audio is already playing.")

    elif not isinstance(wav, (_data.WaveData, str)):
        raise TypeError(
            "'wav_data' must be of type 'WaveData' or a string (file).")
    elif not isinstance(number_of_times, int):
        raise TypeError("'number_of_times' must be an integer.")

    # Play 0 times means do not play.
    if not number_of_times:
        return
    
    _playback._wav = (
        wav if isinstance(wav, _data.WaveData) else wavfile.read(wav))

    _playback._play_count = _playback._starting_play_count = number_of_times

    # Allows for asynchronous execution.
    threading.Thread(target=_playback._play, daemon=True).start()

    while not is_playing():
        if _playback._exception is not None:
            exception = _playback._exception
            _playback._exception = None
            raise exception
        # To minimise resource usage - no difference should be noticed.
        time.sleep(0.01)
    
    if wait_finish:
        wait()


def stop() -> None:
    """
    Stops audio playback.

    If no audio is playing or paused, a RuntimeError is raised.
    """
    if not (is_playing() or is_paused()):
        raise RuntimeError("Audio is not playing.")
    
    _playback._wav = None
    _playback._pass_count = 0
    _playback._play_count = 0
    _playback._starting_play_count = None

    # Paused
    if is_paused():
        _playback._playing = False
        _playback._paused = False
        return

    # Playing
    _playback._to_stop = True
    _playback._paused = False

    while is_playing():
        time.sleep(0.01)


def pause() -> None:
    """
    Temporarily stops audio playback.

    If no audio is playing, a RuntimeError is raised.
    """
    if not is_playing():
        raise RuntimeError("Audio is not playing.")

    _playback._to_pause = True

    while not is_paused():
        time.sleep(0.01)


def resume() -> None:
    """
    Continues audio playback from a pause.

    If no audio is paused, a RuntimeError is raised.
    """
    if is_playing():
        raise RuntimeError("Audio is already playing.")
    elif _playback._wav is None:
        raise RuntimeError("Audio is not playing.")
    
    player = threading.Thread(
        target=lambda: _playback._play(_playback._pass_count), daemon=True)
    player.start()

    while not is_playing():
        time.sleep(0.01)


def wait() -> None:
    """
    Waits for audio to finish playing before continuing execution.

    Warning: if audio is set to play forever, this will lead into an
    infinite loop to sleep virtually forever.
    """
    if _playback._play_count < 0:
        # Infinite loop - sleep virtually forever
        while True:
            time.sleep(999999)

    while is_playing():
        time.sleep(0.01)


def restart() -> None:
    """
    Goes back to the start of audio for this current loop
    of audio playback.

    To reset the playback count entirely i.e number of times
    to play the audio, use the 'reset' function instead.

    If no audio is playing or paused, a RuntimeError is raised.
    """
    if not (is_playing() or is_paused()):
        raise RuntimeError("Audio is not playing.")
    elif not is_paused():
        pause()

    _playback._pass_count = 0
    resume()


def reset() -> None:
    """
    Entirely resets the current audio playback, including
    the number of times to play the audio.

    To restart the current loop of audio playback, use the
    'restart' function instead.

    If no audio is playing or paused, a RuntimeError is raised.
    """
    if not (is_playing() or is_paused()):
        raise RuntimeError("Audio is not playing.")
    elif not is_paused():
        pause()

    _playback._pass_count = 0
    _playback._play_count = _playback._starting_play_count
    resume()


def is_playing() -> bool:
    """
    Audio is currently playing.
    """
    return _playback._playing


def is_paused() -> bool:
    """
    Audio is currently paused.
    """
    return _playback._paused