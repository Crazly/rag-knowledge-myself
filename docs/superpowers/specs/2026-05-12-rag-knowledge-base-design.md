# RAG 个人知识库设计文档

> 日期：2026-05-12
> 状态：待实施
> 版本：v1.0

---

## 一、项目概述

### 1.1 目标

搭建一个面向个人知识管理的 RAG（检索增强生成）知识库系统，支持混合文档类型的自动化处理、语义检索和智能问答。

### 1.2 核心场景

- **个人知识管理**：整理笔记、PDF、Office 文档、网页书签等，作为个人"第二大脑"
- **文档类型**：Markdown 笔记、PDF、Word、Excel、网页内容
- **使用方式**：24/7 部署在云服务器，浏览器访问

### 1.3 非目标（本期不做）

- 多用户/团队协作
- Graph RAG（知识图谱增强检索）
- Wikipedia 等外部知识源集成
- 图片/音频/视频等多模态

---

## 二、架构设计

### 2.1 架构总览

纯 Python FastAPI 单体应用，针对 2C2G 服务器优化。

```
┌───────────────────────────────────────────────┐
│              FastAPI 单体应用                    │
│                                                │
│  ┌──────────┐  ┌──────────┐  ┌─────────────┐ │
│  │  前端页面  │  │  RAG 管道  │  │  定时任务    │ │
│  │ Jinja2   │  │ LlamaIndex│  │ APScheduler │ │
│  │ + HTMX   │  │           │  │  自治更新    │ │
│  └──────────┘  └──────────┘  └─────────────┘ │
│                                                │
│  ┌──────────┐  ┌─────────────────────┐         │
│  │ SQLite   │  │ ChromaDB（嵌入模式） │         │
│  │ 元数据    │  │ 向量存储             │         │
│  └──────────┘  └─────────────────────┘         │
└───────────────────────────────────────────────┘
      │              │              │
 ┌────▼────┐   ┌────▼────┐   ┌────▼────┐
 │BGE-M3   │   │DeepSeek │   │本地磁盘  │
 │硅基流动  │   │V4 API   │   │文件存储  │
 │嵌入+Rerank│  │         │   │         │
 └─────────┘   └─────────┘   └─────────┘
```

### 2.2 为什么选择纯 Python 单体

| 因素 | 说明 |
|------|------|
| 服务器限制 | 2C2G，跑不了 Java + Python 双服务 |
| 用户规模 | 个人使用，无需分布式 |
| 维护成本 | 单体部署运维极简，Docker Compose 一行命令 |
| 生态优势 | Python RAG/文档解析生态远超 Java |

---

## 三、技术选型

| 层 | 选型 | 理由 |
|------|------|------|
| Web 框架 | FastAPI | 异步支持好，自带 Swagger，轻量 |
| RAG 引擎 | LlamaIndex | 文档解析丰富，检索管道成熟 |
| 向量存储 | ChromaDB（嵌入模式） | 零部署，进程内运行 |
| 元数据 | SQLite + SQLAlchemy | 零内存开销，适合单机 |
| 文件存储 | 本地磁盘 `data/files/` | 简单直接 |
| 嵌入模型 | BGE-M3（硅基流动 API） | 中文最强，1024维，便宜 |
| 重排序 | BGE-Reranker-v2-m3（硅基流动） | 与 BGE-M3 同系列，配合最佳 |
| 对话模型 | DeepSeek-V4 API | 1M 上下文，推理强，性价比高 |
| 前端 | Jinja2 模板 + HTMX | 轻量，无需前端构建工具链 |
| 任务调度 | APScheduler | Python 轻量定时任务 |
| 缓存 | SQLite 实现 LLM 缓存 | 减少 API 重复调用，2C2G 不宜再加 Redis |
| 部署 | Docker Compose + Nginx | 一键部署，反代 + HTTPS |

---

## 四、数据流设计

### 4.1 文档入库（离线 / 异步）

```
用户上传文档 → FastAPI 接收 → 存入本地磁盘
                                    │
                              (异步触发管道)
                                    ▼
                            文档解析器（按类型选择）
                              PDF → PyMuPDF
                              Word → python-docx
                              Markdown → 直接读取
                              Excel → openpyxl
                              网页 → trafilatura
                                    │
                                    ▼
                            智能切片（语义分块）
                                    │
                                    ▼
                            BGE-M3 嵌入（1024维）
                                    │
                                    ▼
                            存入 ChromaDB + SQLite 元数据
```

### 4.2 知识问答（在线 / 实时）

```
用户提问
   │
   ▼
问题向量化 (BGE-M3)
   │
   ▼
ChromaDB 粗检索 (召回 Top-20)
   │
   ▼
BGE-Reranker-v2-m3 重排序 (精排 Top-5)
   │
   ▼
组装 Prompt → DeepSeek-V4 生成
   │
   ▼
返回 答案 + 引用来源
```

### 4.3 自治更新（APScheduler 定时任务）

```
定时扫描 data/files/ 目录
   │
   ├── 发现新文件 → 自动触发处理管道
   │
   └── 文件 hash 变更 → 旧向量失效 → 重新处理 → 新向量替换旧向量
```

---

## 五、模块设计

```
knowledge-base/
├── app/
│   ├── main.py                 # FastAPI 入口
│   ├── config.py               # 配置管理
│   ├── api/                    # 路由层
│   │   ├── documents.py        # 文档上传、列表、状态查询
│   │   ├── chat.py             # 问答接口
│   │   └── admin.py            # 管理：重建索引、系统状态
│   ├── rag/                    # RAG 核心
│   │   ├── ingest.py           # 文档解析 + 切片管道
│   │   ├── parsers/            # 各类型解析器
│   │   │   ├── pdf.py
│   │   │   ├── word.py
│   │   │   ├── excel.py
│   │   │   ├── markdown.py
│   │   │   └── web.py
│   │   ├── chunker.py          # 切片策略
│   │   ├── embedder.py         # BGE-M3 嵌入
│   │   ├── retriever.py        # 向量检索 + Reranker
│   │   └── generator.py        # Prompt 组装 + DeepSeek-V4
│   ├── db/                     # 数据库
│   │   ├── models.py           # SQLAlchemy 模型
│   │   ├── database.py         # 连接管理
│   │   └── crud.py             # 增删改查
│   ├── scheduler/              # 定时任务（自治更新）
│   │   └── jobs.py             # 扫描新文件、检测变更
│   ├── web/                    # 前端
│   │   ├── templates/
│   │   │   ├── base.html       # 布局骨架
│   │   │   ├── index.html      # 首页（问答）
│   │   │   ├── documents.html  # 文档管理
│   │   │   └── admin.html      # 管理页
│   │   └── static/
│   │       └── style.css
│   └── utils/
│       ├── file_handler.py     # 文件存储
│       └── hash_utils.py       # 文件哈希
├── data/                       # 运行时数据
│   ├── files/                  # 原始文件存储
│   ├── chroma/                 # ChromaDB 持久化
│   └── knowledge.db            # SQLite 数据库
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

### 模块职责

| 模块 | 职责 | 依赖 |
|------|------|------|
| `api/` | HTTP 请求处理，不写业务逻辑 | `rag/`, `db/` |
| `rag/` | 所有 AI 相关逻辑，可独立测试 | `db/`, `utils/` |
| `db/` | 数据存取，隔离 SQL | 无 |
| `scheduler/` | 自治更新第一二层 | `rag/`, `db/` |
| `web/` | 纯展示，HTMX 做交互 | `api/` |
| `utils/` | 无副作用的工具函数 | 无 |

---

## 六、数据模型

### 6.1 SQLite 表结构

```sql
-- 文档表
CREATE TABLE documents (
    id            TEXT PRIMARY KEY,        -- UUID
    filename      TEXT NOT NULL,
    file_path     TEXT NOT NULL,
    file_size     INTEGER,
    file_hash     TEXT,                    -- SHA256，变更检测用
    file_type     TEXT,                    -- pdf/word/excel/markdown/web
    status        TEXT DEFAULT 'uploaded', -- uploaded/processing/ready/failed
    chunk_count   INTEGER DEFAULT 0,
    error_message TEXT,                    -- 处理失败时的错误信息
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 切片表
CREATE TABLE chunks (
    id            TEXT PRIMARY KEY,        -- UUID
    document_id   TEXT NOT NULL REFERENCES documents(id),
    chunk_index   INTEGER NOT NULL,
    content       TEXT NOT NULL,
    token_count   INTEGER,
    page_number   INTEGER,                 -- PDF/Word 页码
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- LLM 缓存表（可选，第四阶段）
CREATE TABLE qa_cache (
    id            TEXT PRIMARY KEY,        -- MD5(问题文本)
    question      TEXT NOT NULL,
    answer        TEXT NOT NULL,
    sources       TEXT,                    -- JSON
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_chunks_document ON chunks(document_id);
CREATE INDEX idx_documents_status ON documents(status);
CREATE INDEX idx_documents_hash ON documents(file_hash);
```

### 6.2 ChromaDB Collection

```
Collection: knowledge_base
  - id: chunk_uuid（与 SQLite chunks.id 一致）
  - embedding: BGE-M3 (1024维 float array)
  - document_id: 关联文档 UUID
  - chunk_index: 切片序号
  - text: 原始文本片段
  - metadata:
      - filename: 来源文件名
      - page_number: 页码（如有）
      - file_type: 文档类型
```

---

## 七、API 设计

### 7.1 文档管理 API

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/documents` | 文档列表，支持分页和状态筛选 |
| `POST` | `/api/documents/upload` | 上传文件，返回文档 ID |
| `GET` | `/api/documents/{id}` | 文档详情（含处理状态、chunks 数） |
| `DELETE` | `/api/documents/{id}` | 删除文档及其所有 chunks |
| `POST` | `/api/documents/{id}/reprocess` | 重新处理指定文档 |

### 7.2 问答 API

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/chat` | 提出问题，返回答案+来源引用 |

请求体：
```json
{
  "question": "什么是 Transformer？",
  "top_k": 5
}
```

响应体：
```json
{
  "answer": "Transformer 是...",
  "sources": [
    {
      "text": "...",
      "document_name": "深度学习笔记.md",
      "page_number": null,
      "score": 0.92
    }
  ]
}
```

### 7.3 管理 API

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/admin/stats` | 文档数、chunk 数、存储空间 |
| `POST` | `/api/admin/reindex` | 全量重建索引 |

---

## 八、分步实施计划

### 第一阶段：项目骨架 + 文档入库

- **目标**：文档能上传、被解析、可检索
- **任务**：
  1. 初始化项目结构、FastAPI、SQLite、ChromaDB
  2. 实现文档解析器（先做 PDF + Markdown）
  3. 实现切片器
  4. 接入 BGE-M3 嵌入，存入 ChromaDB
  5. 文件上传 API + 自动触发处理管道
  6. 文档列表/状态页面
- **验收标准**：上传 PDF，能在 ChromaDB 中查到对应 chunks

### 第二阶段：问答能力

- **目标**：能问问题，得到答案
- **任务**：
  1. 实现检索器（向量检索 Top-20 + BGE-Reranker 精排 Top-5）
  2. Prompt 模板 + DeepSeek-V4 生成
  3. 问答 API + 前端问答页面
  4. 答案引用来源展示
- **验收标准**：问问题能得到带来源引用的回答

### 第三阶段：自治更新 + 完善

- **目标**：知识库能自行维护
- **任务**：
  1. APScheduler 定时扫描新文件
  2. file_hash 比对检测变更，自动重新处理
  3. 补充 Word/Excel/网页解析器
  4. 文档删除 + 对应向量清理
  5. 管理页面（索引重建、系统状态）
- **验收标准**：丢新文件/改文件自动触发更新

### 第四阶段：打磨 + 部署

- **目标**：稳定可用的生产环境
- **任务**：
  1. LLM 缓存
  2. Nginx 反代 + HTTPS
  3. Docker Compose 一键部署
  4. 导入已有笔记的工具脚本
  5. CSS 微调
- **验收标准**：`docker compose up -d` 即可运行

---

## 九、关键设计决策

### 9.1 为什么用 ChromaDB 嵌入模式而非独立服务

- 2C2G 服务器内存有限，独立 ChromaDB 服务额外占用内存
- 嵌入模式在进程内运行，零部署开销
- 数据量 10 万 chunks 以内，嵌入模式性能足够

### 9.2 为什么用 SQLite 而非 PostgreSQL/MySQL

- 零内存开销，MySQL 自身就要 300MB+
- 单用户场景无需并发写入能力
- 简单备份：复制一个文件即可

### 9.3 为什么用硅基流动 API 而非本地跑 BGE-M3

- 本地跑 BGE-M3（1.5GB）会把 2C2G 吃满
- 硅基流动有免费额度，API 延迟低
- 调用方式和 OpenAI 兼容，代码简单

### 9.4 为什么选 DeepSeek-V4

- 1M token 上下文窗口，可放心召回更多检索结果
- 推理能力强，回答质量好
- 性价比远高于 OpenAI/Claude

### 9.5 为什么重排序是必须的

- 向量检索是语义相似度近似匹配，前 20 条常含噪音
- BGE-Reranker 做 cross-encoding 逐条精判相关性
- 实践数据：Top-20 粗筛 + Rerank Top-5，比直接向量 Top-5 答案质量提升 30%~50%

---

## 十、部署方案

```yaml
# docker-compose.yml 结构
services:
  app:
    build: .
    ports: ["127.0.0.1:8000:8000"]
    volumes:
      - ./data:/app/data
    environment:
      - DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
      - SILICONFLOW_API_KEY=${SILICONFLOW_API_KEY}
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports: ["443:443"]
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
```

服务器要求：2C2G + Debian/Ubuntu，Docker 环境。

---

*文档版本 v1.0，待用户审核通过后进入实施阶段。*
