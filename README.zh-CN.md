<div align="center">

<p>
  <img src="./docs/assets/branding/starfire-icon.png" alt="Starfire 图案 Logo" width="160" />
</p>

<p>
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="./docs/assets/branding/starfire-text-white.png">
    <img src="./docs/assets/branding/starfire-text-black.png" alt="Starfire 文字 Logo" width="420" />
  </picture>
</p>

<p>
  <a href="./README.md">English</a> | <a href="./README.zh-CN.md">中文</a>
</p>

**面向 AI Agent 团队的组织操作系统**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Go Version](https://img.shields.io/badge/go-1.25+-00ADD8?logo=go)](https://golang.org/)
[![Python Version](https://img.shields.io/badge/python-3.11+-3776AB?logo=python)](https://www.python.org/)
[![Next.js](https://img.shields.io/badge/Next.js-15-black?logo=next.js)](https://nextjs.org/)

[产品需求文档（PRD）](./docs/product/PRD.md) • 
[架构设计](./docs/architecture/architecture.md) • 
[通信协议](./docs/api-protocol/a2a-protocol.md) • 
[Agent Runtime](./docs/agent-runtime/workspace-runtime.md)

---

**一键部署：**

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new/template?template=https://github.com/yourusername/starfire)
[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/yourusername/starfire)

> 请将上面按钮 URL 中的 `yourusername/starfire` 替换为你实际的 GitHub 仓库路径。

<!-- 
  DEMO GIF — INSERT HERE
  Recommended: 800×500px, max 5MB, recorded at the steps in docs/demo/fractal-expansion-script.md
  Format: ![Starfire fractal expansion demo](./docs/demo/fractal-expansion.gif)
-->

</div>

---

> *“构建你的 AI 组织图：任意 Agent 都能成为团队，任意团队都能扩展为公司。”*

Starfire 是一个**可视化 AI Agent Team 编排平台**。  
不同于传统工作流自动化工具（如 n8n）把节点当作“任务”，Starfire 把节点定义为**角色（Workspace）**。你可以拖拽工作空间、按组织结构进行嵌套，并通过行业标准 A2A（Agent-to-Agent）协议进行安全协作。

在 Starfire 中，组织层级本身就是网络拓扑，无需手工连线。

---

## 🔥 核心差异化能力

### 👥 基于角色的抽象
在其他平台里，节点通常是 API 任务；在 Starfire 中，节点是 **Workspace**，即组织角色（如 “Developer PM” 或 “Marketing Lead”）。  
其中 AI 模型可以随时热切换，但角色的位置、层级和技能边界保持稳定可控。

### 🍱 递归式团队扩展（分形架构）
任意 Workspace 节点都可以递归扩展为完整子团队。  
对外它仍暴露统一的 A2A 接口；对内由 Team Lead 协调子 Agent。你可以从单个角色起步，平滑扩展到部门级组织，而无需重构主画布。

### 🌐 组织图即拓扑
Starfire 画布不需要手动画边，通信关系由 `parent_id` 层级自动推导：
- 同级可通信
- 父级可委派子级
- 子级可向上汇报
**组织结构天然就是访问控制结构。**

### 🧠 分层记忆架构（HMA）
很多记忆框架（如 Mem0、MemU）采用扁平全局向量库，容易破坏组织数据隔离。Starfire 提供 **Topology-Aware Memory Isolation**：
- **L1（本地记忆）**：仅对单个 Agent 可见的私有 Scratchpad
- **L2（团队共享记忆）**：仅 Team Lead 与其直接子级可检索，由行级安全策略约束
- **L3（企业级记忆）**：由 Root Workspace 管理的全局知识层（如员工手册）

### 📈 全链路可观测与层级化 Human-in-the-Loop
整个分布式团队中的每次 LLM 调用都会统一追踪到 **Langfuse**。  
当 Agent 检测到高风险动作时，会按组织树逐级上报；若当前父级无权限，继续上报直到 Root Workspace，并在 UI 侧请求人工最终审批。

### 🛡️ 分级安全与 Docker/EC2 隔离
不同角色需要不同权限。Starfire 原生支持分层隔离：
- **Tier 1**：文本/数据处理（网络隔离、只读 Docker）
- **Tier 2**：浏览器访问（内置 Playwright）
- **Tier 3**：桌面操作（Xvfb 虚拟显示 + VNC）
- **Tier 4**：完全权限（独立内核隔离 EC2 VM）

---

## 📚 文档导航

Starfire 提供按层分组、可直接落地的生产级文档：

- 📖 **[产品与概念](./docs/product/)**
  - [完整 PRD](./docs/product/PRD.md) | [核心概念](./docs/product/core-concepts.md)
- 🏗️ **[架构与基础设施](./docs/architecture/)**
  - [系统架构](./docs/architecture/architecture.md) | [数据库设计](./docs/architecture/database-schema.md) | [Provisioner](./docs/architecture/provisioner.md)
- 🔌 **[协议与 API](./docs/api-protocol/)**
  - [A2A 通信协议](./docs/api-protocol/a2a-protocol.md) | [层级路由规则](./docs/api-protocol/communication-rules.md)
- 🤖 **[Workspace Agent Runtime](./docs/agent-runtime/)**
  - [Python Runtime](./docs/agent-runtime/workspace-runtime.md) | [技能生态](./docs/agent-runtime/skills.md) | [团队扩展机制](./docs/agent-runtime/team-expansion.md)
- 🛠️ **[开发与部署](./docs/development/)**
  - [构建与启动顺序](./docs/development/build-order.md) | [可观测性](./docs/development/observability.md)
- 🎨 **[前端 Canvas](./docs/frontend/)**
  - [Next.js Canvas 引擎](./docs/frontend/canvas.md)

---

## ⚡ 快速开始

本地完整部署可通过 Docker Compose 一次拉起整套多 Agent 平台。

```bash
# 1. 初始化基础设施（Postgres、Redis、Langfuse）
./infra/scripts/setup.sh

# 2. 启动 Platform 控制平面（Go）
cd platform
go run ./cmd/server

# 3. 启动 Canvas 前端（Next.js 15）
cd ../canvas
npm install
npm run dev
```

访问 `http://localhost:3000` 打开 Starfire Canvas，拖入你的第一个 Agent。

---

## 🏢 架构总览

Starfire 是一个分布式系统：
1. **Canvas（Next.js 15）**：React Flow 可视化画布，通过 HTTP + WebSocket 与后端通信。
2. **Platform（Go / Gin）**：控制平面，负责 workspace CRUD、A2A 发现、注册与存活检测（Redis）及事件流（Postgres pub/sub）。
3. **Workspace Runtime（Python）**：单个 Agent 的执行引擎，基于 Deep Agents + LangGraph，封装为标准 A2A SDK。

> *Workspace 之间通过 JSON-RPC 2.0 直接通信，平台不进入 Agent 对话数据路径。*

---

## ☁️ 一键云部署

Starfire 内置 `railway.toml` 和 `render.yaml`，支持零配置云部署。两个平台都会自动创建托管 Postgres 与 Redis。

### Railway
```bash
# 方案 A：点击 README 部署按钮
# 方案 B：CLI 部署
railway login
railway init
railway up
```

### Render
```bash
# 方案 A：点击 README 部署按钮
# 方案 B：在 Render 控制台做 Blueprint 部署
#   New → Blueprint → 选择你的 GitHub 仓库
```

### 必需环境变量

| 变量 | 必填 | 说明 | 示例 |
|---|---|---|---|
| `DATABASE_URL` | ✅ | Postgres 连接串 | Railway/Render 自动注入 |
| `REDIS_URL` | ✅ | Redis 连接串 | Railway/Render 自动注入 |
| `SECRETS_ENCRYPTION_KEY` | ✅ | 工作区密钥加密用 AES-256 Key | `openssl rand -base64 32` |
| `PLATFORM_URL` | ✅ | Platform 服务公网地址 | `https://starfire-platform.up.railway.app` |
| `CORS_ORIGINS` | ✅ | 允许跨域来源，逗号分隔 | `https://starfire-canvas.up.railway.app` |
| `PORT` | — | API 服务端口（默认 `8080`） | Railway/Render 自动设置 |
| `RATE_LIMIT` | — | 每 IP 每分钟请求数（默认 `100`） | `500` |
| `ACTIVITY_RETENTION_DAYS` | — | 活动日志保留天数（默认 `7`） | `30` |

> **说明：** Workspace Agent 容器由平台通过 Docker Socket 拉起。对于不支持 Docker-in-Docker 的云环境（如 Railway、Render 免费层），可在无 provisioner 模式运行；workspace 需外部启动并通过 API 注册。若需完整 provisioner 能力，建议在具备 Docker 权限的 VM 自托管。

---

## 🔀 基于 LiteLLM 的多模型路由

Starfire 可选集成 [LiteLLM](https://docs.litellm.ai/) 代理服务，为每个 workspace agent 提供统一的 OpenAI 兼容入口，不受底层模型厂商限制。

**用 LiteLLM 启动完整栈：**
```bash
docker compose --profile multi-provider up
```

**配置 workspace**（`config.yaml` 或 Canvas Secrets）：
```yaml
# config.yaml
model: claude-opus-4-5        # 或 gpt-4o, openrouter/deepseek-r1, ollama/llama3.2
```
通过 Canvas 或 API 添加以下密钥：
```
OPENAI_BASE_URL  = http://litellm:4000
OPENAI_API_KEY   = sk-starfire          # 与 LITELLM_MASTER_KEY 保持一致
```

**配置模型供应商**：编辑 `infra/litellm_config.yml`，并在 shell 或 `.env` 中设置对应 API Key：
```bash
export ANTHROPIC_API_KEY=sk-ant-...
export OPENROUTER_API_KEY=sk-or-...
```

LiteLLM UI: `http://localhost:4000/ui`（监控、模型调试、成本追踪）。

> **可与 Ollama 联动：**运行 `docker compose --profile multi-provider --profile local-models up`。`litellm_config.yml` 中的 `ollama/llama3.2` 会自动走 LiteLLM → Ollama。

---

## 🦙 使用 Ollama 本地模型

Starfire 提供可选 Ollama 服务，让 workspace agent 完全运行在本地模型，无需云端 API Key。

**启用 Ollama：**
```bash
docker compose --profile local-models up
```

**拉取模型**（首次运行）：
```bash
docker compose exec ollama ollama pull llama3.2
docker compose exec ollama ollama pull qwen2.5-coder:7b
```

**在 workspace 中配置 Ollama**（`config.yaml`）：
```yaml
model: ollama:llama3.2       # 或 ollama:qwen2.5-coder:7b
```

Docker 网络内 workspace agent 可通过 `http://ollama:11434` 访问 Ollama。Ollama 数据卷（`ollamadata`）会持久化模型，避免重复下载。

> **GPU 支持：**可在 `docker-compose.yml` 中为 `ollama` 服务增加 `deploy.resources.reservations.devices` 以透传 CUDA/ROCm 设备。详见 [Ollama Docker 文档](https://hub.docker.com/r/ollama/ollama)。

---

## 📄 许可证与社区

Starfire 是开源软件，采用 **[MIT License](LICENSE)**。

*Starfire — 点燃 Agent 组织的未来。*
