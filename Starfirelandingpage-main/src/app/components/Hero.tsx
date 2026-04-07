import { motion } from "motion/react";
import { ArrowRight, Terminal } from "lucide-react";
import { HeroVisual } from "./HeroVisual";
import type { Locale } from "../i18n";

type HeroProps = {
  locale: Locale;
};

const copyByLocale = {
  en: {
    badge: "Private beta - now accepting teams",
    titleLine1: "Build AI organizations.",
    titleHighlight: "Govern them at scale.",
    primaryCta: "Explore Scenarios",
    secondaryCta: "Platform Advantages",
    description:
      "Starfire is the organizational operating system for agent teams. Define hierarchical authority, topology-scoped memory, and runtime isolation in one visual control plane.",
  },
  zh: {
    badge: "内测开放中 - 现已支持团队申请",
    titleLine1: "构建 AI 组织。",
    titleHighlight: "规模化治理团队。",
    primaryCta: "查看应用场景",
    secondaryCta: "平台优势",
    description:
      "Starfire 是面向 AI Agent 团队的组织操作系统。在一个可视化控制平面中定义层级权限、拓扑作用域记忆与运行时隔离。",
  },
} satisfies Record<Locale, {
  badge: string;
  titleLine1: string;
  titleHighlight: string;
  primaryCta: string;
  secondaryCta: string;
  description: string;
}>;

export function Hero({ locale }: HeroProps) {
  const copy = copyByLocale[locale];

  return (
    <section className="relative pt-[120px] pb-18 px-6 overflow-hidden">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_70%_55%_at_50%_0%,rgba(0,86,214,0.2),transparent_65%)]" />

      <div className="relative max-w-[1280px] mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7 }}
          className="text-center max-w-[900px] mx-auto"
        >
          <img
            src="/branding/starfire-text-logo-white.png"
            alt="Starfire"
            className="h-14 md:h-16 w-auto mx-auto mb-7 object-contain"
            loading="eager"
          />

          <div className="flex items-center justify-center mb-6">
            <span className="inline-flex items-center gap-2.5 px-3.5 py-1.5 rounded-full text-[11px] font-medium tracking-[0.04em] text-sky-300 bg-sky-500/[0.08] border border-sky-500/[0.18]">
              <span className="w-1.5 h-1.5 rounded-full bg-sky-300 animate-pulse" />
              {copy.badge}
            </span>
          </div>

          <h1 className="text-[clamp(2.45rem,6vw,4.5rem)] font-semibold leading-[1.02] tracking-[-0.04em] text-white mb-6">
            {copy.titleLine1}
            <br />
            <span className="bg-gradient-to-r from-sky-300 via-blue-300 to-cyan-200 bg-clip-text text-transparent">
              {copy.titleHighlight}
            </span>
          </h1>

          <div className="flex flex-wrap justify-center items-center gap-3.5">
            <a
              href="#scenarios"
              className="group inline-flex items-center gap-2.5 px-6 py-3 text-[14px] font-medium text-[#07080C] rounded-lg transition-all duration-200 bg-white hover:bg-slate-200"
            >
              {copy.primaryCta}
              <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
            </a>
            <a
              href="#advantages"
              className="group inline-flex items-center gap-2.5 px-6 py-3 text-[14px] font-medium text-slate-200 bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.1] rounded-lg transition-all duration-200"
            >
              <Terminal className="w-3.5 h-3.5 text-slate-400" />
              {copy.secondaryCta}
            </a>
          </div>

          <p className="mt-8 text-[16px] leading-[1.74] text-slate-100/95 max-w-[860px] mx-auto">
            {copy.description}
          </p>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 30, scale: 0.99 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.8, delay: 0.2 }}
          className="mt-12 md:mt-14"
        >
          <div className="relative rounded-[28px] border border-sky-500/30 p-3 md:p-4 bg-[#04060d]/80 shadow-[0_0_0_1px_rgba(0,86,214,0.25),0_30px_90px_rgba(0,0,0,0.55)]">
            <HeroVisual locale={locale} />
          </div>
        </motion.div>
      </div>
    </section>
  );
}

