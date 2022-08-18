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
- Play audio

Any modified WAV data can subsequently be saved to a file, and fingers crossed, your desired changes will be successful!

Even better, `pywave` only has one dependency - `pyaudio`, and that is to play the audio. Even if you do not have this dependency
installed, you can still use other parts of this package, particularly the modification of WAV data (you can just save and play
somewhere else, such as Audacity).