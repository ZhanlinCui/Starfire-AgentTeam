import { motion } from "motion/react";
import type { Locale } from "../i18n";

type MarketMomentumProps = {
  locale: Locale;
};

const copyByLocale = {
  en: {
    eyebrow: "Market Momentum",
    title: "Why AI Agent Teams Are A Category Now",
    signals: [
      {
        title: "Agentic Orgs > Single Bots",
        detail: "Teams are moving from single assistants to multi-role AI organizations with clear ownership.",
      },
      {
        title: "Governance Is Now Mandatory",
        detail: "Enterprise adoption depends on scoped authority, escalation paths, and auditable execution boundaries.",
      },
      {
        title: "Memory Architecture Is A Moat",
        detail: "Flat context breaks at scale. Topology-aware memory is becoming a core platform differentiator.",
      },
      {
        title: "Runtime Isolation Matters",
        detail: "Sensitive workflows require browser sandbox, Docker, and dedicated runtime tiers by role.",
      },
    ],
  },
  zh: {
    eyebrow: "市场趋势",
    title: "为什么 AI Agent 团队正在成为新一代品类",
    signals: [
      {
        title: "组织化 Agent 正在替代单体机器人",
        detail: "企业正在从单助手模式转向多角色 AI 组织，以明确责任边界与协作链路。",
      },
      {
        title: "治理能力已成为上线前提",
        detail: "企业级落地依赖可配置权限、升级路径与可审计执行边界，而不只是模型效果。",
      },
      {
        title: "记忆架构正在形成平台护城河",
        detail: "扁平上下文在规模化场景会失效，拓扑感知记忆正在成为核心差异点。",
      },
      {
        title: "运行时隔离决定可落地深度",
        detail: "敏感流程需要按角色配置 browser sandbox、Docker 与专用运行层级。",
      },
    ],
  },
} satisfies Record<Locale, { eyebrow: string; title: string; signals: Array<{ title: string; detail: string }> }>;

export function MarketMomentum({ locale }: MarketMomentumProps) {
  const copy = copyByLocale[locale];

  return (
    <section className="px-6 py-14 md:py-16">
      <div className="max-w-[1260px] mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-60px" }}
          transition={{ duration: 0.5 }}
          className="text-center mb-8"
        >
          <span className="inline-flex px-3 py-1 rounded-full text-[11px] tracking-[0.06em] uppercase border border-sky-300/35 text-sky-100 bg-sky-300/[0.12]">
            {copy.eyebrow}
          </span>
          <h2 className="mt-4 text-[clamp(1.7rem,3.8vw,2.6rem)] font-semibold leading-[1.15] tracking-[-0.02em] text-white">
            {copy.title}
          </h2>
        </motion.div>

        <div className="grid md:grid-cols-2 xl:grid-cols-4 gap-3.5">
          {copy.signals.map((signal, index) => (
            <motion.article
              key={signal.title}
              initial={{ opacity: 0, y: 18 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-40px" }}
              transition={{ duration: 0.45, delay: index * 0.06 }}
              className="rounded-2xl border border-white/[0.13] bg-[#121e34] p-5 shadow-[0_12px_35px_rgba(0,0,0,0.28)]"
            >
              <h3 className="text-[16px] font-semibold text-white leading-[1.35] mb-2.5">{signal.title}</h3>
              <p className="text-[13px] leading-[1.68] text-slate-300/88">{signal.detail}</p>
            </motion.article>
          ))}
        </div>
      </div>
    </section>
  );
}
