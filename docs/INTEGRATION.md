# AI智能体安全网关 - 集成指南

本文档面向需要将护栏系统集成到 AI 应用的开发者。

## 集成流程

### 1. 获取 API Key

登录管理后台（默认 http://localhost:8000），进入「令牌管理」，生成一个新的密钥。

记录生成的密钥值（格式为 `gk_xxxxxxxxxx`），后续请求需在 HTTP 头中携带。

### 2. 配置检测路径

在「检测场景」中创建对外检测路径，例如：

- **名称**：聊天输入检测
- **对外路径**：`/chat-input`
- **认证密钥**：选择刚创建的 API Key
- **策略链**：选择一个或多个策略编排，按顺序执行

保存后，该路径对外暴露为 `POST /guard/chat-input`。

### 3. 调用检测接口

#### Python 示例

```python
import requests

GUARDRAIL_URL = "http://localhost:8000"
API_KEY = "gk_xxxxxxxxxx"

def check_content(content: str) -> dict:
    """调用护栏检测接口，返回检测结果。"""
    response = requests.post(
        f"{GUARDRAIL_URL}/guard/chat-input",
        headers={"X-API-Key": API_KEY, "Content-Type": "application/json"},
        json={
            "messages": content,
            "jsonpath": "",
            "illegal_status_code": 403  # 不安全时返回 403
        }
    )
    return response.json()

# 使用示例
result = check_content("用户输入的文本")
if result["code"] == 200:
    print("✓ 检测通过，安全")
else:
    print(f"✗ 检测不通过：{result['message']}")
    print(f"风险类型：{result['risk_type']}")
```

#### JavaScript/Node.js 示例

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
      // 检测不通过
      return error.response.data;
    }
    throw error;
  }
}

// 使用示例
checkContent('用户输入的文本').then(result => {
  if (result.code === 200) {
    console.log('✓ 检测通过，安全');
  } else {
    console.log(`✗ 检测不通过：${result.message}`);
    console.log(`风险类型：${result.risk_type}`);
  }
});
```

#### cURL 示例

```bash
curl -X POST http://localhost:8000/guard/chat-input \
  -H "Content-Type: application/json" \
  -H "X-API-Key: gk_xxxxxxxxxx" \
  -d '{
    "messages": "用户输入的文本",
    "jsonpath": "",
    "illegal_status_code": 403
  }'
```

## 请求参数详解

### `messages`（必填）

被检测的消息内容，可以是：
- 纯文本字符串
- JSON 字符串（配合 `jsonpath` 使用）

### `jsonpath`（可选）

从 `message` 中提取实际检测内容的 JsonPath 表达式。

**示例场景**：AI 应用的完整请求体是复杂 JSON，只需检测其中某个字段。

```json
{
  "messages": "{\"user_input\":\"这是用户输入\",\"context\":\"上下文\"}",
  "jsonpath": "$.user_input"
}
```

此时护栏仅检测 `user_input` 字段的值，而非整个 JSON。

留空则检测整个 `messages`。

### `illegal_status_code`（可选）

当检测结果为不安全时，希望护栏返回的 HTTP 状态码。

- 默认：`200`（业务码 `code` 区分安全/不安全）
- 常用：`403`（便于与其他中间件集成，按 HTTP 状态码拦截）

## 响应格式

无论检测结果如何，响应体格式一致：

```json
{
  "code": 200,          // 业务码：200 安全，4030 不安全，4001 提取失败
  "risk_level": "NONE", // 风险等级：安全为 NONE，不安全为 HIGH，提取失败为 LOW
  "message": "...",     // 提示信息
  "risk_type": "..."    // 风险类型（不安全时非空）
}
```

- `code == 200`：安全，可放行
- `code == 4030`：检测到风险，建议拦截
- `code == 4001`：JsonPath 提取失败（message 不是合法 JSON 或路径不匹配）

## 高级场景

### 场景一：仅检测 LLM 输出

创建策略编排时，选择「仅检测输出」方向的标签，将该策略绑定到独立的 API 路径（如 `/chat-output`）。

在 LLM 生成回复后、返回给用户前调用该路径。

### 场景二：多阶段检测（输入 + 输出）

创建两条 API 路径：
- `/guard/input`：绑定输入策略编排链
- `/guard/output`：绑定输出策略编排链

在请求 LLM 之前调用 `/guard/input`，在收到 LLM 回复后调用 `/guard/output`。

### 场景三：异步检测

如果业务对延迟极其敏感，可：
1. 同步快速返回 LLM 结果给用户
2. 异步调用护栏检测，记录不安全案例用于审计或后处理

护栏本身已做并发优化，典型耗时在 100-500ms（取决于策略配置）。

## 错误处理

| HTTP 状态 | 说明 | 处理建议 |
|-----------|------|----------|
| 200 | 检测完成，根据 `code` 判断结果 | 正常处理 |
| 401 | API Key 无效或缺失 | 检查 `X-API-Key` 头 |
| 403 | API Key 被禁用 或 路径未生效 | 联系管理员 |
| 404 | 对外路径不存在 | 检查请求路径是否正确 |
| 500 | 服务端错误 | 重试或联系运维 |

## 性能优化建议

1. **复用 HTTP 连接**：使用连接池（如 Python 的 `requests.Session`）
2. **设置合理超时**：建议 5-10 秒（与策略的 `max_wait_seconds` 保持一致）
3. **选择合适的策略规则**：
   - 顺序检测：逐个调用模型池，快速失败，适合需要多重冗余保障的高吞吐场景；将更严格/更快的检测模型排在策略前面以尽早拦截
   - 随机检测：每次从可相互替代的冗余模型池中随机选取 1 个调用，成本固定、防护面不确定，适合低成本抽检

## 可观测与监控

- **请求日志**：管理后台「检测记录」，可按路径、结果过滤
- **检测模型日志**：每个检测模型的调用明细与耗时
- **实时大屏**：http://localhost:8000/#/dashboard，观察检测流程

## 常见问题

**Q：护栏检测失败（超时/异常）时，如何处理？**

A：根据业务场景决定：
- 保守策略：检测失败视为不安全，拦截请求
- 宽松策略：检测失败则放行，记录日志供后续审计

护栏的 `timeout_policy` 配置项控制单模型超时时的计入方式（safe / unsafe）。

**Q：如何减少误判？**

A：
1. 将更严格/更快的检测模型排在策略前面，以尽早拦截并减少后续调用
2. 接入多个来源的检测模型（如商业服务 + 自研脚本），按顺序组成检测链
3. 定期回顾可观测日志，调整策略参数与模型顺序

**Q：能否动态修改策略而不重启服务？**

A：可以。管理后台的配置立即生效，无需重启。

---

**更多文档**

- [项目说明与快速开始](../README.md)
- [系统架构与设计原理](./ARCHITECTURE.md)
- [API 参考文档](http://localhost:8000/docs)
