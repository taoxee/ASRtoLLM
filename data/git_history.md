## 83f0400 2026-03-03
**docs: add vendor API key prerequisites section to README CN/EN**


 README_CN.md | 15 +++++++++++++++
 README_EN.md | 15 +++++++++++++++
 2 files changed, 30 insertions(+)

## d795105 2026-03-03
**docs: update conversationHist with Conversation 7 completion and Conversation 8 summary**


 data/conversationHist.md | 30 ++++++++++++++++++++++++++++--
 1 file changed, 28 insertions(+), 2 deletions(-)

## 704737e 2026-03-03
**feat: update branding to VibeMeet2Notes/灵感纪要, fix license to Apache 2.0, add footer author link**


 LICENSE           |  2 +-
 README.md         |  6 +++++-
 README_CN.md      |  4 ++--
 README_EN.md      |  4 ++--
 static/index.html | 14 +++++++++-----
 5 files changed, 19 insertions(+), 11 deletions(-)

## 640031e 2026-03-03
**fix: translate Minimax-CN api_key label from 接口密钥 to Key**


 app/config.py | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)

## 90c12ee 2026-03-03
**fix: i18n completeness - toggle text, task notifications, page title, vendor names**


 data/conversationHist.md |  18 +++
 static/index.html        | 292 ++++++++++++++++++++++++++++-------------------
 2 files changed, 194 insertions(+), 116 deletions(-)

## 9daeaf9 2026-03-03
**docs: add multi-language UI feature to README**


 README_CN.md | 1 +
 README_EN.md | 1 +
 2 files changed, 2 insertions(+)

## f35e112 2026-03-03
**feat: add i18n support with language switcher (Chinese/English)**


 data/conversationHist.md |  34 ++++-
 static/index.html        | 370 +++++++++++++++++++++++++++++++++++++++++++----
 2 files changed, 374 insertions(+), 30 deletions(-)

## 047e271 2026-03-03
**docs: fix repo name in Star History badges, translate vendor names in README_EN**


 README.md    |  2 +-
 README_CN.md |  2 +-
 README_EN.md | 28 ++++++++++++++--------------
 3 files changed, 16 insertions(+), 16 deletions(-)

## 341d22e 2026-03-03
**docs: add bilingual README split, update conversation history**


 README.md                | 121 ++---------------------------------------
 README_CN.md             | 138 +++++++++++++++++++++++++++++++++++++++++++++++
 README_EN.md             | 138 +++++++++++++++++++++++++++++++++++++++++++++++
 data/conversationHist.md |  37 +++++++++++++
 4 files changed, 317 insertions(+), 117 deletions(-)

## a6df32c 2026-03-03
**change proj name**

Signed-off-by: Tao <61774203+taoxee@users.noreply.github.com>
 README.md | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)

## a618614 2026-03-03
**change proj name**

Signed-off-by: Tao <61774203+taoxee@users.noreply.github.com>
 README.md | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)

## db713a3 2026-03-02
**docs: update README with new project structure, update conversation history**


 ASR_prompt.txt           |  28 ----------
 LLM_prompt.txt           |  20 -------
 README.md                |  27 +++++++++-
 conversationHist.md      | 132 -----------------------------------------------
 data/conversationHist.md |  21 ++++++++
 vendor_keys.csv          |  15 ------
 6 files changed, 47 insertions(+), 196 deletions(-)

## 6e42f2d 2026-03-02
**refactor: split monolithic app.py into modular structure (app/config, utils, services, routes)**


 app/__init__.py           |  12 +
 app/config.py             | 178 +++++++++++++++
 app/routes.py             | 252 ++++++++++++++++++++
 app.py => app/services.py | 569 ++++++----------------------------------------
 app/utils.py              |  48 ++++
 data/ASR_prompt.txt       |  28 +++
 data/LLM_prompt.txt       |  20 ++
 data/conversationHist.md  | 132 +++++++++++
 data/vendor_keys.csv      |  15 ++
 run.py                    |   7 +
 10 files changed, 758 insertions(+), 503 deletions(-)

## 42c7cb1 2026-03-02
**docs: update conversation history with conversation 3**


 conversationHist.md | 27 +++++++++++++++++++++++++++
 1 file changed, 27 insertions(+)

## c12de11 2026-03-02
**feat: multi-task queue with parallel processing, token usage tracking, collapsible queue, completion notifications**


 app.py            |  82 +++++++++++---
 static/index.html | 320 ++++++++++++++++++++++++++++++++++++++++--------------
 2 files changed, 308 insertions(+), 94 deletions(-)

## 2c651c0 2026-02-28
**docs: add conversation history summary**


 conversationHist.md | 105 ++++++++++++++++++++++++++++++++++++++++++++++++++++
 1 file changed, 105 insertions(+)

## 21d17c4 2026-02-28
**feat: add recommendation tip banner + ElevenLabs retry fix**


 LLM_prompt.txt    |  1 +
 app.py            | 59 +++++++++++++++++++++++++++++++++++++++++++------------
 static/index.html | 13 ++++++++++++
 3 files changed, 60 insertions(+), 13 deletions(-)

## 7627fb7 2026-02-28
**fix: aliyun ASR use DashScope OSS upload instead of base64**

- DashScope does not support base64 or direct file upload
- Use upload credential API to upload file to DashScope OSS first
- Then submit oss:// URL for paraformer-v2 transcription
- Fixes MaxStringLength error for large audio files

 .gitignore |   1 +
 app.py     | 109 +++++++++++++++++++++++++++++++++++++++++++++----------------
 2 files changed, 81 insertions(+), 29 deletions(-)

## 14725ac 2026-02-28
**feat: implement all remaining ASR handlers + vendor field updates**

- Add 讯飞 ASR (raasr.xfyun.cn v2 API, chunked upload, speaker diarization)
- Add 阿里云 ASR (DashScope Paraformer HTTP API, async transcription)
- Add 微软-世纪互联 ASR (Azure China Fast Transcription API)
- Add 微软-Global ASR (Azure Global Fast Transcription API)
- All 9 ASR vendors now fully implemented with diarization
- All 7 LLM vendors fully implemented
- 讯飞: add language field (default: autodialect)
- 微软-Global: simplify to Key + Region (default: eastus)
- Update credential import/file-import to support CSV auto-detection

 LLM_prompt.txt      |   2 +-
 app.py              | 386 ++++++++++++++++++++++++++++++++++++++++++++++++++--
 conversationHist.md |   0
 import_keys.py      |   2 +-
 static/index.html   |  81 ++++++++++-
 5 files changed, 453 insertions(+), 18 deletions(-)

## 297eb3a 2026-02-28
**feat: credential management - clear all, import (auto-detect/file/export)**

- Add 'clear all keys' button to wipe localStorage credentials
- Add 'one-click import' via /api/import-keys (env vars, .env, CSV)
- Add 'import from JSON file' for manual credential restore
- Add 'export credentials' to download vendor_creds.json
- Create import_keys.py: auto-detect keys from env vars, .env, vendor_keys.csv
- Add vendor_creds.json to .gitignore

 .gitignore        |   1 +
 app.py            |  13 +++
 import_keys.py    | 240 ++++++++++++++++++++++++++++++++++++++++++++++++++++++
 static/index.html | 104 +++++++++++++++++++++++
 4 files changed, 358 insertions(+)

## 0aeb470 2026-02-28
**docs: bilingual README (CN/EN) with star history**


 README.md | 99 +++++++++++++++++++++++++++++++++++++++++++++++++++++----------
 1 file changed, 84 insertions(+), 15 deletions(-)

## 9b7edb6 2026-02-28
**feat: speaker diarization + meeting minutes**

- Add ASR_prompt.txt and LLM_prompt.txt for structured prompts
- Enable speaker diarization for Deepgram, ElevenLabs, Soniox, 腾讯云
- Structured JSON transcript output with speaker labels and timestamps
- LLM now generates Markdown meeting minutes instead of generic summary
- Implement 腾讯云 ASR handler (TC3-HMAC-SHA256 signing)
- Frontend renders diarized segments with color-coded speakers
- Frontend renders Markdown meeting minutes with proper formatting
- Update UI labels: 智能摘要→会议纪要, add 说话人分离 indicator

 .gitignore        |   1 +
 ASR_prompt.txt    |  28 +++
 LLM_prompt.txt    |  19 ++
 app.py            | 738 +++++++++++++++++++++++++++++++++++++++++++++++++++---
 requirements.txt  |   1 +
 static/index.html | 326 ++++++++++++++++++++++--
 6 files changed, 1046 insertions(+), 67 deletions(-)

## 8bc80c1 2026-02-28
**init: ASRtoLLM media transcription and summarization tool**


 .gitignore            |  12 ++
 .vscode/settings.json |   2 +
 README.md             |  44 ++++++-
 app.py                | 328 ++++++++++++++++++++++++++++++++++++++++++++++++++
 requirements.txt      |   5 +
 static/index.html     | 320 ++++++++++++++++++++++++++++++++++++++++++++++++
 vendor_keys.csv       |  15 +++
 7 files changed, 725 insertions(+), 1 deletion(-)

## 37a0ef2 2026-02-28
**Initial commit**


 LICENSE   | 201 ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
 README.md |   1 +
 2 files changed, 202 insertions(+)
