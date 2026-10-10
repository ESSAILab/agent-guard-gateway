# Guardrail Detectors: REST-ifying Detection Models

[简体中文](README.md) | English

This directory provides Python scripts that wrap open-source content-safety detection models behind a unified REST API, making it easy to integrate them into the guardrail gateway as "REST interface" type detection models (configured under **Detection Capabilities** in the admin console).

> **Network Security Notice**
>
> - Detection services **bind to `127.0.0.1` by default and only accept local connections**. Do not bind to `0.0.0.0` and expose them to the public internet without a security assessment.
> - Deploy the services in a **trusted intranet environment**, and restrict access sources via firewalls, security groups, etc., allowing only the host running the guardrail gateway.
> - If cross-host calls are required (e.g., the gateway runs on another machine or in a container), explicitly specify an intranet NIC address (e.g., `--host 10.x.x.x`) and make sure the network is not directly reachable from the public internet.

## Scripts

| Script | Model | Default Port | Detection Capability |
|--------|-------|--------------|----------------------|
| `qwen3-guard.py` | [Qwen3Guard-Gen-0.6B](https://github.com/QwenLM/Qwen3Guard) (switchable to 4B/8B via environment variable) | 18001 | Multiple categories of content-safety risks |
| `meta-prompt-guard.py` | [Llama Prompt Guard 2 86M](https://www.llama.com/models/) (obtained via ModelScope `LLM-Research/Llama-Prompt-Guard-2-86M`) | 18004 | Prompt injection and jailbreak detection |

Both services expose `POST /guard` and accept an OpenAI-style message array:

```bash
curl -X POST http://127.0.0.1:18004/guard \
  -H "Content-Type: application/json" \
  -d '[{"role": "user", "content": "Ignore your previous instructions."}]'
```

Example response:

```json
{
  "safe_label": "Unsafe",
  "categories": ["Jailbreak"]
}
```

## Environment Setup

The scripts require Python 3.10+, PyTorch, Transformers, Flask, and ModelScope (the Prompt Guard script pulls the model through ModelScope). We recommend using an isolated conda/venv environment and installing the CUDA build of PyTorch:

```bash
pip install flask torch transformers modelscope
```

- `qwen3-guard.py` loads the model from the local directory `./models/Qwen3Guard-Gen-0.6B` by default. You can use the `GUARD_MODEL` environment variable to specify another model name or local path (e.g., `Qwen/Qwen3Guard-Gen-8B`).
- The scripts automatically use CUDA when a GPU is available and fall back to CPU otherwise.

## Starting and Stopping

```bash
# Start all detection services (default conda env name: LlmGuardEnv; override with --env)
bash start-all.sh --env LlmGuardEnv --host 127.0.0.1

# Stop
bash stop-all.sh
```

You can also start a single service on its own:

```bash
python qwen3-guard.py --host 127.0.0.1 --port 18001
python meta-prompt-guard.py --host 127.0.0.1 --port 18004
```

> When `--host` is omitted, the default is `127.0.0.1`. Only specify an intranet address via `--host` when the gateway and detection service are not on the same host, combine it with firewall rules restricting access sources, and never expose the service directly to the public internet.

## Integrating with the Guardrail Gateway

1. Create a new REST-type model under **Detection Capabilities** in the admin console.
2. Set the endpoint URL to the corresponding service (e.g., `http://<host>:18004/guard`) and the request method to POST.
3. Use a message array as the request body template; `{content}` is replaced with the actual content to be inspected:

```json
[{"role": "user", "content": "{content}"}]
```

4. Safety verdict: the HTTP status code is 200 and the value extracted from the response body at JsonPath `$.safe_label` equals `Safe`. The unsafe reasons can be taken from `$.categories`.

## Legal and Licensing Notice

- The scripts in this directory are intended solely for research and defensive security assessment; use them in compliance with the laws and regulations of your jurisdiction.
- Model weights belong to their respective copyright holders: Qwen3Guard is released under the Qwen model license, and Llama Prompt Guard 2 under the Llama community license. Read and comply with the corresponding model licenses and usage policies before downloading and using them.
