import { motion } from "motion/react";
import type { Locale } from "../i18n";

type MemoryArchitectureProps = {
  locale: Locale;
};

const copyByLocale: Record<
  Locale,
  {
    eyebrow: string;
    title: string;
    description: string;
    layers: Array<{ name: string; summary: string; detail: string; color: string }>;
    outcomesTitle: string;
    outcomes: string[];
  }
> = {
  en: {
    eyebrow: "Core Innovation",
    title: "Hierarchical Memory Architecture",
    description:
      "Starfire replaces flat global memory with topology-aware isolation. Memory follows your organization, so collaboration stays fast while boundaries stay enforceable.",
    layers: [
      {
        name: "L1 - Local Memory",
        summary: "Private scratchpad per workspace.",
        detail:
          "Context is isolated to the individual agent role. Personal reasoning, temporary findings, and short-lived working state stay private by default.",
        color: "from-sky-300/45 to-blue-500/15",
      },
      {
        name: "L2 - Team Shared Memory",
        summary: "Shared only with a Team Lead and direct children.",
        detail:
          "A collaboration layer for active teams. Access is scoped to direct hierarchy, enabling coordination without leaking memory across sibling teams.",
        color: "from-cyan-300/45 to-cyan-500/15",
      },
      {
        name: "L3 - Corporate Memory",
        summary: "Top-down organizational knowledge.",
        detail:
          "Root-managed policies, standards, and approved knowledge can flow down the org structure, ensuring consistency and governance at scale.",
        color: "from-violet-300/45 to-violet-500/15",
      },
    ],
    outcomesTitle: "Why This Wins In Production",
    outcomes: [
      "Sibling workspaces remain isolated by default",
      "Parent-child memory sharing follows org topology",
      "Human approvals and authority escalation map to hierarchy",
      "Designed for auditability and enterprise data boundaries",
    ],
  },
  zh: {
    eyebrow: "核心创新",
    title: "层级记忆架构",
    description:
      "Starfire 用拓扑感知隔离替代扁平全局记忆。记忆沿组织结构流动，让协作保持高效，同时边界始终可执行。",
    layers: [
      {
        name: "L1 - 本地记忆",
        summary: "每个工作空间独享私有记忆区。",
        detail:
          "上下文默认隔离在单个 Agent 角色内，个人推理、临时结论与短期工作状态保持私有。",
        color: "from-sky-300/45 to-blue-500/15",
      },
      {
        name: "L2 - 团队共享记忆",
        summary: "仅 Team Lead 与直接子级可访问。",
        detail:
          "面向活跃协作团队的共享层，访问范围严格绑定直接层级，避免跨同级团队记忆泄漏。",
        color: "from-cyan-300/45 to-cyan-500/15",
      },
      {
        name: "L3 - 企业级记忆",
        summary: "自上而下统一组织知识。",
        detail:
          "由 Root Workspace 管理策略、标准与已审批知识，并按组织结构下发，支撑规模化一致治理。",
        color: "from-violet-300/45 to-violet-500/15",
      },
    ],
    outcomesTitle: "为什么它能在生产环境取胜",
    outcomes: [
      "同级工作空间默认隔离，避免串扰",
      "父子级记忆共享严格遵循组织拓扑",
      "人工审批与权限升级天然映射层级关系",
      "从设计上满足审计需求与企业数据边界",
    ],
  },
};

export function MemoryArchitecture({ locale }: MemoryArchitectureProps) {
  const copy = copyByLocale[locale];

  return (
    <section className="relative px-6 py-20 md:py-24 bg-[#0d1729] border-y border-white/[0.08]">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_58%_44%_at_50%_0%,rgba(56,139,253,0.12),transparent_66%)]" />
      <div className="max-w-[1260px] mx-auto relative">
        <motion.div
          initial={{ opacity: 0, y: 18 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-60px" }}
          transition={{ duration: 0.55 }}
          className="text-center max-w-[960px] mx-auto mb-10"
        >
          <span className="inline-flex px-3 py-1 rounded-full text-[11px] tracking-[0.06em] uppercase border border-sky-300/35 text-sky-100 bg-sky-300/[0.12]">
            {copy.eyebrow}
          </span>
          <h2 className="mt-5 text-[clamp(2rem,4.9vw,3.3rem)] font-semibold leading-[1.1] tracking-[-0.03em] text-white">
            {copy.title}
          </h2>
          <p className="mt-4 text-[16px] md:text-[17px] leading-[1.75] text-slate-300/88">{copy.description}</p>
        </motion.div>

        <div className="grid md:grid-cols-3 gap-4 mb-7">
          {copy.layers.map((layer, index) => (
            <motion.article
              key={layer.name}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-40px" }}
              transition={{ duration: 0.45, delay: index * 0.08 }}
              className="rounded-2xl border border-white/[0.14] bg-[#111f35] p-5 md:p-6 shadow-[0_14px_40px_rgba(0,0,0,0.3)]"
            >
              <div className={`w-full h-1.5 rounded-full bg-gradient-to-r ${layer.color} mb-4`} />
              <h3 className="text-[18px] font-semibold text-white">{layer.name}</h3>
              <p className="mt-2 text-[13.5px] text-sky-100/95">{layer.summary}</p>
              <p className="mt-3 text-[13px] leading-[1.68] text-slate-300/86">{layer.detail}</p>
            </motion.article>
          ))}
        </div>

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-40px" }}
          transition={{ duration: 0.45, delay: 0.15 }}
          className="rounded-2xl border border-white/[0.12] bg-[#13223a] p-5 md:p-6"
        >
          <h3 className="text-[16px] font-semibold text-white mb-3">{copy.outcomesTitle}</h3>
          <div className="grid md:grid-cols-2 gap-2.5">
            {copy.outcomes.map((item) => (
              <div key={item} className="flex items-center gap-2.5 text-[13px] text-slate-200/92">
                <span className="w-1.5 h-1.5 rounded-full bg-sky-300" />
                <span>{item}</span>
              </div>
            ))}
          </div>
        </motion.div>
      </div>
    </section>
  );
}

