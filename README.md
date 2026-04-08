<div align="center">
  <h1>🧠 Motifold</h1>
  <p><strong>一个 AI 原生的生产力与认知辅助平台。</strong></p>
</div>

Motifold 为了增强在面对复杂任务与决策制定时的认知能力，将结构化问题求解（形态分析）与可视化知识拆解（黑板推演）整合到一个统一的工作区中。

## ✨ 核心特性

- **🤖 智能对话与动态路由**: 基于 LangGraph 与 Celery 构建。具备消息异步处理与 SSE 流式输出能力。通过动态路由中间件，能够根据任务复杂度自动选择最合适的 LLM 模型（mini, pro, max）。
- **🧩 形态学分析矩阵**: 运用茨威基（Zwicky）的形态学分析法解决复杂的多维问题。AI 可自动提取核心焦点问题，生成维度参数与状态，并评估交叉一致性，通过交互式的“平行坐标图”辅助你探索有效的解空间。
- **👨‍🏫 黑板推演**: 一个可视化的认知教学工具。AI 会将复杂的知识概念空间化（分为文本、公式、结果等板块），并逆向拆解出带有时间序列的“教学步骤”与讲义，实现渐进式的讲解体验。
- **🔌 MCP 协议支持**: 原生集成了 FastMCP，允许外部 LLM 与智能体直接通过标准协议读取工作区、获取聊天历史并触发黑板推演任务，支持 SSE 和 stdio 两种传输方式。

## 🎯 功能设计

### 1. 形态分析矩阵 

<div align="center">
  <img src="./assets/graph.png" width="800" alt="graph" />
</div>

针对复杂的多维设计与决策问题，Motifold 实现了基于“茨威基形态学”的结构化分析工具：
- **维度与状态提取**：系统严格遵循“7x7 法则”，自动从用户焦点问题中提取 7 个正交参数（维度），并为每个参数生成 7 个独立状态，构建完整的分析空间。
- **交叉一致性评估**：AI 自动对所有维度的状态组合进行成对一致性评估，将其分类为“完全兼容（绿）”、“有条件兼容（黄）”或“互斥/不可能（红）”。
- **可视化探索**：结合前端的 ECharts 平行坐标图，用户可以直观地筛选和探索在逻辑与工程上皆可行的“解空间”，避免认知盲区。

### 2. 黑板推演
为了提升对复杂知识的吸收率，Motifold 提供了一种极具沉浸感的空间化认知工具：
- **空间化布局生成**：AI 扮演高级教师的角色，将最终的知识全貌拆解为独立的文本、数学公式和结论区块（Blocks），并赋予它们防重叠的 X/Y 坐标和手写风的自然旋转角度。
- **逆向时间序列拆解**：系统对最终的“黑板”进行逆向工程，拆解出带有逻辑顺位（3-6 步）的教学讲义（脚本）。
- **渐进式交互**：在前端播放时，知识点会伴随 AI 教师的讲解逐步高亮和浮现，完美还原了线下课堂的真实推演体验。

## 🛠️ 技术栈

### 前端
- **框架:** Next.js 16 (React 19)
- **样式:** Tailwind CSS
- **可视化:** ECharts (矩阵可视化平行坐标图)
- **图标:** Lucide React
- **包管理器:** `pnpm`

### 后端
- **框架:** Python 3.13 & FastAPI
- **AI 编排:** LangGraph & LangChain
- **MCP 协议:** FastMCP
- **数据库与缓存:** PostgreSQL & Redis
- **异步任务队列:** Celery
- **ORM 与迁移:** SQLAlchemy & Alembic
- **包管理器:** `uv`

## 🚀 快速开始

### 环境前置要求
- [Docker](https://www.docker.com/) 以及 Docker Compose
- [Node.js](https://nodejs.org/) (v18+) & `pnpm`
- [Python 3.13+](https://www.python.org/) & [`uv`](https://docs.astral.sh/uv/)

### 1. 启动服务 (推荐)

在项目根目录运行单机编排：

```bash
# 配置环境变量
cp backend/.env.example backend/.env
# 编辑 backend/.env 文件，填入你的 OpenAI API Key: OPENAI_API_KEY=sk-...

# 启动全栈服务 (Postgres, Redis, API, Celery, Frontend)
make up
# 或者直接使用 docker compose: docker compose up -d --build
```
*API 服务将在宿主机端口映射为 `http://localhost:18000`。MCP SSE 端点位于 `http://localhost:18000/mcp`。*
*前端应用将在宿主机端口映射为 `http://localhost:13000`。*

### 3. 本地调用 MCP 工具 (可选)

Motifold 提供了本地 stdio 模式的 MCP 脚本，方便其他工具直接调用：
```bash
cd backend
uv run motifold-local-mcp
```

## 📂 项目结构

```text
motifold/
├── backend/      # 包含 FastAPI, Celery Workers, LangGraph 智能体、MCP 服务器及数据库迁移
└── frontend/     # 包含 Next.js 应用, UI 交互组件及 ECharts 图表可视化
```

## 🤝 贡献指南

欢迎任何形式的贡献、Issues 或功能请求！请随时查看 Issues 页面。