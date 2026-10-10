"""
单个检测模型的调用与有效性检测。

支持两种接入方式：
  - REST API：构造 HTTP 请求，按「状态码 + JsonPath 值」判定安全。
  - Python 脚本：在受限子进程中执行用户脚本，约定 detect(content) 返回
    (code, message)，code==0 表示安全，message 为不安全提示。

所有调用均返回结构化的 InvokeResult，供策略引擎做顺序检测判定。
"""
import asyncio
import json
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx
from jsonpath_ng.ext import parse as jsonpath_parse

from app.models import DetectionModel


@dataclass
class InvokeResult:
    """单模型调用结果。"""

    safe: bool
    # 判定状态：safe / unsafe / timeout / error
    status: str
    prompt_message: str = ""
    request_detail: str = ""
    response_detail: str = ""
    latency_ms: float = 0.0
    model_id: Optional[int] = None
    model_name: str = ""
    access_type: str = ""


# ---------------------------------------------------------------------
# JsonPath 工具
# ---------------------------------------------------------------------
def extract_jsonpath(data: Any, expr: str) -> Optional[Any]:
    """按 JsonPath 表达式提取首个匹配值；失败或无匹配返回 None。"""
    if not expr:
        return None
    try:
        matches = jsonpath_parse(expr).find(data)
        if matches:
            return matches[0].value
    except Exception:
        pass
    return None


def render_body_template(template: dict, content: str) -> Any:
    """
    渲染 REST 请求体模板：递归地将字符串中的 {content} 占位符替换为被检测内容。
    若模板为空，默认将 content 作为请求体；content 为合法 JSON 时解析为对象，否则原样透传。
    """
    if not template:
        if isinstance(content, str):
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return content
        return content

    def _render(node: Any) -> Any:
        if isinstance(node, str):
            return node.replace("{content}", content)
        if isinstance(node, dict):
            return {k: _render(v) for k, v in node.items()}
        if isinstance(node, list):
            return [_render(v) for v in node]
        return node

    return _render(template)


# ---------------------------------------------------------------------
# REST 接入调用
# ---------------------------------------------------------------------
async def _invoke_rest(
    model: DetectionModel, content: str, timeout: float
) -> InvokeResult:
    """通过 REST API 调用检测模型并判定安全性。"""
    start = time.perf_counter()
    body = render_body_template(model.body_template or {}, content)
    headers = model.headers or {"Content-Type": "application/json"}
    method = (model.http_method or "POST").upper()
    req_detail = json.dumps(
        {"url": model.endpoint_url, "method": method, "body": body},
        ensure_ascii=False,
    )

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            if method == "GET":
                resp = await client.get(
                    model.endpoint_url, headers=headers, params=body
                )
            else:
                resp = await client.request(
                    method, model.endpoint_url, headers=headers, json=body
                )
        latency = (time.perf_counter() - start) * 1000

        # 解析响应体（尽量按 JSON 解析）
        try:
            resp_json = resp.json()
        except Exception:
            resp_json = {"_raw": resp.text}
        resp_detail = json.dumps(
            {"status_code": resp.status_code, "body": resp_json},
            ensure_ascii=False,
        )[:4000]

        safe = _judge_rest_safe(model, resp.status_code, resp_json)
        prompt_msg = ""
        if not safe:
            prompt_msg = _extract_rest_prompt(model, resp_json)

        return InvokeResult(
            safe=safe,
            status="safe" if safe else "unsafe",
            prompt_message=prompt_msg,
            request_detail=req_detail,
            response_detail=resp_detail,
            latency_ms=latency,
        )
    except (httpx.TimeoutException, asyncio.TimeoutError):
        latency = (time.perf_counter() - start) * 1000
        return InvokeResult(
            safe=False,
            status="timeout",
            request_detail=req_detail,
            response_detail="请求超时",
            latency_ms=latency,
        )
    except Exception as exc:  # 网络/连接等错误
        latency = (time.perf_counter() - start) * 1000
        return InvokeResult(
            safe=False,
            status="error",
            request_detail=req_detail,
            response_detail=f"调用异常: {exc}",
            latency_ms=latency,
        )


def _judge_rest_safe(model: DetectionModel, status_code: int, body: Any) -> bool:
    """
    REST「安全」判定：
      - 若设置了 safe_status_code，则状态码必须匹配；
      - 若设置了 safe_jsonpath，则提取值需与 safe_expected_value 相等（不区分大小写）。
    两个条件都设置时需同时满足；都未设置时，默认 2xx 视为安全。
    """
    checks_defined = False

    if model.safe_status_code is not None:
        checks_defined = True
        if status_code != model.safe_status_code:
            return False

    if model.safe_jsonpath:
        checks_defined = True
        value = extract_jsonpath(body, model.safe_jsonpath)
        expected = model.safe_expected_value or ""
        if value is None:
            return False
        if str(expected).casefold() != str(value).casefold():
            return False

    if not checks_defined:
        # 未配置任何条件时的兜底规则
        return 200 <= status_code < 300

    return True


def _extract_rest_prompt(model: DetectionModel, body: Any) -> str:
    """从响应体按 prompt_jsonpath 提取不安全提示信息。"""
    if model.prompt_jsonpath:
        value = extract_jsonpath(body, model.prompt_jsonpath)
        if value is not None:
            return str(value)
    return "检测到安全风险"


# ---------------------------------------------------------------------
# Python 脚本接入调用
# ---------------------------------------------------------------------
# 在子进程中执行用户脚本的包装器：导入脚本后调用 detect(content)，
# 约定返回 (code, message)；将结果以 JSON 打印到 stdout。
_SCRIPT_RUNNER = r'''
import sys, json
content = sys.stdin.read()
ns = {}
try:
    exec(compile(_USER_SCRIPT, "<user_script>", "exec"), ns)
    detect = ns.get("detect")
    if detect is None:
        print(json.dumps({"error": "脚本未定义 detect(content) 函数"}))
        sys.exit(0)
    result = detect(content)
    if isinstance(result, (list, tuple)):
        code = result[0]
        msg = result[1] if len(result) > 1 else ""
    else:
        code = result
        msg = ""
    print(json.dumps({"code": code, "message": str(msg)}, ensure_ascii=False))
except Exception as exc:
    print(json.dumps({"error": str(exc)}, ensure_ascii=False))
'''


async def _invoke_script(
    model: DetectionModel, content: str, timeout: float
) -> InvokeResult:
    """
    在独立子进程中执行用户脚本。

    安全说明：脚本在单独的 Python 子进程中运行，与主服务进程隔离；
    生产环境建议进一步配合容器/沙箱限制资源。
    """
    start = time.perf_counter()
    req_detail = f"script detect(content), content_len={len(content)}"

    # 将用户脚本作为变量注入 runner，避免脚本内容被当作 runner 代码解析
    runner = "_USER_SCRIPT = " + repr(model.script_content) + "\n" + _SCRIPT_RUNNER

    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            runner,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(content.encode("utf-8")), timeout=timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            latency = (time.perf_counter() - start) * 1000
            return InvokeResult(
                safe=False,
                status="timeout",
                request_detail=req_detail,
                response_detail="脚本执行超时",
                latency_ms=latency,
            )

        latency = (time.perf_counter() - start) * 1000
        out = stdout.decode("utf-8", "replace").strip()
        err = stderr.decode("utf-8", "replace").strip()

        try:
            # 取最后一行 JSON，容忍脚本中的额外打印
            last_line = out.splitlines()[-1] if out else "{}"
            data = json.loads(last_line)
        except Exception:
            return InvokeResult(
                safe=False,
                status="error",
                request_detail=req_detail,
                response_detail=f"脚本输出解析失败: {out or err}",
                latency_ms=latency,
            )

        if "error" in data:
            return InvokeResult(
                safe=False,
                status="error",
                request_detail=req_detail,
                response_detail=f"脚本错误: {data['error']}",
                latency_ms=latency,
            )

        # 固定规则：第一个返回值为 0 表示安全
        code = data.get("code")
        safe = str(code) == "0"
        msg = data.get("message", "") or ("" if safe else "检测到安全风险")
        return InvokeResult(
            safe=safe,
            status="safe" if safe else "unsafe",
            prompt_message="" if safe else msg,
            request_detail=req_detail,
            response_detail=json.dumps(data, ensure_ascii=False),
            latency_ms=latency,
        )
    except Exception as exc:
        latency = (time.perf_counter() - start) * 1000
        return InvokeResult(
            safe=False,
            status="error",
            request_detail=req_detail,
            response_detail=f"脚本调用异常: {exc}",
            latency_ms=latency,
        )


# ---------------------------------------------------------------------
# 统一入口
# ---------------------------------------------------------------------
async def invoke_model(
    model: DetectionModel, content: str, timeout: float
) -> InvokeResult:
    """根据模型接入方式分派调用，并补充模型元信息。"""
    if model.access_type == "rest":
        result = await _invoke_rest(model, content, timeout)
    else:
        result = await _invoke_script(model, content, timeout)
    result.model_id = model.id
    result.model_name = model.name
    result.access_type = model.access_type
    return result


# ---------------------------------------------------------------------
# 有效性检测
# ---------------------------------------------------------------------
async def validate_model_connectivity(model: DetectionModel) -> dict:
    """REST 模型连接有效性检测：发送一次探测请求，报告状态码。"""
    if model.access_type != "rest":
        return {"ok": False, "message": "非 REST 接入方式，无法进行连接检测"}
    if not model.endpoint_url:
        return {"ok": False, "message": "未配置接口地址"}

    result = await _invoke_rest(model, '[{"role": "user", "content": "Hello"}]', timeout=10.0)
    if result.status in ("safe", "unsafe"):
        return {
            "ok": True,
            "message": "连接成功，接口可访问",
            "detail": result.response_detail,
        }
    return {
        "ok": False,
        "message": "连接失败",
        "detail": result.response_detail,
    }


async def validate_model_script(model: DetectionModel) -> dict:
    """脚本有效性检测：用样例内容试运行脚本，检查是否能正常返回。"""
    if model.access_type != "script":
        return {"ok": False, "message": "非脚本接入方式，无法进行脚本检测"}
    if not model.script_content.strip():
        return {"ok": False, "message": "脚本内容为空"}

    result = await _invoke_script(model, "脚本有效性检测样例文本", timeout=10.0)
    if result.status in ("safe", "unsafe"):
        return {
            "ok": True,
            "message": "脚本可正常执行并返回结果",
            "detail": result.response_detail,
        }
    return {
        "ok": False,
        "message": "脚本执行失败",
        "detail": result.response_detail,
    }
