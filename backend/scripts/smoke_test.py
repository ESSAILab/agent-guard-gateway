"""端到端冒烟测试（使用 TestClient，无需独立启动服务进程）。"""
import json
import os
import sys

# 使用独立测试库，避免污染开发库
os.environ["DATABASE_URL"] = "sqlite:///./smoke_test.db"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

PASS, FAIL = 0, 0


def check(label, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [PASS] {label} {extra}")
    else:
        FAIL += 1
        print(f"  [FAIL] {label} {extra}")


def main():
    # 清理旧测试库
    if os.path.exists("smoke_test.db"):
        os.remove("smoke_test.db")

    with TestClient(app) as c:
        # 登录
        tok = c.post(
            "/api/auth/login",
            data={"username": "admin", "password": "admin123"},
        ).json()["access_token"]
        h = {"Authorization": f"Bearer {tok}"}
        check("登录获取令牌", len(tok) > 20)

        # 内置标签
        tags = c.get("/api/tags", headers=h).json()
        check("内置标签数量为 6", len(tags) == 6, f"got {len(tags)}")

        # 创建脚本模型
        script = (
            "def detect(content):\n"
            "    if '敏感' in content:\n"
            "        return (1, '内容包含敏感词')\n"
            "    return (0, '')"
        )
        m = c.post(
            "/api/models",
            headers=h,
            json={
                "name": "敏感词脚本模型",
                "access_type": "script",
                "script_content": script,
                "tag_ids": [1],
            },
        ).json()
        mid = m["id"]
        check("创建脚本模型", m["access_type"] == "script")
        check("模型关联标签", len(m.get("tags", [])) == 1)

        # 脚本有效性检测
        v = c.post(f"/api/models/{mid}/validate", headers=h).json()
        check("脚本有效性检测通过", v["ok"] is True, v.get("message", ""))

        # 创建策略（sequential 顺序检测）
        s = c.post(
            "/api/strategies",
            headers=h,
            json={
                "name": "个人信息策略",
                "tag_id": 1,
                "rule_type": "sequential",
                "model_ids": [mid],
            },
        ).json()
        sid = s["id"]
        check("创建策略编排", sid is not None)

        # 创建 API Key
        kj = c.post("/api/api-keys", headers=h, json={"name": "测试密钥"}).json()
        kid, kval = kj["id"], kj["key_value"]
        check("生成 API Key", kval.startswith("gk_"))

        # 创建 API 路径
        p = c.post(
            "/api/api-paths",
            headers=h,
            json={
                "name": "聊天输入检测",
                "path": "/chat-input",
                "api_key_id": kid,
                "strategy_ids": [sid],
            },
        ).json()
        check("创建 API 路径", p["path"] == "/chat-input")

        kh = {"X-API-Key": kval}
        # 安全用例
        r = c.post("/guard/chat-input", headers=kh, json={"messages": "你好世界", "jsonpath": ""}).json()
        check("检测-安全内容返回 200", r["code"] == 200, r)
        # 不安全用例
        r = c.post("/guard/chat-input", headers=kh, json={"messages": "这是敏感内容", "jsonpath": ""}).json()
        check("检测-敏感内容判不安全", r["code"] == 4030, r)
        check("不安全提示信息正确", r["message"] == "内容包含敏感词", r)
        check("风险类型为个人信息检测", r["risk_type"] == "个人信息检测", r)
        # JsonPath 提取
        r = c.post("/guard/chat-input", headers=kh, json={"messages": '{"text":"含敏感词内容"}', "jsonpath": "$.text"}).json()
        check("JsonPath 提取后判不安全", r["code"] == 4030, r)
        # JsonPath 提取失败 -> 不安全
        rr = c.post("/guard/chat-input", headers=kh, json={"messages": '{"text":"x"}', "jsonpath": "$.missing", "illegal_status_code": 403})
        check("JsonPath 失败返回不安全", rr.json()["code"] == 4001, rr.json())
        check("非法时按指定状态码返回 403", rr.status_code == 403, rr.status_code)
        # 错误 Key
        bad = c.post("/guard/chat-input", headers={"X-API-Key": "wrong"}, json={"messages": "x"})
        check("错误 API Key 返回 401", bad.status_code == 401)

        # 统计
        st = c.get("/api/observability/stats", headers=h).json()
        check("统计-总请求数 > 0", st["total_requests"] > 0, st["total_requests"])
        check("统计-不安全计数 > 0", st["unsafe_count"] > 0)
        # 检测日志
        dl = c.get("/api/observability/detection-logs", headers=h).json()
        check("检测模型调用日志已记录", len(dl) > 0, f"count={len(dl)}")

    print(f"\n结果：通过 {PASS}，失败 {FAIL}")
    if os.path.exists("smoke_test.db"):
        os.remove("smoke_test.db")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
