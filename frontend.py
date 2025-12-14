import requests
import json

BASE_URL = "http://127.0.0.1:5000"

def start_pipeline(duration=10, target_lang="es"):
    """Start the audio pipeline"""
    url = f"{BASE_URL}/api/start-pipeline"
    payload = {"duration": duration, "target_lang": target_lang}
    response = requests.post(url, json=payload)
    return response.json()

def get_logs():
    """Fetch logs from backend"""
    url = f"{BASE_URL}/api/logs"
    response = requests.get(url)
    return response.json()

def get_results():
    """Fetch results from backend"""
    url = f"{BASE_URL}/api/results"
    response = requests.get(url)
    return response.json()

def download_audio(filename):
    """Download audio file"""
    url = f"{BASE_URL}/api/audio/{filename}"
    response = requests.get(url)
    if response.status_code == 200:
        with open(filename, "wb") as f:
            f.write(response.content)
        return True, filename
    return False, response.text

def summarize_text(text):
    """Get summary of text"""
    url = f"{BASE_URL}/api/summarize"
    response = requests.post(url, json={"text": text})
    return response.json()

def translate_text(target_lang):
    """Dynamically translate transcript to target language and get TTS"""
    url = f"{BASE_URL}/api/translate"
    response = requests.post(url, json={"target_lang": target_lang})
    return response.json()


# ===============================
# EXAMPLE USAGE
# ===============================
if __name__ == "__main__":
    print("Starting pipeline...")
    start_response = start_pipeline(duration=5, target_lang="es")
    print("Pipeline response:", start_response)

    import time
    print("Waiting for processing to finish...")
    time.sleep(15)  # Wait for pipeline to process audio

    logs = get_logs()
    print("Logs:")
    for log in logs['logs']:
        print(log)

    results = get_results()
    print("Results:")
    print(json.dumps(results['results'], indent=2))

    if 'translated_text' not in results['results']:
        # Example of dynamic translation
        trans_response = translate_text("fr")
        print("Dynamic translation to French:")
        print(json.dumps(trans_response, indent=2))
