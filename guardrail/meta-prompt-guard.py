import argparse
import logging
import os
import sys
import torch
from flask import Flask, request, jsonify
from modelscope import AutoTokenizer, AutoModelForSequenceClassification

os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/meta-prompt-guard.log", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)


'''
运行示例
conda run -n LlmGuardEnv python meta-prompt-guard.py --port 18004
conda run -n LlmGuardEnv python meta-prompt-guard.py --host 127.0.0.1 --port 18004

curl -X POST http://127.0.0.1:18004/guard \
  -H "Content-Type: application/json" \
  -d '[{"role": "user", "content": "Hello world!"}]'

'''

app = Flask(__name__)

model_id = "LLM-Research/Llama-Prompt-Guard-2-86M"
logger.info("Loading tokenizer and model...")
tokenizer = AutoTokenizer.from_pretrained(model_id)
model = AutoModelForSequenceClassification.from_pretrained(model_id)

# 手动覆盖正确标签映射
model.config.id2label = {0: "BENIGN", 1: "MALICIOUS"}
model.config.label2id = {"BENIGN": 0, "MALICIOUS": 1}

device = "cuda" if torch.cuda.is_available() else "cpu"
model = model.to(device)
model.eval()
logger.info("Model loaded successfully on %s.", device)


def check_prompt(text):
    """Classifies whether a prompt is malicious (jailbreak / injection)."""
    inputs = tokenizer(text, return_tensors="pt").to(device)
    with torch.no_grad():
        logits = model(**inputs).logits
    predicted_class_id = logits.argmax().item()
    label = model.config.id2label[predicted_class_id]
    probabilities = torch.softmax(logits, dim=-1)[0]
    confidence = probabilities[predicted_class_id].item()
    return label, confidence


def process_messages(messages):
    # Extract the last user message as the prompt to check
    user_content = None
    for message in reversed(messages):
        if message.get('role') == 'user':
            user_content = message.get('content', '')
            break

    if not user_content:
        raise ValueError('messages must contain a user message')

    logger.debug("Checking prompt: %s", user_content)
    label, confidence = check_prompt(user_content)
    logger.debug("Prompt guard result: label=%s, confidence=%.4f", label, confidence)

    is_malicious = (label == "MALICIOUS")
    safe_label = 'Unsafe' if is_malicious else 'Safe'
    categories = ['Jailbreak'] if is_malicious else ['None']

    return safe_label, categories


@app.route('/guard', methods=['POST'])
def guard():
    logger.debug("========== New request ==========")
    try:
        data = request.get_json(force=True)
        logger.debug("Received request data: %s", data)
        # messages = data.get('messages', [])
        messages = data

        if not messages:
            return jsonify({'error': 'messages is required'}), 400

        safe_label, categories = process_messages(messages)
        logger.debug("Generated safe_label: %s, Categories: %s", safe_label, categories)

        result = {
            'safe_label': safe_label,
            'categories': categories
        }
        logger.debug("Response: %s", result)
        return jsonify(result)
    except ValueError as exc:
        logger.exception("Invalid request")
        return jsonify({'error': str(exc)}), 400
    except Exception:
        logger.exception("Exception occurred while processing request")
        return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Llama Prompt Guard 2 86M REST API Service')
    parser.add_argument('--host', type=str, default='127.0.0.1', help='Host address for the REST API service (default: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=18004, help='Port number for the REST API service (default: 18004)')

    args = parser.parse_args()

    app.run(host=args.host, port=args.port)
