import sys
import configparser

# Azure Speech
import os
import azure.cognitiveservices.speech as speechsdk
# import wave
import librosa

# Azure Translation
from azure.ai.translation.text import TextTranslationClient

# from azure.ai.translation.text.models import InputTextItem
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError


from flask import Flask, request, abort , render_template , url_for
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
)
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
    AudioMessage,
)

# Config Parser
config = configparser.ConfigParser()
config.read("config.ini")

# Azure Speech Settings
speech_config = speechsdk.SpeechConfig(
    subscription=config["AzureSpeech"]["SPEECH_KEY"],
    region=config["AzureSpeech"]["SPEECH_REGION"],
)
audio_config = speechsdk.audio.AudioOutputConfig(use_default_speaker=True)
UPLOAD_FOLDER = "static"

# Translator Setup
text_translator = TextTranslationClient(
    credential=AzureKeyCredential(config["AzureTranslator"]["Key"]),
    endpoint=config["AzureTranslator"]["EndPoint"],
    region=config["AzureTranslator"]["Region"],
)


app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


channel_access_token = config["Line"]["CHANNEL_ACCESS_TOKEN"]
channel_secret = config["Line"]["CHANNEL_SECRET"]
if channel_secret is None:
    print("Specify LINE_CHANNEL_SECRET as environment variable.")
    sys.exit(1)
if channel_access_token is None:
    print("Specify LINE_CHANNEL_ACCESS_TOKEN as environment variable.")
    sys.exit(1)

handler = WebhookHandler(channel_secret)

configuration = Configuration(access_token=channel_access_token)

@app.route("/")
def home():
    return render_template("index.html")
@app.route("/azure_translate", methods=["POST"])
def call_llm():
    if request.method == "POST":
        print("POST!")
        data = request.form
        print(data)
        chinese_text = data["message"]
        print(chinese_text)
        translation_result = azure_translate(chinese_text)
        print(translation_result)
        audio_duration = azure_speech(translation_result)
        print(audio_duration)
        return translation_result      
    return "OK"
@app.route("/callback", methods=["POST"])
def callback():
    # get X-Line-Signature header value
    signature = request.headers["X-Line-Signature"]
    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # parse webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"


@handler.add(MessageEvent, message=TextMessageContent)
def message_text(event):
    translation_result = azure_translate(event.message.text)
    tranliterate_result = azure_transliterate(translation_result)
    # dictionary_result = azure_dictionary(event.message.text)
    audio_duration = azure_speech(translation_result)
    print(translation_result)
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[
                    TextMessage(text=translation_result),
                    TextMessage(text=tranliterate_result),
                    # TextMessage(text=dictionary_result),
                    AudioMessage(
                        originalContentUrl=config["Deploy"]["URL"]
                        + "/static/outputaudio.wav",
                        duration=audio_duration,
                    ),
                ],
            )
        )
 
#-----------------Azure Functions-----------------#

def azure_speech(user_input):
    # The language of the voice that speaks.
    # speech_config.speech_synthesis_voice_name = "en-US-JennyNeural"
    speech_config.speech_synthesis_voice_name = "ko-KR-YuJinNeural"
    file_name = "outputaudio.wav"
    file_config = speechsdk.audio.AudioOutputConfig(filename="static/" + file_name)
    speech_synthesizer = speechsdk.SpeechSynthesizer(
        speech_config=speech_config, audio_config=file_config
    )

    # Receives a text from console input and synthesizes it to wave file.
    result = speech_synthesizer.speak_text_async(user_input).get()
    # Check result
    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        print(
            "Speech synthesized for text [{}], and the audio was saved to [{}]".format(
                user_input, file_name
            )
        )

        # with wave.open("static\outputaudio.wav", "r") as wav_file:
        #     frames = wav_file.getnframes()
        #     rate = wav_file.getframerate()
        #     audio_duration = round(frames / float(rate))
        audio_duration = round(
            librosa.get_duration(path="static/outputaudio.wav") * 1000
        )
        print(audio_duration)
        return audio_duration
    elif result.reason == speechsdk.ResultReason.Canceled:
        cancellation_details = result.cancellation_details
        print("Speech synthesis canceled: {}".format(cancellation_details.reason))
        if cancellation_details.reason == speechsdk.CancellationReason.Error:
            print("Error details: {}".format(cancellation_details.error_details))


def azure_translate(user_input):

    try:
        target_languages = ["ko"]
        # input_text_elements = [InputTextItem(text=user_input)]
        input_text_elements = [user_input]

        response = text_translator.translate(
            body=input_text_elements, to_language=target_languages
        )
        print(response)
        translation = response[0] if response else None

        if translation:
            return translation.translations[0].text

    except HttpResponseError as exception:
        print(f"Error Code: {exception.error}")
        print(f"Message: {exception.error.message}")

def azure_transliterate(user_input):
    try:
        language = "ko"
        from_script = "Kore"
        to_script = "Latn"
        input_text_elements = [user_input]

        response = text_translator.transliterate(
            body=input_text_elements,
            language=language,
            from_script=from_script,
            to_script=to_script,
        )
        transliteration = response[0] if response else None

        if transliteration:
            print(
                f"Input text was transliterated to '{transliteration.script}' script. Transliterated text: '{transliteration.text}'."
            )
            return transliteration.text

    except HttpResponseError as exception:
        if exception.error is not None:
            print(f"Error Code: {exception.error.code}")
            print(f"Message: {exception.error.message}")
        raise


def azure_dictionary(user_input):
    try:
        from_language = "zh-Hans"
        to_language = "en"
        input_text_elements = [user_input]

        response = text_translator.lookup_dictionary_entries(
            body=input_text_elements, from_language=from_language, to_language=to_language
        )
        dictionary_entry = response[0] if response else None

        if dictionary_entry:
            if len(dictionary_entry.translations) == 0:
                return "字典裡面沒有這個詞"
            print(f"For the given input {len(dictionary_entry.translations)} entries were found in the dictionary.")
            print(
                f"First entry: '{dictionary_entry.translations[0].display_target}', confidence: {dictionary_entry.translations[0].confidence}."
            )
            # merge all translations into one string
            result = ""
            for x in dictionary_entry.translations:
                result += x.display_target + "\n"
            return result

    except HttpResponseError as exception:
        if exception.error is not None:
            print(f"Error Code: {exception.error.code}")
            print(f"Message: {exception.error.message}")
        raise


if __name__ == "__main__":
    app.run()