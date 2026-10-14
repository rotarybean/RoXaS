# Voice and audio

## Pipeline (CPU-only on the CM5)

Wake or push-to-talk, then whisper.cpp (tiny.en or base.en, with a vocabulary
prompt for rotary and DTC terms), then retrieval and the 0.5B model through
llama.cpp, then Piper (run as its HTTP server, not the command line, so the
voice model stays loaded). Audio leaves through a USB DAC because the CM5 has
no analog output.

## Conversation states

| State | Music | Mic | Ends when |
|---|---|---|---|
| Music | full | closed | Button press, or an alert arrives |
| Listening | faded to silence | open | Speech ends (voice-activity detection) or timeout |
| Thinking | silent | closed | The answer is ready |
| Speaking | silent, or ducked to ~20% for alerts | closed | Speech finishes |

Rules:

- The mic is closed by default. The car never listens while music plays.
- During a conversation, music stays muted for the whole turn and fades back up
  once at the end. For an unprompted alert, music ducks, the car speaks, and
  music returns.
- A button press during Speaking cuts the voice and goes to Listening.
- About 5 seconds of silence cancels listening with a soft tone.
- Critical alerts interrupt anything. Normal alerts wait until idle.
- A short chime marks the mic opening and closing.

## Fade settings (starting point, tune by ear)

Fade down about 300 to 400 ms, up about 1 second, on a perceptual curve (cube
the gain as a quick approximation). Normalize music loudness and level the
voice so it does not jump.

## Head unit input

The factory RX-8 head unit has no aux jack. Adapters that plug into its
CD-changer port add an aux source. The head unit must be on that source for
anything to play, which is why all audio routes through aux. Check part
availability and head-unit compatibility, and take the connector pinout from
the factory service manual, not from forum posts.
