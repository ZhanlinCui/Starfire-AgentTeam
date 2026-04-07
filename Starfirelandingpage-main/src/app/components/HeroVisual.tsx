import { motion } from "motion/react";
import React, { useState } from "react";
import {
  Shield,
  Eye,
  Lock,
  ChevronDown,
  ChevronRight,
  Brain,
  Zap,
  GitBranch,
  Layers,
  Activity,
  AlertTriangle,
} from "lucide-react";
import type { Locale } from "../i18n";

const mono = { fontFamily: "'JetBrains Mono', monospace" };

type HeroVisualProps = {
  locale: Locale;
};

type VisualCopy = {
  topologyTitle: string;
  tenant: string;
  live: string;
  rootTitle: string;
  rootMeta: string;
  badges: {
    trace: string;
    rbac: string;
    agents: string;
  };
  engineering: {
    label: string;
    role: string;
    scoped: string;
    count: string;
    escalation: string;
    subAgents: Array<{ label: string; model: string; runtime: string; status: "active" | "idle" | "escalated" }>;
  };
  research: {
    label: string;
    role: string;
    isolated: string;
    overlay: string;
  };
  operations: {
    label: string;
    role: string;
    onDemand: string;
    overlay: string;
  };
  telemetry: Array<{ label: string; value: string; dot: string }>;
};

const copyByLocale: Record<Locale, VisualCopy> = {
  en: {
    topologyTitle: "Topology / Production",
    tenant: "acme-corp",
    live: "LIVE",
    rootTitle: "Acme Corporation",
    rootMeta: "root-workspace · gpt-4o orchestrator",
    badges: {
      trace: "full-trace",
      rbac: "rbac",
      agents: "12 agents",
    },
    engineering: {
      label: "Engineering",
      role: "team-workspace",
      scoped: "scoped",
      count: "4",
      escalation: "Escalation → Engineering Lead: deploy approval pending",
      subAgents: [
        { label: "Frontend Agent", model: "gpt-4o", runtime: "browser", status: "active" },
        { label: "Backend Agent", model: "claude-3.5", runtime: "docker", status: "active" },
        { label: "Infra Agent", model: "gpt-4o", runtime: "docker", status: "idle" },
        { label: "QA Agent", model: "gpt-4o-mini", runtime: "sandbox", status: "escalated" },
      ],
    },
    research: {
      label: "Research",
      role: "team-workspace",
      isolated: "isolated",
      overlay: "memory: sandboxed",
    },
    operations: {
      label: "Operations",
      role: "team-workspace",
      onDemand: "on-demand",
      overlay: "tier: standard",
    },
    telemetry: [
      { label: "comms", value: "hierarchy-routed", dot: "bg-sky-400/40" },
      { label: "memory", value: "topology-scoped", dot: "bg-violet-400/40" },
      { label: "trace", value: "langfuse + otel", dot: "bg-emerald-400/40" },
      { label: "runtime", value: "docker / browser / sandbox", dot: "bg-amber-400/40" },
    ],
  },
  zh: {
    topologyTitle: "拓扑 / 生产环境",
    tenant: "acme-corp",
    live: "在线",
    rootTitle: "Acme 企业组织",
    rootMeta: "root-workspace · gpt-4o 协调器",
    badges: {
      trace: "全链路追踪",
      rbac: "角色权限",
      agents: "12 个 Agent",
    },
    engineering: {
      label: "工程团队",
      role: "团队工作空间",
      scoped: "作用域隔离",
      count: "4",
      escalation: "升级事件 → 工程负责人：发布审批待处理",
      subAgents: [
        { label: "前端 Agent", model: "gpt-4o", runtime: "browser", status: "active" },
        { label: "后端 Agent", model: "claude-3.5", runtime: "docker", status: "active" },
        { label: "基础设施 Agent", model: "gpt-4o", runtime: "docker", status: "idle" },
        { label: "测试 Agent", model: "gpt-4o-mini", runtime: "sandbox", status: "escalated" },
      ],
    },
    research: {
      label: "研究团队",
      role: "团队工作空间",
      isolated: "隔离",
      overlay: "记忆：沙箱隔离",
    },
    operations: {
      label: "运营团队",
      role: "团队工作空间",
      onDemand: "按需执行",
      overlay: "运行层级：标准",
    },
    telemetry: [
      { label: "通信", value: "按层级路由", dot: "bg-sky-400/40" },
      { label: "记忆", value: "拓扑作用域", dot: "bg-violet-400/40" },
      { label: "追踪", value: "langfuse + otel", dot: "bg-emerald-400/40" },
      { label: "运行时", value: "docker / browser / sandbox", dot: "bg-amber-400/40" },
    ],
  },
};

function NodeBadge({ children }: { children: React.ReactNode }) {
  return (
    <span
      className="inline-flex items-center gap-1 px-1.5 py-[2px] rounded text-[8px] text-gray-500 bg-white/[0.03] border border-white/[0.05]"
      style={mono}
    >
      {children}
    </span>
  );
}

function ConnectionLine({ color = "sky", className = "" }: { color?: string; className?: string }) {
  const colors: Record<string, string> = {
    sky: "from-sky-500/30 via-sky-500/10 to-transparent",
    violet: "from-violet-500/20 via-violet-500/08 to-transparent",
    blue: "from-blue-500/20 via-blue-500/08 to-transparent",
  };
  return (
    <div className={`flex justify-center ${className}`}>
      <div className={`w-px h-5 bg-gradient-to-b ${colors[color] || colors.sky}`} />
    </div>
  );
}

function SubAgentRow({
  label,
  model,
  status,
  runtime,
  delay,
}: {
  label: string;
  model: string;
  status: "active" | "idle" | "escalated";
  runtime?: string;
  delay: number;
}) {
  const statusStyles = {
    active: "bg-emerald-400",
    idle: "bg-gray-600",
    escalated: "bg-amber-400 animate-pulse",
  };
  return (
    <motion.div
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.35, delay }}
      className="flex items-center justify-between px-3 py-[7px] rounded-md border border-white/[0.04] bg-white/[0.012] hover:bg-white/[0.025] transition-colors group"
    >
      <div className="flex items-center gap-2.5">
        <div className={`w-[5px] h-[5px] rounded-full ${statusStyles[status]}`} />
        <span className="text-[11px] text-gray-300">{label}</span>
      </div>
      <div className="flex items-center gap-2">
        {runtime && (
          <span
            className="text-[8px] text-gray-600 px-1.5 py-0.5 rounded bg-white/[0.02] border border-white/[0.03]"
            style={mono}
          >
            {runtime}
          </span>
        )}
        <span className="text-[9px] text-gray-600" style={mono}>
          {model}
        </span>
      </div>
    </motion.div>
  );
}

function TeamNode({
  label,
  role,
  accent,
  status,
  expanded,
  onToggle,
  children,
  badges,
  delay,
  overlaySignal,
}: {
  label: string;
  role: string;
  accent: string;
  status: "active" | "idle" | "waiting";
  expanded?: boolean;
  onToggle?: () => void;
  children?: React.ReactNode;
  badges?: React.ReactNode;
  delay: number;
  overlaySignal?: React.ReactNode;
}) {
  const statusColor = status === "active" ? "bg-emerald-400" : status === "waiting" ? "bg-amber-400" : "bg-gray-500";

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay }}
      className="relative"
    >
      <div
        className="rounded-lg border transition-all duration-300 overflow-hidden"
        style={{
          borderColor: `${accent}`,
          background: `linear-gradient(160deg, ${accent}0a 0%, transparent 60%)`,
          boxShadow: expanded ? `0 0 24px -8px ${accent}20` : "none",
        }}
      >
        <div className="px-3 py-2.5 flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <div className={`w-[6px] h-[6px] rounded-full ${statusColor} shrink-0`} />
            <div className="min-w-0">
              <div className="text-[11.5px] font-medium text-gray-200 truncate">{label}</div>
              <div className="text-[9px] truncate" style={{ color: accent, opacity: 0.7, ...mono }}>
                {role}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-1.5 shrink-0">
            {badges}
            {onToggle && (
              <button onClick={onToggle} className="p-0.5 text-gray-600 hover:text-gray-300 transition-colors">
                {expanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
              </button>
            )}
          </div>
        </div>

        {expanded && children && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            transition={{ duration: 0.35 }}
            className="border-t px-3 py-2.5 space-y-[6px]"
            style={{ borderColor: `${accent}25` }}
          >
            {children}
          </motion.div>
        )}
      </div>

      {overlaySignal && (
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: delay + 0.6, duration: 0.4 }}
          className="absolute -right-1 -top-1 z-10"
        >
          {overlaySignal}
        </motion.div>
      )}
    </motion.div>
  );
}

export function HeroVisual({ locale }: HeroVisualProps) {
  const [expanded, setExpanded] = useState(true);
  const copy = copyByLocale[locale];

  return (
    <div className="relative w-full rounded-xl overflow-hidden border border-white/[0.07]" style={{ background: "#090B10" }}>
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_60%_50%_at_50%_0%,rgba(56,139,253,0.04),transparent)]" />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_40%_40%_at_80%_80%,rgba(124,58,237,0.03),transparent)]" />

      <svg className="absolute inset-0 w-full h-full opacity-[0.02]">
        <defs>
          <pattern id="heroGrid2" width="24" height="24" patternUnits="userSpaceOnUse">
            <circle cx="12" cy="12" r="0.5" fill="white" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#heroGrid2)" />
      </svg>

      <div className="relative">
        <div className="px-4 lg:px-5 py-3 flex items-center justify-between border-b border-white/[0.05]">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5">
              <div className="w-[9px] h-[9px] rounded-full bg-[#ff5f57]" />
              <div className="w-[9px] h-[9px] rounded-full bg-[#febc2e]" />
              <div className="w-[9px] h-[9px] rounded-full bg-[#28c840]" />
            </div>
            <div className="w-px h-3 bg-white/[0.06] ml-1" />
            <div className="flex items-center gap-2">
              <Layers className="w-3 h-3 text-sky-400/60" />
              <span className="text-[11px] font-medium tracking-[0.05em] uppercase text-gray-500" style={mono}>
                {copy.topologyTitle}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-[10px] text-gray-600" style={mono}>
              {copy.tenant}
            </span>
            <div className="flex items-center gap-1.5 px-2 py-[3px] rounded-full bg-emerald-500/[0.08] border border-emerald-500/[0.15]">
              <div className="w-[5px] h-[5px] rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-[9px] text-emerald-400 font-medium" style={mono}>
                {copy.live}
              </span>
            </div>
          </div>
        </div>

        <div className="px-4 lg:px-5 py-5 lg:py-6">
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.2 }}
            className="rounded-lg border border-sky-500/20 px-4 py-3 flex items-center justify-between"
            style={{ background: "linear-gradient(135deg, rgba(56,139,253,0.06) 0%, rgba(56,139,253,0.01) 100%)" }}
          >
            <div className="flex items-center gap-3">
              <div className="w-2 h-2 rounded-full bg-sky-400 shadow-[0_0_8px_rgba(56,139,253,0.4)]" />
              <div>
                <div className="text-[12.5px] font-medium text-white">{copy.rootTitle}</div>
                <div className="text-[9px] text-sky-400/60" style={mono}>
                  {copy.rootMeta}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <NodeBadge>
                <Eye className="w-2.5 h-2.5" /> {copy.badges.trace}
              </NodeBadge>
              <NodeBadge>
                <Shield className="w-2.5 h-2.5" /> {copy.badges.rbac}
              </NodeBadge>
              <NodeBadge>
                <Activity className="w-2.5 h-2.5" /> {copy.badges.agents}
              </NodeBadge>
            </div>
          </motion.div>

          <div className="flex items-end justify-center gap-[calc(33%-24px)] py-0">
            <ConnectionLine color="sky" />
            <ConnectionLine color="blue" />
            <ConnectionLine color="violet" />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <TeamNode
              label={copy.engineering.label}
              role={copy.engineering.role}
              accent="rgba(56,139,253,0.3)"
              status="active"
              expanded={expanded}
              onToggle={() => setExpanded(!expanded)}
              delay={0.4}
              badges={
                <>
                  <NodeBadge>
                    <Brain className="w-2.5 h-2.5" /> {copy.engineering.scoped}
                  </NodeBadge>
                  <NodeBadge>
                    <GitBranch className="w-2.5 h-2.5" /> {copy.engineering.count}
                  </NodeBadge>
                </>
              }
            >
              {copy.engineering.subAgents.map((subAgent, index) => (
                <SubAgentRow
                  key={`${subAgent.label}-${subAgent.model}`}
                  label={subAgent.label}
                  model={subAgent.model}
                  status={subAgent.status}
                  runtime={subAgent.runtime}
                  delay={0.65 + index * 0.1}
                />
              ))}

              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 1.1 }}
                className="flex items-center gap-1.5 pt-1.5 mt-1 border-t border-white/[0.03]"
              >
                <AlertTriangle className="w-2.5 h-2.5 text-amber-400/70" />
                <span className="text-[9px] text-amber-400/70" style={mono}>
                  {copy.engineering.escalation}
                </span>
              </motion.div>
            </TeamNode>

            <TeamNode
              label={copy.research.label}
              role={copy.research.role}
              accent="rgba(99,179,237,0.2)"
              status="active"
              delay={0.5}
              badges={
                <NodeBadge>
                  <Lock className="w-2.5 h-2.5" /> {copy.research.isolated}
                </NodeBadge>
              }
              overlaySignal={
                <div
                  className="px-2 py-1 rounded-md bg-violet-500/[0.1] border border-violet-500/[0.15] text-[8px] text-violet-400"
                  style={mono}
                >
                  {copy.research.overlay}
                </div>
              }
            />

            <TeamNode
              label={copy.operations.label}
              role={copy.operations.role}
              accent="rgba(99,179,237,0.12)"
              status="waiting"
              delay={0.6}
              badges={
                <NodeBadge>
                  <Zap className="w-2.5 h-2.5" /> {copy.operations.onDemand}
                </NodeBadge>
              }
              overlaySignal={
                <div
                  className="px-2 py-1 rounded-md bg-sky-500/[0.08] border border-sky-500/[0.12] text-[8px] text-sky-400/70"
                  style={mono}
                >
                  {copy.operations.overlay}
                </div>
              }
            />
          </div>

          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 1.3 }}
            className="flex flex-wrap items-center gap-x-5 gap-y-1.5 pt-4 mt-5 border-t border-white/[0.04]"
          >
            {copy.telemetry.map((signal) => (
              <div key={signal.label} className="flex items-center gap-1.5">
                <span className={`w-1 h-1 rounded-full ${signal.dot}`} />
                <span className="text-[9px] text-gray-600" style={mono}>
                  {signal.label}
                </span>
                <span className="text-[9px] text-gray-500" style={mono}>
                  {signal.value}
                </span>
              </div>
            ))}
          </motion.div>
        </div>
      </div>
    </div>
  );
}

