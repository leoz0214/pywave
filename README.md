# pywave

Want to modify or play your *WAV* files, but cannot find suitable tools to do so? Well, `pywave` is here to save the day.

It can read a normal, uncompressed WAV file into a temporary file, so memory usage is low. Once this process is complete,
you can do lots with the WAV data:

- Get metadata (sample rate, bit depth, channel count etc.)
- Change audio playback speed
- Change audio sample rate (without changing speed)
- Change bit depth
- Get one channel of audio
- Decrease audio volume
- Reverse audio
- Crop audio
- Add silence (start/middle/end)
- Repeat audio
- Join audio
- Split audio
- Accelerate/decelerate audio (start at one speed, end at another)
- Play audio

Any modified WAV data can subsequently be saved to a file, and fingers crossed, your desired changes will be successful!

## Dependencies

Amazingly, `pywave` only has one dependency - `pyaudio`, and that is to play the audio. Even if you do not have this dependency
installed, you can still use other parts of this package, particularly the modification of WAV data (you can just save and play
somewhere else, such as Audacity).

## Compatibility

Python 3.9 or greater is supported.

## Examples

Getting started is super simple! Get a WAV file you would like to modify or experiment on.
Here are some examples of code which can build a solid base for your utilisation of this package.

### Speeding up audio (without changing sample rate)

    from pywave import wavfile

    audio = wavfile.read("audio.wav")
    double_speed_audio = audio.change_speed(2, "count")
    wavfile.write(double_speed_audio, "audiox2.wav")

### Ensuring WAV files have a maximum bit depth of 16

from pywave import wavfile

    wav_files = ["1.wav", "2.wav", "3.wav"]
    for file in wav_files:
        wav = wavfile.read(file)
        if wav.info.bit_depth > 16:
            wav = wav.change_bit_depth(16)
            wavfile.write(wav, file)

### Getting the second channel of audio of a stereo WAV and playing it 3 times.

    from pywave import wavfile
    from pywave import wavplay

    wav = wavfile.read("audio.wav")
    channel_2 = wav.to_mono(2)

    wavplay.play(channel_2, 3, True)

### Make the second half of a WAV quieter.

    from pywave import wavfile
    from pywave import wavmanip

    wav = wavfile.read("audio.wav")
    halves = wav.split(2, "count")
    halves[1] = halves[1].decrease_volume(10, "decibels")

    edited_wav = wavmanip.join(
        halves, wav.info.sample_rate,
        wav.info.bit_depth, wav.info.channels)
    wavfile.write(edited_wav, "new.wav")
