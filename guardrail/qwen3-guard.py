import argparse
import json
import logging
import os
import re
import sys
import torch
from flask import Flask, request, jsonify
from transformers import AutoModelForCausalLM, AutoTokenizer

os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/qwen3-guard.log", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)


''' 
运行示例
conda run -n LlmGuardEnv python qwen3-guard.py --port 18001
conda run -n LlmGuardEnv python qwen3-guard.py --host 127.0.0.1 --port 18001


curl -X POST http://127.0.0.1:18001/guard \
  -H "Content-Type: application/json" \
  -d '[{"role": "user", "content": "Hello world!"}]'

'''

app = Flask(__name__)
model_name = os.environ.get("GUARD_MODEL", "./models/Qwen3Guard-Gen-0.6B")
# 也可通过环境变量 GUARD_MODEL 指定其他模型，例如：
# Qwen/Qwen3Guard-Gen-8B、Qwen/Qwen3Guard-Gen-4B
# load the tokenizer and the model
logger.info("Loading tokenizer and model: %s", model_name)
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(
    model_name,
    torch_dtype="auto",
    device_map="cuda" if torch.cuda.is_available() else None,
)
logger.info("Model loaded successfully.")


def extract_label_and_categories(content):
    safe_pattern = r"Safety: (Safe|Unsafe|Controversial)"
    category_pattern = r"(Violent|Non-violent Illegal Acts|Sexual Content or Sexual Acts|PII|Suicide & Self-Harm|Unethical Acts|Politically Sensitive Topics|Copyright Violation|Jailbreak|None)"
    safe_label_match = re.search(safe_pattern, content)
    label = safe_label_match.group(1) if safe_label_match else None
    categories = re.findall(category_pattern, content)
    return label, categories


def process_messages(messages):
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False
    )
    logger.debug("Applied chat template text: %s", text)
    model_inputs = tokenizer([text], return_tensors="pt").to(model.device)

    generated_ids = model.generate(
        **model_inputs,
        max_new_tokens=128
    )
    output_ids = generated_ids[0][len(model_inputs.input_ids[0]):].tolist()

    content = tokenizer.decode(output_ids, skip_special_tokens=True)
    logger.debug("Raw model output: %s", content)
    safe_label, categories = extract_label_and_categories(content)
    logger.debug("Parsed safe_label: %s, categories: %s", safe_label, categories)
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
    except Exception:
        logger.exception("Exception occurred while processing request")
        return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Qwen3Guard REST API Service')
    parser.add_argument('--host', type=str, default='127.0.0.1', help='Host address for the REST API service (default: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=18001, help='Port number for the REST API service (default: 18001)')

    args = parser.parse_args()

    app.run(host=args.host, port=args.port)
