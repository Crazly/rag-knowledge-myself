# RAG 个人知识库

基于 RAG（检索增强生成）的个人知识管理系统。支持多种文档格式的自动解析、语义检索和流式 AI 问答。

## 系统架构

```
┌──────────────────────────────────┐
│         FastAPI 单体应用           │
│                                  │
│  • 前端 (Jinja2 + HTMX + SSE)    │
│  • RAG 管道 (LlamaIndex)         │
│  • 定时任务 (APScheduler)         │
│                                  │
│  FAISS 向量存储    SQLite 元数据   │
└──────────────────────────────────┘
      │              │
 ┌────▼────┐   ┌────▼────┐
 │BGE-M3   │   │DeepSeek  │
 │嵌入+Rerank│  │V4  API   │
 │硅基流动  │   │         │
 └─────────┘   └─────────┘
```

## 环境要求

- Python 3.12+
- 2GB 内存（Docker 部署）或本地运行 500MB+
- 硅基流动 API Key（BGE-M3 嵌入 + BGE-Reranker 重排序）
- DeepSeek API Key（DeepSeek-V4 对话生成）

## 快速开始

### 1. 克隆与安装

```bash
cd knowledge-base

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置 API Key

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入你的 API Key：

```env
SILICONFLOW_API_KEY=sk-xxxxxxxx
DEEPSEEK_API_KEY=sk-xxxxxxxx
```

| 服务 | 获取地址 | 用途 |
|------|---------|------|
| 硅基流动 | https://siliconflow.cn | BGE-M3 嵌入 + Reranker 重排序 |
| DeepSeek | https://platform.deepseek.com | DeepSeek-V4 对话生成 |

### 3. 启动服务

```bash
# 加载环境变量
export $(cat .env | xargs)

# 启动
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 4. 打开界面

| 页面 | 地址 | 功能 |
|------|------|------|
| 知识问答 | http://127.0.0.1:8000/ | 流式 AI 问答，Enter 发送 |
| 文档管理 | http://127.0.0.1:8000/documents | 上传/查看/删除文档 |
| 系统管理 | http://127.0.0.1:8000/admin | 系统状态、索引重建 |
| API 文档 | http://127.0.0.1:8000/docs | Swagger 调试界面 |

---

## 支持的文件类型

| 类型 | 扩展名 | 解析引擎 |
|------|--------|----------|
| PDF | `.pdf` | PyMuPDF |
| Markdown | `.md`, `.txt` | 直接读取 |
| Excel | `.xlsx` | openpyxl |
| Word | `.docx` | python-docx |
| 网页 | `.html`, URL | trafilatura |

## 上传文档

**方式一：Web 界面**

打开 http://127.0.0.1:8000/documents ，拖拽或选择文件上传。上传后自动触发处理管道：

```
上传 → 解析 → 切片 → BGE-M3 嵌入 → FAISS 向量库
```

处理状态实时更新：`uploaded` → `processing` → `ready` / `failed`

**方式二：批量导入**

```bash
# 导入目录下所有文档
python scripts/import.py ~/Documents/my-notes --recursive

# 不递归子目录
python scripts/import.py ~/Documents/my-notes
```

**方式三：自动扫描**

服务启动后，定时任务每 5 分钟扫描 `data/files/` 目录，自动发现并处理新文件。直接将文件丢入 `data/files/` 目录即可，无需重启。

---

## 问答使用

### Web 界面

打开 http://127.0.0.1:8000/ ，输入问题，点击按钮或按 **Enter** 键发送（Shift+Enter 换行）。答案逐字流式输出。

### API 调用

**JSON 接口（非流式）**

```bash
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"什么是Transformer？","top_k":5}'
```

返回：
```json
{
  "answer": "Transformer是...",
  "sources": [
    {
      "text": "...",
      "document_name": "深度学习笔记.md",
      "page_number": null,
      "score": 0.9521
    }
  ]
}
```

**流式接口（SSE）**

```bash
curl -N -X POST http://127.0.0.1:8000/api/chat/stream \
  -d "question=什么是Transformer&top_k=5"
```

SSE 事件类型：

| 事件 | 含义 |
|------|------|
| `status` | 状态提示（检索中/生成中/命中缓存） |
| `token` | 逐字输出的答案 token |
| `answer` | 完整答案（缓存命中或无结果时） |
| `sources` | 参考来源 HTML |
| `done` | 完成 |
| `error` | 错误信息 |

---

## 检索流程

```
用户提问
  │
  ▼
① BGE-M3 向量化（1024维）
  │
  ▼
② FAISS 粗检索 (Top-20)
  │
  ▼
③ BGE-Reranker-v2-m3 重排序 (精排 Top-5)
  │
  ▼
④ 过滤 score < 0.1 的噪音
  │
  ▼
⑤ 组装 Prompt → DeepSeek-V4 流式生成
  │
  ▼
⑥ 返回答案 + 引用来源
```

### LLM 缓存

相同问题的答案会被缓存到 SQLite。再次提问命中缓存时，直接返回缓存的答案，节省 API 调用费用。

---

## 自治更新

服务运行时自动维护知识库：

| 能力 | 说明 |
|------|------|
| **新文件发现** | 每 5 分钟扫描 `data/files/`，自动处理 |
| **变更检测** | 文件 hash 变化 → 删除旧向量 → 重新处理 |
| **索引重建** | 管理页面「全量重建索引」按钮 |

---

## 配置参考

`app/config.py` 中的可调整参数：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `CHUNK_SIZE` | 1024 | 切片大小（tokens） |
| `CHUNK_OVERLAP` | 128 | 切片重叠量 |
| `RETRIEVAL_TOP_K` | 20 | FAISS 粗检索返回数 |
| `RERANK_TOP_K` | 5 | Reranker 精排后保留数 |
| `LLM_MODEL` | `deepseek-chat` | DeepSeek 模型名 |

---

## 管理 API

### 系统状态

```bash
curl http://127.0.0.1:8000/api/admin/stats
```

返回：文档总数、已就绪数、片段数、向量数、存储空间

### 重建索引

```bash
curl -X POST http://127.0.0.1:8000/api/admin/reindex
```

清除所有向量，依次重新处理全部文档。

---

## 云服务器部署

### 第一步：本机打包项目

```bash
cd /Users/yangjc/openCodeProjects

# 打包（排除临时文件）
tar --exclude='__pycache__' --exclude='*.pyc' --exclude='data' \
    --exclude='.idea' --exclude='.DS_Store' --exclude='.git' \
    -czf knowledge-base.tar.gz knowledge-base/

# 上传到服务器
scp knowledge-base.tar.gz root@你的服务器IP:/opt/
```

### 第二步：服务器安装 Docker

```bash
ssh root@你的服务器IP

# 安装 Docker（Ubuntu/Debian）
curl -fsSL https://get.docker.com | bash

# 确认 docker compose 可用
docker compose version
```

### 第三步：配置并启动

```bash
cd /opt
tar -xzf knowledge-base.tar.gz
cd knowledge-base

# 1. 创建 .env 文件
cat > .env << 'EOF'
SILICONFLOW_API_KEY=你的硅基流动APIKey
DEEPSEEK_API_KEY=你的DeepSeek APIKey
ACCESS_TOKEN=  # 留空则不需要密码，设值则访问需要输入令牌
EOF

# 2. 创建数据目录
mkdir -p data/files data/chroma

# 3. 构建并启动
docker compose up -d --build

# 4. 查看启动日志
docker compose logs -f
```

### 第四步：开放端口

在云服务器控制台的**安全组/防火墙**中放行：

| 端口 | 协议 | 用途 |
|------|------|------|
| 80 | TCP | HTTP 访问 |
| 443 | TCP | HTTPS 访问（配置 SSL 证书后） |

### 第五步：访问

```
http://你的服务器IP/
```

如果设置了 `ACCESS_TOKEN`，首次访问会跳转到登录页，输入令牌后自动保存 30 天。

### 日常运维命令

```bash
cd /opt/knowledge-base

# 查看状态
docker compose ps

# 查看日志
docker compose logs -f app

# 重启服务
docker compose restart

# 更新代码后重新部署
docker compose down
docker compose up -d --build

# 备份数据
tar -czf backup-$(date +%Y%m%d).tar.gz data/
```

### 配置 HTTPS（可选）

```bash
# 安装 certbot 获取免费 SSL 证书
apt install certbot -y
certbot certonly --standalone -d 你的域名

# 证书路径：
# /etc/letsencrypt/live/你的域名/fullchain.pem
# /etc/letsencrypt/live/你的域名/privkey.pem

# 更新 nginx.conf 添加 HTTPS 配置，然后重启
docker compose restart nginx
```

### 安全建议

1. **设置 ACCESS_TOKEN**：在 `.env` 中添加一行 `ACCESS_TOKEN=你的复杂令牌`，重启后需要输入令牌才能访问
2. **限制 IP**：安全组只允许特定 IP 访问 80 端口
3. **定期备份**：`crontab -e` 加入 `0 3 * * * tar -czf /backup/kb-$(date +\%Y\%m\%d).tar.gz /opt/knowledge-base/data/`

---

## 目录结构

```
knowledge-base/
├── app/
│   ├── main.py              # FastAPI 入口
│   ├── config.py             # 配置管理
│   ├── api/                  # 路由层
│   │   ├── chat.py           # 问答 API（流式 SSE + JSON）
│   │   ├── documents.py      # 文档管理 API
│   │   └── admin.py          # 管理 API
│   ├── rag/                  # RAG 核心
│   │   ├── embedder.py       # BGE-M3 嵌入（硅基流动）
│   │   ├── retriever.py      # FAISS 检索 + Reranker 重排序
│   │   ├── generator.py      # DeepSeek-V4 生成（流式 + 非流式）
│   │   ├── chunker.py        # 语义切片
│   │   ├── cache.py          # LLM 缓存
│   │   ├── ingest.py         # 文档处理管道
│   │   ├── vector_store.py   # FAISS 向量存储
│   │   └── parsers/          # 文档解析器
│   ├── db/                   # 数据层（SQLite + SQLAlchemy）
│   ├── scheduler/            # 定时任务（自治更新）
│   ├── web/                  # 前端（Jinja2 + HTMX）
│   └── utils/                # 工具函数
├── scripts/
│   └── import.py             # 批量导入工具
├── data/                     # 运行时数据（不纳入版本控制）
│   ├── files/                # 原始文件
│   ├── chroma/               # FAISS 索引文件
│   └── knowledge.db          # SQLite 数据库
├── docs/                     # 设计文档
├── Dockerfile
├── docker-compose.yml
├── nginx.conf
├── requirements.txt
└── .env.example
```

## 集成 Dify 平台

本项目已内置 Dify 「外部知识库 API」兼容接口，可直接挂载到 Dify Agent。

### API 端点

| 端点 | 方法 | 用途 |
|------|------|------|
| `/api/dify/retrieve` | POST | 知识检索（Dify 格式） |
| `/api/dify/health` | GET | 健康检查 |

### 在 Dify 中配置

1. 打开 Dify → **知识库** → **连接外部知识库** → **API（外部知识库）**

2. 填写配置：

| 参数 | 值 |
|------|-----|
| 名称 | 我的个人知识库 |
| API 地址 | `http://你的服务器IP:8000/api/dify/retrieve` |
| API Key | 留空（或设 `ACCESS_TOKEN` 后填入 `X-Access-Token` 头） |

3. 点击「测试连接」，确认返回 `"status": "ok"`

4. 保存后在 Dify 的 Agent/应用中选择该知识库即可

### 调用示例

```bash
curl -X POST http://你的服务器IP:8000/api/dify/retrieve \
  -H "Content-Type: application/json" \
  -d '{"query":"什么是RAG","knowledge_id":""}'
```

返回：
```json
{
  "records": [
    {
      "content": "RAG（检索增强生成）是一种...",
      "score": 0.9521,
      "title": "机器学习笔记.md",
      "document_name": "机器学习笔记.md",
      "source": "机器学习笔记.md"
    }
  ]
}
```

### 与 Agent 配合

在 Dify Agent 中挂载后，Agent 会自动：
1. 将用户问题发送到知识库检索
2. 获取相关片段作为上下文
3. 用 Dify 配置的 LLM 生成最终回答

你的个人知识库负责「检索」，Dify 负责「对话编排」。

---

## 常见问题

**Q: 上传文档后状态一直是 `uploaded`？**
A: 检查 API Key 是否正确设置。查看终端日志确认错误原因。

**Q: 上传 Excel 报错 400？**
A: 确保使用 `.xlsx` 格式，旧版 `.xls` 暂不支持。

**Q: 流式输出中断？**
A: Nginx 需要关闭代理缓冲：`proxy_buffering off;`。项目中的 nginx.conf 已配置。

**Q: 如何修改定时扫描间隔？**
A: 修改 `app/scheduler/jobs.py` 中的 `minutes=5` 参数。

**Q: 如何调整切片大小？**
A: 修改 `app/config.py` 中的 `CHUNK_SIZE` 和 `CHUNK_OVERLAP`。

**Q: 向量检索结果太少？**
A: 增大 `app/config.py` 中 `RETRIEVAL_TOP_K` 的值。

**Q: 如何清空知识库重新开始？**
A: 删除 `data/` 目录，重启服务即可（会自动重建 SQLite 和 FAISS 索引）。

---

## 技术选型参考

| 组件 | 选型 | 替代方案 |
|------|------|----------|
| Web 框架 | FastAPI | Flask, Django |
| RAG 引擎 | LlamaIndex | LangChain |
| 向量存储 | FAISS | ChromaDB, Milvus, Qdrant |
| 元数据 | SQLite | PostgreSQL, MySQL |
| 嵌入模型 | BGE-M3 (硅基流动) | text-embedding-3, bge-large-zh |
| 重排序 | BGE-Reranker-v2-m3 | Cohere Rerank |
| 对话模型 | DeepSeek-V4 | GPT-4o, Claude, Qwen |
| 前端 | Jinja2 + HTMX | React, Vue, Streamlit |
| 部署 | Docker Compose | K8s, 裸机 |
