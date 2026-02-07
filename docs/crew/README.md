# Crew 工作流

本目录记录 Crew 工作流的配置与说明。

## 配置

默认配置位于 `config/crewai.json`，示例字段：

- `provider`: LLM 提供方名称（例如 `minimax`）。
- `model`: 模型名称（建议使用 `provider/model` 格式，例如 `minimax/abab6`）。
- `api_key_env`: 从环境变量读取 API Key 的名称（不会在仓库中保存密钥）。
- `base_url`: 可选的 API Base URL（如 Minimax 中国版）。
- `temperature`: 可选采样温度。
- `max_tokens`: 可选最大输出 token。

### 凭证模式

- **API Key（默认）**：`auth_mode: "api_key"` + `api_key_env: "OPENAI_API_KEY"` 等。
- **OAuth Token**：`auth_mode: "oauth"` + `credential_env: "MY_OAUTH_TOKEN"`（未提供时会回落到 `api_key_env`）。

> 运行脚本会自动读取主模型的 `credential_env` 并校验对应环境变量。OAuth 模式下，如果未检测到本地 token，会启动本地登录流程并在重定向后自动保存 token 至 `~/.projectmanager_tokens/<env>.txt`，后续运行将直接复用。

> 建议通过环境变量配置密钥，例如：
> `export MINIMAX_API_KEY=your_key`

## 运行

```bash
python -m src crew_run --title "..." --request-type new_requirement --details "..." --auto-confirm
```

也可使用 JSON 文件：

```bash
python -m src crew_run --request docs/crew/request.json --auto-confirm
```

## 输出

- 任务记录：`docs/tasks.md`
- CrewAI 生成测试用例：`docs/test_cases_crew.md`
