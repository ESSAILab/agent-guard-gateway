# Content Security Guard — Higress 插件

基于 [Higress](https://higress.io/) Go/Wasm 机制开发的内容安全检测插件。插件挂载在 AI 网关的请求处理阶段，从 OpenAI 风格请求体中提取 `messages` 字段，调用 AI 智能体安全网关的对外检测接口（`POST /guard{path}`），当检测结果为不安全时，直接由网关返回预设回复，阻断请求继续转发到大模型。

## 工作流程

1. 拦截进入网关的请求体，按 OpenAI 格式提取 `messages`；
2. 将消息内容 POST 到护栏网关配置的检测路径；
3. 检测服务返回 `code == 200` 时放行（`ResumeHttpRequest`）；
4. 返回其他业务码时，使用配置的 `unsafeResponse` 构造一条 OpenAI 风格响应直接回复调用方；
5. 检测服务不可达或响应异常时默认放行，避免安全服务故障影响主链路。

## 插件配置

| 字段 | 类型 | 说明 |
|------|------|------|
| `serviceName` | string | 护栏检测服务的服务名（Higress/MCP 服务注册名） |
| `port` | int | 护栏检测服务端口 |
| `requestPath` | string | 护栏对外检测路径，如 `/guard/prompt-guard` |
| `unsafeResponse` | string | 判定不安全时返回给调用方的回复文本 |

配置示例：

```json
{
  "serviceName": "contentcheck.static",
  "port": 8000,
  "requestPath": "/guard/prompt-guard",
  "unsafeResponse": "我不能回答此类问题。"
}
```

`envoy.yaml` 提供了本地 Envoy + Wasm 的调试样例（服务地址、集群配置按实际环境修改）。

## 编译

需要 Go 1.24+，并使用 Higress 提供的 Wasm 构建工具链：

```bash
# 在本目录下执行（首次运行会自动下载构建工具）
go run github.com/higress-group/wasm-go@latest build
```

产物为 `main.wasm`。可使用本目录的 `Dockerfile` 构建包含插件的 OCI 镜像，或通过 `docker-compose.yaml` 在本地 Envoy 中调试。

## 部署

将编译得到的 `main.wasm` 按 Higress 的 Wasm 插件机制配置到对应路由/域名上，并填写上述插件配置。使用前请先在护栏管理后台：

1. 创建检测模型与策略（顺序/随机）；
2. 创建对外检测路径（如 `/prompt-guard`）并绑定策略链与 API Key（如需 API Key 认证，可在自定义请求头中携带 `X-API-Key`）。

## 许可

本插件代码遵循仓库根目录 [LICENSE](../../../../LICENSE)（仅限研究目的）。Higress、proxy-wasm-go-sdk 等第三方组件版权归原版权方所有，遵循其各自开源许可证。
