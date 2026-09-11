# KnowledgeMind 智知 — 企业级 RAG 智能知识库系统

基于 **DeepSeek** 大模型的检索增强生成（RAG）系统，支持多格式文档上传、多路混合检索、流式对话、多轮会话记忆，帮助企业快速构建私域知识库。

---

## 项目背景

企业内部沉淀了大量文档（产品手册、制度文件、会议纪要、技术文档等），传统基于关键词的全文搜索难以精准获取所需知识。KnowledgeMind 通过 **RAG（检索增强生成）** 技术，将企业文档向量化存储，结合 LLM 的语义理解与生成能力，实现"问即所得"的智能知识问答。

---

## 核心特性

| 特性 | 说明 |
|------|------|
| **多格式文档解析** | 支持 PDF、Word、Excel、PPT、Markdown、TXT、CSV |
| **多路混合检索** | 向量检索（ChromaDB）+ 关键词检索（BM25）+ 知识图谱检索 |
| **智能重排序** | 三级 Rerank 策略（L1/L2/L3），根据查询复杂度自适应调整 |
| **流式对话** | SSE 流式输出，打字机效果，用户体验流畅 |
| **多轮会话记忆** | 基于 Redis 的会话持久化，支持上下文连续对话 |
| **多模型支持** | DeepSeek / 阿里云百炼 / Ollama 本地模型，一键切换 |
| **置信度评估** | 自动评估回答可信度，透明展示知识来源 |
| **引用追溯** | 每条回答精确标注引用片段，支持原文查看 |
| **Docker 一键部署** | 前后端 + Redis 容器化，`docker-compose up` 即用 |

---

## 技术架构

```mermaid
graph TB
    subgraph 前端
        A[React 18 + TypeScript]
        B[Ant Design 5]
        C[Vite 5]
    end

    subgraph 后端
        D[FastAPI + Uvicorn]
        E[ChromaDB 向量库]
        F[Redis 会话缓存]
        G[BM25 关键词检索]
        H[知识图谱检索]
    end

    subgraph AI 模型
        I[DeepSeek API]
        J[阿里云百炼]
        K[Ollama 本地]
    end

    subgraph 文档处理
        L[文档解析器]
        M[智能分块 Pipeline]
        N[嵌入模型]
    end

    A --> C
    A --> D
    D --> E
    D --> F
    D --> G
    D --> H
    D --> I
    D --> J
    D --> K
    L --> M
    M --> N
    N --> E

    style A fill:#1677ff,color:#fff
    style D fill:#52c41a,color:#fff
    style I fill:#722ed1,color:#fff
```

### 检索流程

```mermaid
sequenceDiagram
    participant U as 用户
    participant F as 前端
    participant B as FastAPI
    participant R as RAG 引擎
    participant V as 向量库
    participant L as LLM

    U->>F: 输入问题
    F->>B: POST /chat/stream
    B->>R: 意图识别 + 查询改写
    R->>V: 多路检索 (向量+BM25+图谱)
    V-->>R: 候选文档
    R->>R: Rerank 重排序
    R->>L: 组装 Prompt + 上下文
    L-->>R: 流式生成
    R-->>B: 逐 token 返回
    B-->>F: SSE 事件流
    F-->>U: 打字机效果展示
```

---

## 技术栈

| 层级 | 技术 | 选型理由 |
|------|------|----------|
| **前端框架** | React 18 + TypeScript | 类型安全、生态丰富、企业级首选 |
| **UI 组件库** | Ant Design 5 | 开箱即用的企业级组件 |
| **构建工具** | Vite 5 | 极快的 HMR 和构建速度 |
| **后端框架** | FastAPI | 高性能异步、自动 API 文档、Pydantic 校验 |
| **向量数据库** | ChromaDB | 轻量嵌入、零配置、适合中小规模 |
| **缓存** | Redis 7 | 会话持久化、L2 缓存 |
| **LLM 提供商** | DeepSeek API | 高性价比、中文能力强 |
| **嵌入模型** | BGE-small-zh-v1.5 | 中文语义匹配 SOTA |
| **容器化** | Docker + docker-compose | 一键部署、环境隔离 |

---

## 快速开始

### 前置要求

- Python 3.10+
- Node.js 18+
- Redis 7+（可选，用于会话持久化）
- DeepSeek API Key（或 Ollama 本地模型）

### 1. 克隆项目

```bash
git clone <repo-url>
cd KnowledgeMind
```

### 2. 配置环境变量

```bash
cp backend/.env.example backend/.env
# 编辑 backend/.env，填入 DS_API_KEY
```

### 3. Docker 一键启动（推荐）

```bash
docker-compose up -d
# 访问 http://localhost:8002
```

### 4. 本地开发模式

**后端：**

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload
```

**前端：**

```bash
cd frontend
npm install
npm run dev
# 访问 http://localhost:5173
```

---

## 项目结构

```
KnowledgeMind/
├── frontend/                # React 前端
│   ├── src/
│   │   ├── api/             # API 客户端 & 类型定义
│   │   ├── components/      # 组件
│   │   │   ├── ChatBox.tsx          # 聊天主组件
│   │   │   ├── MessageItem.tsx      # 消息气泡
│   │   │   ├── ChatSidebar.tsx      # 侧边栏
│   │   │   ├── ChatHeader.tsx       # 顶部栏
│   │   │   ├── ChatInput.tsx        # 输入框
│   │   │   ├── CitationPanel.tsx    # 引用面板
│   │   │   ├── DocumentUpload.tsx   # 文档上传
│   │   │   └── DocumentManager.tsx  # 文档管理
│   │   ├── hooks/           # 自定义 Hooks
│   │   │   ├── useChat.ts           # 聊天逻辑
│   │   │   └── useConversations.ts  # 会话管理
│   │   ├── styles/          # 全局样式
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   └── vite.config.ts
├── backend/                 # FastAPI 后端
│   ├── app/
│   │   ├── api/             # API 路由
│   │   ├── core/            # 认证、安全
│   │   ├── models/          # 数据模型
│   │   ├── services/        # 核心服务
│   │   │   ├── rag_engine.py        # RAG 引擎
│   │   │   ├── hybrid_search.py     # 混合检索
│   │   │   ├── vector_store.py      # 向量存储
│   │   │   ├── reranker.py          # 重排序
│   │   │   ├── model_provider.py    # 模型提供商
│   │   │   └── ...
│   │   └── config.py        # 配置管理
│   ├── requirements.txt
│   └── Dockerfile
├── docker-compose.yml
├── README.md
└── .gitignore
```

---

## API 文档

启动后端后访问 http://localhost:8002/docs 查看 Swagger 自动生成的 API 文档。

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/chat` | POST | 同步对话 |
| `/api/v1/chat/stream` | POST | 流式对话 (SSE) |
| `/api/v1/search` | POST | 语义搜索 |
| `/api/v1/upload` | POST | 上传文档 |
| `/api/v1/documents` | GET | 文档列表 |
| `/api/v1/documents/{id}` | DELETE | 删除文档 |
| `/api/v1/conversations` | GET | 会话列表 |
| `/api/v1/conversations/{id}` | GET | 会话详情 |
| `/api/v1/conversations/{id}` | DELETE | 删除会话 |
| `/api/v1/health` | GET | 健康检查 |
| `/api/v1/stats` | GET | 统计信息 |

---

## License

MIT