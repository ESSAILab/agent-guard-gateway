# AI Agent Security Gateway - Integration Guide

[简体中文](INTEGRATION.md) | English

This document is for developers who need to integrate the guardrail system into their AI applications.

## Integration Flow

### 1. Get an API Key

Log in to the admin console (default: http://localhost:8000), go to **API Key Management**, and generate a new key.

Save the generated key value (in the format `gk_xxxxxxxxxx`); it must be carried in an HTTP header in subsequent requests.

### 2. Configure a Detection Path

Create an external detection path under **Detection Scenarios**, for example:

- **Name**: Chat input detection
- **External path**: `/chat-input`
- **Authentication key**: select the API key you just created
- **Policy chain**: select one or more policies to be executed in order

After saving, the path is exposed as `POST /guard/chat-input`.

### 3. Call the Detection API

#### Python Example

```python
import requests

GUARDRAIL_URL = "http://localhost:8000"
API_KEY = "gk_xxxxxxxxxx"

def check_content(content: str) -> dict:
    """Call the guardrail detection API and return the result."""
    response = requests.post(
        f"{GUARDRAIL_URL}/guard/chat-input",
        headers={"X-API-Key": API_KEY, "Content-Type": "application/json"},
        json={
            "messages": content,
            "jsonpath": "",
            "illegal_status_code": 403  # Return 403 when unsafe
        }
    )
    return response.json()

# Usage example
result = check_content("text submitted by the user")
if result["code"] == 200:
    print("Passed: content is safe")
else:
    print(f"Rejected: {result['message']}")
    print(f"Risk type: {result['risk_type']}")
```

#### JavaScript/Node.js Example

```javascript
const axios = require('axios');

const GUARDRAIL_URL = 'http://localhost:8000';
const API_KEY = 'gk_xxxxxxxxxx';

async function checkContent(content) {
  try {
    const response = await axios.post(
      `${GUARDRAIL_URL}/guard/chat-input`,
      {
        messages: content,
        jsonpath: '',
        illegal_status_code: 403
      },
      {
        headers: {
          'X-API-Key': API_KEY,
          'Content-Type': 'application/json'
        }
      }
    );
    return response.data;
  } catch (error) {
    if (error.response && error.response.status === 403) {
      // Detection did not pass
      return error.response.data;
    }
    throw error;
  }
}

// Usage example
checkContent('text submitted by the user').then(result => {
  if (result.code === 200) {
    console.log('Passed: content is safe');
  } else {
    console.log(`Rejected: ${result.message}`);
    console.log(`Risk type: ${result.risk_type}`);
  }
});
```

#### cURL Example

```bash
curl -X POST http://localhost:8000/guard/chat-input \
  -H "Content-Type: application/json" \
  -H "X-API-Key: gk_xxxxxxxxxx" \
  -d '{
    "messages": "text submitted by the user",
    "jsonpath": "",
    "illegal_status_code": 403
  }'
```

## Request Parameters

### `messages` (required)

The message content to inspect. It can be:
- A plain text string
- A JSON string (used together with `jsonpath`)

### `jsonpath` (optional)

A JsonPath expression that extracts the actual content to inspect from `messages`.

**Example scenario**: the AI application's full request body is complex JSON, and only one of its fields needs to be inspected.

```json
{
  "messages": "{\"user_input\":\"this is user input\",\"context\":\"context\"}",
  "jsonpath": "$.user_input"
}
```

In this case the guardrail only inspects the value of the `user_input` field rather than the whole JSON.

Leave it empty to inspect the entire `messages` payload.

### `illegal_status_code` (optional)

The HTTP status code the guardrail should return when the detection result is unsafe.

- Default: `200` (the business code `code` distinguishes safe/unsafe)
- Common choice: `403` (easier to integrate with other middleware that blocks based on HTTP status codes)

## Response Format

Regardless of the detection result, the response body has a consistent format:

```json
{
  "code": 200,          // Business code: 200 safe, 4030 unsafe, 4001 extraction failed
  "risk_level": "NONE", // Risk level: NONE when safe, HIGH when unsafe, LOW when extraction fails
  "message": "...",     // Descriptive message
  "risk_type": "..."    // Risk type (non-empty when unsafe)
}
```

- `code == 200`: safe, the request can be allowed through
- `code == 4030`: risk detected, blocking is recommended
- `code == 4001`: JsonPath extraction failed (message is not valid JSON or the path does not match)

## Advanced Scenarios

### Scenario 1: Inspect LLM Output Only

When creating a policy, select tags in the "output only" direction and bind that policy to a dedicated API path (e.g., `/chat-output`).

Call that path after the LLM generates a reply but before returning it to the user.

### Scenario 2: Multi-Stage Detection (Input + Output)

Create two API paths:
- `/guard/input`: bound to the input policy chain
- `/guard/output`: bound to the output policy chain

Call `/guard/input` before requesting the LLM, and call `/guard/output` after receiving the LLM reply.

### Scenario 3: Asynchronous Detection

If your business is extremely latency-sensitive, you can:
1. Return the LLM result to the user synchronously and quickly
2. Call the guardrail asynchronously and record unsafe cases for auditing or post-processing

The gateway itself is already optimized for concurrency; typical latency is 100-500ms (depending on the policy configuration).

## Error Handling

| HTTP Status | Description | Recommended Action |
|-------------|-------------|--------------------|
| 200 | Detection completed; judge the result based on `code` | Handle normally |
| 401 | API key missing or invalid | Check the `X-API-Key` header |
| 403 | API key disabled or path not active | Contact the administrator |
| 404 | External path does not exist | Check that the request path is correct |
| 500 | Server-side error | Retry or contact operations |

## Performance Recommendations

1. **Reuse HTTP connections**: use a connection pool (e.g., Python's `requests.Session`)
2. **Set reasonable timeouts**: 5-10 seconds is recommended (consistent with the policy's `max_wait_seconds`)
3. **Choose the right policy rule**:
   - Sequential detection: invokes the model pool one by one with fast failure; suited to high-throughput scenarios requiring multi-layer redundancy. Place stricter/faster detection models earlier in the policy to intercept as early as possible.
   - Random detection: randomly picks one invocation from a pool of interchangeable redundant models each time; fixed cost and an unpredictable protection surface, suited to low-cost spot checks.

## Observability and Monitoring

- **Request logs**: under **Detection Records** in the admin console, filterable by path and result
- **Detection model logs**: invocation details and latency for each detection model
- **Live dashboard**: http://localhost:8000/#/dashboard, to observe the detection flow

## FAQ

**Q: What happens when guardrail detection fails (timeout/error)?**

A: Decide according to your business scenario:
- Conservative strategy: treat detection failure as unsafe and block the request
- Permissive strategy: allow the request through on detection failure and log it for later auditing

The gateway's `timeout_policy` setting controls how a single-model timeout is counted (safe / unsafe).

**Q: How can I reduce false positives?**

A:
1. Place stricter/faster detection models earlier in the policy to intercept early and reduce subsequent calls
2. Integrate detection models from multiple sources (e.g., a commercial service plus an in-house script) to form a sequential detection chain
3. Review observability logs periodically and adjust policy parameters and model ordering

**Q: Can policies be changed dynamically without restarting the service?**

A: Yes. Configuration made in the admin console takes effect immediately; no restart is needed.

---

**More documents**

- [Project Overview and Quick Start](../README_EN.md)
- [System Architecture and Design Principles](./ARCHITECTURE_EN.md)
- [API Reference](http://localhost:8000/docs)
