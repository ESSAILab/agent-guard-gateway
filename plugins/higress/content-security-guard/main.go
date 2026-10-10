package main

import (
	"encoding/json"
	"net/http"

	"github.com/higress-group/proxy-wasm-go-sdk/proxywasm"
	"github.com/higress-group/proxy-wasm-go-sdk/proxywasm/types"
	logs "github.com/higress-group/wasm-go/pkg/log"
	"github.com/higress-group/wasm-go/pkg/wrapper"
	"github.com/tidwall/gjson"
)

func main() {}

func init() {
	wrapper.SetCtx(
		"content-security-guard",
		wrapper.ParseConfigBy(parseConfig),
		wrapper.ProcessRequestBodyBy(onHttpRequestBody),
	)
}

/*
配置示例
{
	"serviceName": "contentcheck.static",
	"port": 8000,
	"requestPath": "/guard/prompt-guard",
	"unsafeResponse": "我不能回答此类问题。"
}
*/

type MyConfig struct {
	// 内容安全服务名称
	serviceName string
	// 端口号
	port int64
	// 请求路径
	requestPath string

	// 不安全响应字符串
	unsafeResponse string
	// 用于发送HTTP请求的client
	client wrapper.HttpClient
}

func parseConfig(json gjson.Result, config *MyConfig, log logs.Log) error {
	log.Debugf("Content security guard config: %s", json.String())
	config.serviceName = json.Get("serviceName").String()
	config.port = json.Get("port").Int()
	config.requestPath = json.Get("requestPath").String()
	config.unsafeResponse = json.Get("unsafeResponse").String()
	// 创建工作模型客户端
	config.client = wrapper.NewClusterClient(wrapper.FQDNCluster{
		FQDN: config.serviceName,
		Port: config.port,
	})

	return nil
}

// 定义用于构建JSON请求的结构体
type Request struct {
	Messages string `json:"messages"`
}

// 最终响应结构体
type Response struct {
	Choices []Choice `json:"choices"`
}

type Choice struct {
	Message struct {
		Role    string `json:"role"`
		Content string `json:"content"`
	} `json:"message"`
}

// 检查响应结构体
type CheckResponse struct {
	Code     int    `json:"code"`
	Message  string `json:"message"`
	RiskType string `json:"risk-type"`
}

func onHttpRequestBody(ctx wrapper.HttpContext, config MyConfig, body []byte, log logs.Log) types.Action {
	// 按照OpenAi的格式解析请求体，提取messages字段
	messages := gjson.GetBytes(body, "messages").String()
	if len(messages) > 1024 {
		log.Debugf("Content security guard extracted messages: %s...", messages[:1024])
	} else {
		log.Debugf("Content security guard extracted messages: %s", messages)
	}

	// 构建请求消息
	request := Request{
		Messages: messages,
	}
	requestHeaders := [][2]string{{"Content-Type", "application/json"}}

	requestBody, err := json.Marshal(request)
	if err != nil {
		log.Infof("Content security guard error occurred while marshaling request, err: %v", err)
		return types.ActionContinue
	}

	// TODO: handle request header errors
	err = config.client.Post(config.requestPath, requestHeaders, requestBody,
		// 回调函数，将在响应异步返回时被执行
		func(statusCode int, responseHeaders http.Header, responseBody []byte) {
			// 打印响应的HTTP状态码和应答body
			log.Debugf("Content security guard get status: %d, response body: %s", statusCode, responseBody)
			// 请求没有返回200状态码，进行处理
			if statusCode != http.StatusOK {
				log.Errorf("Content security guard call check service failed, status: %d", statusCode)
				proxywasm.ResumeHttpRequest()
			} else {
				// 解析Json格式的响应体，取出code字段、message字段
				var checkResponse CheckResponse
				err := json.Unmarshal(responseBody, &checkResponse)
				if err != nil {
					log.Warnf("Content security guard error occurred while unmarshaling response, err: %v", err)
					proxywasm.ResumeHttpRequest()
					return
				}

				// 响应消息中包含Code字段，取值为200时表明安全，继续处理
				if checkResponse.Code == 200 {
					log.Debugf("Content security guard content is safe, code: %d, message: %s", checkResponse.Code, checkResponse.Message)
					proxywasm.ResumeHttpRequest()
					return
				} else {
					log.Infof("Content security guard content is unsafe, code: %d, message: %s", checkResponse.Code, checkResponse.Message)
					var response Response
					response.Choices = []Choice{
						{
							Message: struct {
								Role    string `json:"role"`
								Content string `json:"content"`
							}{
								Role:    "assistant",
								Content: config.unsafeResponse,
							},
						},
					}
					responseBody, err = json.Marshal(response)
					if err != nil {
						log.Errorf("Error occurred while marshaling response, err: %v", err)
						return
					}
					proxywasm.SendHttpResponse(http.StatusOK, [][2]string{{"Content-Type", "application/json"}}, responseBody, -1)
				}
			}
		}, 600000)

	// 处理HTTP调用错误
	if err != nil {
		log.Errorf("Content security guard trigger check service failed, error occurred while calling http, err: %v", err)
		return types.ActionContinue
	} else {
		log.Infof("Content security guard call check service success")
		return types.ActionPause
	}
}
