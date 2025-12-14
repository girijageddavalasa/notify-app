import sounddevice as sd
from scipy.io.wavfile import write
import boto3
import time
import requests
import os
from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import threading
import json

# ========================
# AWS CONFIGURATION (HARDCODED)
# ========================
AWS_ACCESS_KEY_ID = #give urs
AWS_SECRET_ACCESS_KEY = #give urs
AWS_REGION = #give urs
BUCKET_NAME = #give urs

class AudioProcessingPipeline:
    def __init__(self):
        self.AWS_ACCESS_KEY_ID = AWS_ACCESS_KEY_ID
        self.AWS_SECRET_ACCESS_KEY = AWS_SECRET_ACCESS_KEY
        self.AWS_REGION = AWS_REGION
        self.BUCKET_NAME = BUCKET_NAME

        # Initialize AWS clients
        self.s3 = boto3.client(
            "s3",
            aws_access_key_id=self.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=self.AWS_SECRET_ACCESS_KEY,
            region_name=self.AWS_REGION
        )

        self.transcribe = boto3.client(
            "transcribe",
            aws_access_key_id=self.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=self.AWS_SECRET_ACCESS_KEY,
            region_name=self.AWS_REGION
        )

        self.comprehend = boto3.client(
            "comprehend",
            aws_access_key_id=self.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=self.AWS_SECRET_ACCESS_KEY,
            region_name=self.AWS_REGION
        )

        self.translate = boto3.client(
            "translate",
            aws_access_key_id=self.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=self.AWS_SECRET_ACCESS_KEY,
            region_name=self.AWS_REGION
        )

        self.polly = boto3.client(
            "polly",
            aws_access_key_id=self.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=self.AWS_SECRET_ACCESS_KEY,
            region_name=self.AWS_REGION
        )

        self.results = {}
        self.logs = []

    def log_message(self, message):
        self.logs.append(message)
        print(message)

    def get_logs(self):
        return self.logs

    def clear_logs(self):
        self.logs = []

    def record_audio(self, duration=10, fs=16000, audio_file="audio.wav"):
        try:
            self.log_message(f"🎙 Recording for {duration} seconds...")
            audio = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype='int16')
            sd.wait()
            write(audio_file, fs, audio)
            self.log_message(f" Audio recorded and saved as {audio_file}")
            self.results['audio_file'] = audio_file
            return True, audio_file
        except Exception as e:
            self.log_message(f"Recording failed: {str(e)}")
            return False, str(e)

    def upload_to_s3(self, audio_file):
        try:
            self.log_message("⬆ Uploading audio to S3...")
            s3_key = "audio/" + audio_file
            self.s3.upload_file(audio_file, self.BUCKET_NAME, s3_key)
            self.log_message("Uploaded to S3 successfully!")
            self.results['s3_key'] = s3_key
            return True, s3_key
        except Exception as e:
            self.log_message(f" S3 Upload Failed: {str(e)}")
            return False, str(e)

    def transcribe_audio(self, s3_key):
        try:
            job_name = "transcribe_job_" + str(int(time.time()))
            job_uri = f"s3://{self.BUCKET_NAME}/{s3_key}"
            self.log_message(f"Starting Transcription Job: {job_name}")

            self.transcribe.start_transcription_job(
                TranscriptionJobName=job_name,
                Media={"MediaFileUri": job_uri},
                MediaFormat="wav",
                LanguageCode="en-US",
            )

            self.log_message("Waiting for transcription to finish...")
            while True:
                status = self.transcribe.get_transcription_job(TranscriptionJobName=job_name)
                state = status["TranscriptionJob"]["TranscriptionJobStatus"]
                if state in ["COMPLETED", "FAILED"]:
                    break
                self.log_message(f"Status: {state}")
                time.sleep(5)

            if state == "FAILED":
                self.log_message(" Transcription failed.")
                return False, "Transcription failed"

            self.log_message(" Transcription completed!")
            uri = status["TranscriptionJob"]["Transcript"]["TranscriptFileUri"]

            response = requests.get(uri)
            if response.status_code == 200 and response.text.strip() != "":
                data = response.json()
                transcript_text = data["results"]["transcripts"][0]["transcript"]
                self.log_message(f" Transcribed Text: {transcript_text}")
                self.results['transcript'] = transcript_text
                return True, transcript_text
            else:
                self.log_message(" Failed to download valid transcript.")
                return False, "Failed to download transcript"

        except Exception as e:
            self.log_message(f" Transcription error: {str(e)}")
            return False, str(e)

    def analyze_sentiment(self, text):
        try:
            self.log_message(" Analyzing text sentiment with Comprehend...")
            sentiment = self.comprehend.detect_sentiment(Text=text, LanguageCode="en")
            entities = self.comprehend.detect_entities(Text=text, LanguageCode="en")
            key_phrases = self.comprehend.detect_key_phrases(Text=text, LanguageCode="en")

            sentiment_result = sentiment["Sentiment"]
            entities_list = [e["Text"] for e in entities["Entities"]]
            key_phrases_list = [k["Text"] for k in key_phrases["KeyPhrases"]]

            self.log_message(f" Sentiment: {sentiment_result}")
            self.results.update({
                'sentiment': sentiment_result,
                'entities': entities_list,
                'key_phrases': key_phrases_list
            })

            return True, {
                'sentiment': sentiment_result,
                'entities': entities_list,
                'key_phrases': key_phrases_list
            }
        except Exception as e:
            self.log_message(f" Analysis error: {str(e)}")
            return False, str(e)

    def translate_text(self, text, target_lang="es"):
        try:
            self.log_message(f"Translating text to {target_lang}...")
            translation = self.translate.translate_text(
                Text=text, SourceLanguageCode="en", TargetLanguageCode=target_lang
            )
            translated_text = translation["TranslatedText"]
            self.log_message(f"Translated Text: {translated_text}")
            return True, translated_text
        except Exception as e:
            self.log_message(f" Translation error: {str(e)}")
            return False, str(e)

    def text_to_speech(self, text, voice_id="Joanna", output_file="speech.mp3"):
        try:
            self.log_message(f" Converting text to speech: {output_file}")
            response = self.polly.synthesize_speech(Text=text, OutputFormat="mp3", VoiceId=voice_id)
            with open(output_file, "wb") as f:
                f.write(response["AudioStream"].read())
            self.log_message(f"Audio saved as {output_file}")
            return True, output_file
        except Exception as e:
            self.log_message(f"Text-to-speech error: {str(e)}")
            return False, str(e)

    def summarize_text(self, text):
        try:
            self.log_message("Summarizing text...")
            phrases = self.comprehend.detect_key_phrases(Text=text, LanguageCode="en")
            bullet_points = [f"• {p['Text']}" for p in phrases['KeyPhrases'][:5]]
            summary = "\n".join(bullet_points)
            self.results['summary'] = summary
            self.log_message(f"Summary generated:\n{summary}")
            return True, summary
        except Exception as e:
            self.log_message(f"Summarization error: {str(e)}")
            return False, str(e)

    def run_full_pipeline(self, duration=10, target_lang="es"):
        try:
            success, audio_file = self.record_audio(duration=duration)
            if not success: return False, "Recording failed"
            success, s3_key = self.upload_to_s3(audio_file)
            if not success: return False, "S3 upload failed"
            success, transcript = self.transcribe_audio(s3_key)
            if not success: return False, "Transcription failed"
            success, analysis = self.analyze_sentiment(transcript)
            if not success: return False, "Sentiment analysis failed"

            # Translate transcript
            success, translated = self.translate_text(transcript, target_lang=target_lang)
            if not success: return False, "Translation failed"

            # Generate summary in original language
            success, summary = self.summarize_text(transcript)
            if not success: return False, "Summary failed"

            # Translate summary to target language
            success, translated_summary = self.translate_text(summary, target_lang=target_lang)
            if not success: return False, "Summary translation failed"
            self.results['translated_summary'] = translated_summary

            # Map voice to language
            voice_map = {"es": "Lupe", "fr": "Celine", "de": "Marlene",
                         "hi": "Aditi", "ja": "Mizuki", "zh": "Zhiyu", "en": "Joanna"}
            voice_id = voice_map.get(target_lang, "Joanna")

            # TTS for transcript
            success, tts_transcript = self.text_to_speech(translated, voice_id=voice_id, output_file=f"transcript_{target_lang}.mp3")
            if not success: return False, "Transcript TTS failed"
            self.results['tts_translated'] = tts_transcript

            # TTS for summary
            success, tts_summary = self.text_to_speech(translated_summary, voice_id=voice_id, output_file=f"summary_{target_lang}.mp3")
            if not success: return False, "Summary TTS failed"
            self.results['tts_summary'] = tts_summary

            self.log_message("\nPIPELINE COMPLETED SUCCESSFULLY!")
            return True, self.results
        except Exception as e:
            self.log_message(f"Pipeline error: {str(e)}")
            return False, str(e)


# ========================
# FLASK APPLICATION
# ========================
app = Flask(__name__, template_folder='templates', static_folder='static')
CORS(app)
pipeline = None


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/start-pipeline', methods=['POST'])
def start_pipeline():
    global pipeline
    try:
        data = request.json
        duration = data.get('duration', 10)
        target_lang = data.get('target_lang', 'es')
        pipeline = AudioProcessingPipeline()
        def run(): pipeline.run_full_pipeline(duration=duration, target_lang=target_lang)
        threading.Thread(target=run, daemon=True).start()
        return jsonify({'status': 'started'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/logs', methods=['GET'])
def get_logs():
    global pipeline
    if pipeline: return jsonify({'logs': pipeline.get_logs()})
    return jsonify({'logs': []})


@app.route('/api/results', methods=['GET'])
def get_results():
    global pipeline
    if pipeline: return jsonify({'results': pipeline.results})
    return jsonify({'results': {}})


@app.route('/api/audio/<filename>', methods=['GET'])
def download_audio(filename):
    try:
        return send_file(filename, mimetype='audio/mpeg', as_attachment=True)
    except Exception as e:
        return jsonify({'error': str(e)}), 404


@app.route('/api/summarize', methods=['POST'])
def summarize_api():
    global pipeline
    if not pipeline:
        pipeline = AudioProcessingPipeline()
    text = request.json.get('text', '')
    success, summary = pipeline.summarize_text(text)
    if success:
        return jsonify({'summary': summary})
    else:
        return jsonify({'error': summary}), 500


@app.route('/api/translate', methods=['POST'])
def dynamic_translate():
    global pipeline
    if not pipeline or 'transcript' not in pipeline.results:
        return jsonify({'error': 'No transcript available. Run pipeline first.'}), 400

    data = request.json
    target_lang = data.get('target_lang', 'es')
    text_to_translate = pipeline.results['transcript']
    summary_text = pipeline.results['summary']

    # Translate transcript and summary
    success, translated_text = pipeline.translate_text(text_to_translate, target_lang)
    if not success: return jsonify({'error': translated_text}), 500

    success, translated_summary = pipeline.translate_text(summary_text, target_lang)
    if not success: return jsonify({'error': translated_summary}), 500

    # Map voice
    voice_map = {"es": "Lupe", "fr": "Celine", "de": "Marlene",
                 "hi": "Aditi", "ja": "Mizuki", "zh": "Zhiyu", "en": "Joanna"}
    voice_id = voice_map.get(target_lang, "Joanna")

    # TTS for transcript
    success, tts_transcript = pipeline.text_to_speech(translated_text, voice_id=voice_id, output_file=f"transcript_{target_lang}.mp3")
    if not success: return jsonify({'error': tts_transcript}), 500

    # TTS for summary
    success, tts_summary = pipeline.text_to_speech(translated_summary, voice_id=voice_id, output_file=f"summary_{target_lang}.mp3")
    if not success: return jsonify({'error': tts_summary}), 500

    # Save results
    pipeline.results['translated_text'] = translated_text
    pipeline.results['translated_summary'] = translated_summary
    pipeline.results['tts_translated'] = tts_transcript
    pipeline.results['tts_summary'] = tts_summary

    return jsonify({
        'translated_text': translated_text,
        'summary': translated_summary,
        'tts_translated': tts_transcript,
        'tts_summary': tts_summary
    })


# ========================
# PAGES / NAVIGATION
# ========================
@app.route('/translate')
def translate_page():
    return render_template('translate.html')


@app.route('/transcript')
def transcript_page():
    return render_template('transcript.html')


@app.route('/logs')
def logs_page():
    return render_template('logs.html')


if __name__ == '__main__':
    app.run(debug=True)
