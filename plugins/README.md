# Plugins

适配各类 AI 网关 / API 网关的护栏插件，使内容安全检测能力可以在网关侧无感接入。

| 目录 | 适配网关 | 说明 |
|------|----------|------|
| [`higress/content-security-guard/`](higress/content-security-guard/) | [Higress](https://higress.io/) | Go/Wasm 插件，请求经网关时调用护栏检测接口，不安全请求直接拦截 |
