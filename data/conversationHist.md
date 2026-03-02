# ASRtoLLM 项目对话记录

## Conversation 1 (32 messages)

### Task 1: 项目初始化 — Flask + 前端 Web App
- 搭建 Flask 后端 + 原生 HTML/JS 前端，接受音视频文件，调用 ASR 转写后送 LLM 生成摘要
- 端口从 5000 改为 8080（macOS AirPlay 占用 5000）
- 文件：`app.py`, `static/index.html`, `requirements.txt`

### Task 2: 供应商凭证管理（动态字段）
- `app.py` 中 VENDORS 字典定义每个供应商的凭证字段，`secret: False` 的字段明文显示
- 密钥字段用 `type="text"` + CSS `-webkit-text-security: disc`（避免 macOS 切换输入法）
- 凭证自动保存到 localStorage，ASR/LLM 下拉框只显示凭证完整的供应商
- 供应商区域可折叠

### Task 3: Git 初始化与推送
- 创建 `.gitignore` 和 `README.md`，推送到 `https://github.com/taoxee/ASRtoLLM.git`

### Task 4: 任务输出目录
- 每次任务保存到 `output/<YYYYMMDD_HHMMSS_shortid>/`
- 包含：`meta.json`, `transcript.txt`, `summary.txt`, `asr_log.json`, `llm_log.json`, `source_<filename>`
- 添加 `/api/tasks` 和 `/api/tasks/<task_id>` 接口，前端有可折叠"历史任务"区域

### Task 5: 代理自动检测
- `_detect_proxy()` 通过 `scutil --proxy` 读取 macOS 系统代理
- 所有 API 调用使用共享 `requests.Session()` 配置代理
- 依赖 `requests[socks]`

### Task 6: SSE 进度条 + 分步预览
- `/api/process` 使用 Server-Sent Events 流式返回
- 前端显示进度条、步骤指示器，转写和摘要结果逐步展示

### Task 7: 重复文件缓存检测
- `_find_cached()` 在 `output/` 中查找相同文件名+供应商组合的历史结果
- 命中缓存时显示"✅ 命中缓存"

### Task 8: 说话人分离 + 会议纪要（核心功能转型）
- 从通用"摘要"转型为说话人分离 + 结构化会议纪要
- 创建 `ASR_prompt.txt` 和 `LLM_prompt.txt`，启动时加载
- ASR 输出结构化 JSON：`{metadata, segments}`，每段含 speaker/start_time/end_time/text
- LLM 接收分离后的 JSON，输出 Markdown 会议纪要
- 前端：说话人标签彩色显示（5色），摘要渲染 Markdown
- UI 标签更新："智能摘要"→"会议纪要"，"语音转文字"→"语音转文字 + 说话人分离"

### Task 9: 全部 11 个 ASR 供应商实现
- **OpenAI** — Whisper，OpenAI 兼容 API（verbose_json，单说话人）
- **Groq** — Whisper-large-v3，OpenAI 兼容 API
- **Deepgram** — Nova-2，原生分离（`diarize=true&utterances=true`）
- **ElevenLabs** — Scribe v1，分离 + 3次重试 + 代理回退
- **Soniox** — 异步上传 API，`enable_speaker_diarization`
- **火山云** — openspeech.bytedance.com submit+query API
- **腾讯云** — TC3-HMAC-SHA256 签名，`CreateRecTask` + 轮询，`SpeakerDiarization=1`
- **微软-Global** — Azure Fast Transcription REST API + `diarizationSettings`，Key + Region（默认 eastus）
- **微软-世纪互联** — 同 Global，中国端点（`{region}.api.cognitive.azure.cn`）
- **阿里云** — DashScope Paraformer-v2，OSS 上传凭证 API，`diarization_enabled=true`
- **讯飞** — raasr.xfyun.cn v2 API，分块上传，HMAC-SHA1 签名

### Task 10: 全部 7 个 LLM 供应商实现
- OpenAI (gpt-4o), Groq (llama-3.3-70b), 智谱 (glm-4-flash), Minimax-CN, Minimax-Global, 腾讯云 (deepseek-v3), 阿里云 (qwen-plus)

### Task 11: 凭证导入/导出/清除按钮
- 📥 一键导入凭证 — 调用 `/api/import-keys`（`import_keys.py` 自动检测环境变量/.env/vendor_keys.csv）
- 📁 从文件导入（CSV/JSON）— 自动识别格式
- 📤 导出凭证 — 下载 `vendor_creds.json`
- 🗑️ 清除所有凭证 — 清除 localStorage
- 创建 `import_keys.py`

### Task 12: 供应商字段调整
- 讯飞：添加 `language` 字段，默认 `autodialect`
- 微软-Global：简化为 Key + Region（移除密钥2/终结点）

### Task 13: 双语 README + Star History
- README 改为中英双语，含功能亮点、分离支持表、使用说明、输出结构、Star History 图表

### Task 14: 推荐提示横幅
- 页面顶部可关闭提示条："ASR 推荐 Deepgram，LLM 推荐 阿里云"
- 关闭后 localStorage 记住状态

### 用户纠正与偏好
- 端口 8080（非 5000）
- 不用 `type="password"`，用 CSS 遮罩
- 系统代理自动检测（ShadowsocksX-NG）
- zsh 中 `pip install 'requests[socks]'` 需引号
- 位置/区域/终结点/url 字段明文显示
- 供应商区域可折叠，上传功能突出
- 下拉框只显示凭证完整的供应商
- 微软-Global 只有 Key + Region
- 不自动 push，用户控制推送时机
- 目标是会议纪要（非字幕生成）

---

## Conversation 2 (3 messages)

### Task: 提交未暂存更改
- 将 Conversation 1 末尾未提交的更改（ElevenLabs 重试修复 + 推荐提示横幅）提交为 `21d17c4`
- 提交信息：`feat: add recommendation tip banner + ElevenLabs retry fix`
- 涉及文件：`app.py`, `static/index.html`, `LLM_prompt.txt`

### Task: 对话记录
- 将两次对话的完整摘要写入 `conversationHist.md`

### Git 状态
- 本地 main 领先 origin/main 4 个 commit（推送后同步）
- 最新 commit：`21d17c4`

---

## Conversation 3 (8 messages)

### Task 1: 多任务并行队列 + Token 用量记录
- 后端：`app.py` 新增 `threading` + `OrderedDict` 任务队列，`_task_lock` 线程安全，`/api/queue` 端点
- LLM handlers 改为返回 `(content, token_info)` 元组，`token_info` 含 model/prompt_tokens/completion_tokens/total_tokens
- Token 用量保存到 `meta.json` 的 `token_usage` 字段和 `llm_log.json`
- 前端：文件选择支持多选（`multiple`），前端维护 `taskQueue` 对象，最多 `MAX_PARALLEL=3` 个任务并行
- 每个任务独立 SSE 流，队列 UI 显示各任务状态/进度/token 用量
- 历史任务列表也显示 token 用量
- 文件：`app.py`, `static/index.html`

### Task 2: 处理结果显示文件名
- 结果卡片顶部新增 `#result-filename` 元素，显示 `📄 filename`
- 实时处理和历史任务加载均显示对应文件名

### Task 3: 任务队列可折叠 + 完成通知
- 任务队列标题可点击折叠/展开，显示任务计数（进行中/已完成/总数）
- 任务完成或失败时右上角弹出通知横幅（`.task-notify`）
- 通知 10 秒后自动消失，点 ✕ 可立即关闭
- 点击通知跳转到对应任务的处理结果

### Git 状态
- 提交 `c12de11`：`feat: multi-task queue with parallel processing, token usage tracking, collapsible queue, completion notifications`
- 已推送到 origin/main
