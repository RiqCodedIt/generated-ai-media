import os
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from elevenlabs import play
# https://elevenlabs.io/docs/quickstart

def generate_speech():
    load_dotenv()

    client = ElevenLabs(
    api_key=os.getenv("ELEVENLABS_API_KEY"),
    )

    speech_text = "Lets get rich boys! We are going to the moon!"

    audio = client.text_to_speech.convert(
        text=f"{speech_text}",
        voice_id="JBFqnCBsd6RMkjVDRZzb",
        model_id="eleven_multilingual_v2",
        output_format="mp3_44100_128",
    )
    play(audio)
    return audio

def main():
    generate_speech()

if __name__== "__main__":
    main()