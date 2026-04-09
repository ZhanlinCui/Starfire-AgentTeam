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

[快速开始](#zh-quick-start) •
[兼容的-Agent-架构](#zh-compatible-agent-architectures) •
[记忆架构](#zh-memory-architecture)

---

**一键部署：**

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new/template?template=https://github.com/ZhanlinCui/Starfire-AgentTeam)
[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/ZhanlinCui/Starfire-AgentTeam)

<!--
  DEMO GIF — INSERT HERE
  Recommended: 800×500px, max 5MB, recorded at the steps in docs/demo/fractal-expansion-script.md
  Format: ![Starfire fractal expansion demo](./docs/demo/fractal-expansion.gif)
-->

</div>

---

> *构建 AI 组织，而不是脆弱的 prompt chain。*

Starfire 是一个**面向 AI Agent 团队的商业级 orchestration 与 control plane**。它解决的不是“单个 agent 能否跑起来”，而是如何把多个 agent 组织成真实可运营的结构，包括角色分工、委派边界、运行时兼容、记忆隔离、审批链路与全链路可观测性。

在 Starfire 里，节点不是任务，而是**Workspace 角色**。一个 workspace 今天可以是单个 agent，明天可以扩展成完整子团队，而它对外的接口、权限边界、记忆边界和组织位置都保持稳定。

---

## 为什么现在需要 Starfire

很多 agent 产品能做出惊艳 demo，但一到真实组织环境就开始失效。常见问题非常集中：

| 生产环境问题 | 传统 agent 系统通常怎么失效 | Starfire 如何解决 |
|---|---|---|
| 单个通用 agent 成为瓶颈 | 规划、执行、审批、领域知识全塞进一个上下文线程，越做越脆 | 将工作拆成持久化的 workspace 角色，并给出明确层级与委派路径 |
| 多 agent graph 难以演进 | 拓扑、边和路由逻辑被硬编码在流程里，越改越脆 | 组织图就是拓扑，结构变化不需要重接整套系统 |
| 不同团队偏好不同 agent framework | LangGraph、Claude Code、CrewAI、AutoGen、CLI agent 很难共享一套运行模型 | Starfire 用统一的 workspace 生命周期、A2A 协议、memory surface 与 canvas 把它们纳入同一控制平面 |
| 共享记忆造成越权和串扰 | 扁平全局 memory store 无法体现组织边界，治理风险很高 | HMA 将记忆访问和汇报线、团队边界、显式 scope 绑定 |
| 缺少可运营 control plane | Demo 常缺审批、liveness、重试、tracing、restart 等能力 | Starfire 提供 registry、健康探测、restart 流程、HITL escalation 与事件流 |

## 为什么它具备商业价值

- **角色原生 orchestration：** 模型可以替换，role、权限、memory、topology 不会被破坏。
- **渐进式扩容：** 单个 workspace 可以平滑升级成一个受控子团队，而外部协作方式不变。
- **可运营 guardrails：** 生命周期、health sweep、审批上报和 runtime tiering 都是平台能力，不是零散脚本。
- **企业级隔离模型：** access control、memory segmentation、workspace 级配置与 secrets 都在平台层统一约束。
- **异构 runtime 兼容：** 团队可以统一治理方式，而不必统一到某一个 agent framework。

<a id="zh-compatible-agent-architectures"></a>

## 兼容的 Agent 架构

Starfire 的目标不是把所有团队强行收敛到一个 framework，而是把异构 agent stack 统一到同一种 operating model。

| Runtime | 架构类型 | 原生优势 | Starfire 额外提供什么 |
|---|---|---|---|
| **LangGraph** | 图式 Python agent runtime | 工具调用结构化、执行图可控、易于挂 skills/plugins | Canvas orchestration、A2A delegation、组织感知 memory、runtime tiers、平台生命周期 |
| **DeepAgents** | 偏规划型的 LangGraph 变体 | 更强的任务拆解和协调模式 | 同一套 workspace contract、层级路由、observability 和 restart 行为 |
| **Claude Code** | Agentic CLI runtime | 真实编码工作流、原生 session continuity、CLAUDE.md 与工具钩子 | 安全容器化、MCP/A2A delegation、组织拓扑和共享 control plane |
| **CrewAI** | 角色型多 agent framework | 轻量 crew 组合、任务导向协作 | 持久 workspace 身份、access control、统一 canvas、标准 agent card 与 registry |
| **AutoGen** | Assistant-agent + tool orchestration | 工具丰富、对微软生态友好 | 相同部署模型、runtime governance、memory surface 与 inter-agent communication |
| **OpenClaw** | CLI-native agent runtime | 另类 agent CLI 工作流与原生 session 机制 | Workspace 生命周期、平台路由、监控与层级协作模型 |

这些 runtime 在 Starfire 中都会收敛到同一个 workspace 抽象、同一套 A2A 通信规则，以及同一个 control plane。

<a id="zh-memory-architecture"></a>

## 为什么我们的 Memory 架构更领先

Starfire 的 **HMA（Hierarchical Memory Architecture）** 是按组织设计的，不是按单个 agent demo 设计的。

| 传统 agent memory | Starfire HMA |
|---|---|
| 扁平全局 memory store，或只做弱命名空间隔离 | Memory scope 直接映射组织结构：**L1 Local**、**L2 Team**、**L3 Global** |
| 记忆共享往往是隐式的，容易过度暴露 | 共享是显式的、拓扑感知的，与汇报线和团队边界对齐 |
| 隔离通常只是应用层约定 | 隔离落在 workspace awareness namespace、平台规则与 RLS 约束上 |
| 适合 recall，但不适合治理 | 同时兼顾 recall 与治理，能按组织边界隔离敏感知识 |
| Memory 与操作流程是分离的 | 稳定工作流可以从 memory 提升为 skill，并通过热加载回到 runtime |

这点对商业落地非常关键：真实团队不会接受某个 agent 能随便读取所有团队的工作记忆。Starfire 把 memory 当成组织基础设施，而不是全局 scratchpad。

## 核心差异化能力

### 👥 基于角色的抽象
很多平台的节点本质是 API task。Starfire 的节点是 **Workspace**，也就是组织中的一个角色，例如 Developer PM、Marketing Lead 或 QA。底层模型和 runtime 可以替换，但团队结构不会因此失稳。

### 🍱 递归式团队扩展（分形架构）
任何 workspace 都可以扩展成内部子团队，同时对外继续保持单一 A2A 接口。你可以从一个 specialist 开始，后续把它扩成一个部门，而无需改动上游系统接入。

### 🌐 组织图即拓扑
Starfire 画布没有手动画线。通信路径由 `parent_id` 层级自动推导，因此拓扑和访问策略天然一致。
- 同级可通信
- 父级可委派子级
- 子级可向上汇报
**组织结构天然就是访问控制结构。**

### 🧠 分层记忆架构（HMA）
Starfire 提供 **topology-aware memory isolation**：
- **L1（本地记忆）**：只属于单个 agent 的私有 scratchpad。
- **L2（团队共享记忆）**：仅 Team Lead 与其直接子级可检索，并由行级安全策略约束。
- **L3（企业级记忆）**：由 Root Workspace 管理的全局知识层，例如员工手册、统一规范、品牌要求。

### 📈 全链路可观测与层级化 Human-in-the-Loop
整个分布式团队的 LLM 调用都可通过 **Langfuse** 追踪。当 workspace 检测到高风险动作时，它可以沿组织树逐级上报，直到有权限的父级或人类完成审批。

### 🛡️ 分级安全与运行时隔离
不同角色需要不同权限。Starfire 原生支持分层隔离：
- **Tier 1：** 文本/数据处理（网络隔离、只读 Docker）
- **Tier 2：** 标准工作区（资源受限 Docker + `/workspace` 挂载）
- **Tier 3：** 特权操作（`--privileged` + host PID，仍走 Docker 网络）
- **Tier 4：** 完整宿主机访问（privileged + host PID + host network + Docker socket）

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
  - [Runtime 概览](./docs/agent-runtime/workspace-runtime.md) | [技能生态](./docs/agent-runtime/skills.md) | [团队扩展机制](./docs/agent-runtime/team-expansion.md)
- 🛠️ **[开发与部署](./docs/development/)**
  - [构建与启动顺序](./docs/development/build-order.md) | [可观测性](./docs/development/observability.md)
- 🎨 **[前端 Canvas](./docs/frontend/)**
  - [Next.js Canvas 引擎](./docs/frontend/canvas.md)

---

<a id="zh-quick-start"></a>

## ⚡ 快速开始

本地完整部署可通过 Docker Compose 一次拉起整套多 Agent 平台。

推荐的本地路径：
1. 启动共享基础设施 `./infra/scripts/setup.sh`
2. 在仓库根目录运行 `molecli doctor` 检查本地环境
3. 启动 Platform 控制平面
4. 启动 Canvas 前端
5. 打开 Canvas 并部署第一个模板

```bash
# 1. 初始化基础设施（Postgres、Redis、Langfuse）
./infra/scripts/setup.sh

# 2. 检查本地环境
molecli doctor

# 3. 启动 Platform 控制平面（Go）
cd platform
go run ./cmd/server

# 4. 启动 Canvas 前端（Next.js 15）
cd ../canvas
npm install
npm run dev
```

访问 `http://localhost:3000` 打开 Starfire Canvas，进入模板面板并部署你的第一个 agent workspace。

---

## 🏢 架构总览

Starfire 是一个彻底分布式的系统：
1. **Canvas（Next.js 15）**：React Flow 可视化画布，通过 HTTP + WebSocket 与后端通信。
2. **Platform（Go / Gin）**：控制平面，负责 workspace CRUD、A2A 发现、registry liveness、事件流和 provisioner。
3. **Workspace Runtime（可插拔适配层）**：统一承载 LangGraph、DeepAgents、Claude Code、CrewAI、AutoGen、OpenClaw 等运行时，并对外暴露标准 A2A workspace。

> *Workspace 之间通过 JSON-RPC 2.0 直接通信，平台不进入 agent 对话的数据路径。*

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

> **说明：** Workspace agent 容器由平台通过 Docker socket 拉起。对于不支持 Docker-in-Docker 的云环境（如 Railway、Render 免费层），可在无 provisioner 模式运行；workspace 需外部启动并通过 API 注册。若需完整 provisioner 能力，建议在具备 Docker 权限的 VM 自托管。

---

## 🔀 基于 LiteLLM 的多模型路由

Starfire 可选集成 [LiteLLM](https://docs.litellm.ai/) 代理服务，为每个 workspace agent 提供统一的 OpenAI 兼容入口，不受底层模型厂商限制。

**用 LiteLLM 启动完整栈：**
```bash
docker compose --profile multi-provider up
```

**配置 workspace**，可通过 `config.yaml` 或 Canvas Secrets 面板：
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

LiteLLM UI 地址：`http://localhost:4000/ui`，可用于监控、模型调试和成本跟踪。

> **可与 Ollama 联动：**运行 `docker compose --profile multi-provider --profile local-models up`。`litellm_config.yml` 中的 `ollama/llama3.2` 会自动走 LiteLLM → Ollama。

---

## 🦙 使用 Ollama 本地模型

Starfire 提供可选 Ollama 服务，让 workspace agent 完全运行在本地模型上，无需云端 API Key。

**启用 Ollama：**
```bash
docker compose --profile local-models up
```

**拉取模型**（首次运行）：
```bash
docker compose exec ollama ollama pull llama3.2
docker compose exec ollama ollama pull qwen2.5-coder:7b
```

**在 workspace 中配置 Ollama**：
```yaml
model: ollama:llama3.2       # 或 ollama:qwen2.5-coder:7b
```

Docker 网络内的 workspace agent 可通过 `http://ollama:11434` 访问 Ollama。Ollama 数据卷 `ollamadata` 会持久化模型，避免重复下载。

> **GPU 支持：**可在 `docker-compose.yml` 中为 `ollama` 服务增加 `deploy.resources.reservations.devices` 以透传 CUDA/ROCm 设备。详见 [Ollama Docker 文档](https://hub.docker.com/r/ollama/ollama)。

---

## 📄 许可证与社区

Starfire 是开源软件，采用 **[MIT License](LICENSE)**。

*Starfire — 点燃 Agent 组织的未来。*
