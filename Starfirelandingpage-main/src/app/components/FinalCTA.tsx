import { motion } from "motion/react";
import { ArrowRight, BookOpen } from "lucide-react";
import type { Locale } from "../i18n";

type FinalCTAProps = {
  locale: Locale;
};

const copyByLocale = {
  en: {
    eyebrow: "Ready To Launch",
    titleTop: "Design your",
    titleBottom: "AI org chart",
    subtitle: "Where any agent can become a team, and any team can become a company.",
    description:
      "Start with one workspace. Add a role. Expand it into a team. Scale into an organization. Starfire grows with the complexity of your ambition.",
    explore: "Explore Platform",
    docs: "Read Docs",
  },
  zh: {
    eyebrow: "准备开始",
    titleTop: "设计你的",
    titleBottom: "AI 组织图",
    subtitle: "让任何 Agent 都能成为团队，让任何团队都能扩展成公司。",
    description:
      "从一个 workspace 起步，增加角色，扩展为团队，再规模化成组织。Starfire 会随你的业务复杂度一起成长。",
    explore: "探索平台",
    docs: "阅读文档",
  },
} satisfies Record<
  Locale,
  {
    eyebrow: string;
    titleTop: string;
    titleBottom: string;
    subtitle: string;
    description: string;
    explore: string;
    docs: string;
  }
>;

export function FinalCTA({ locale }: FinalCTAProps) {
  const copy = copyByLocale[locale];

  return (
    <section id="docs" className="py-24 lg:py-32 px-6 bg-[#0f192b] border-t border-white/[0.08]">
      <div className="max-w-[980px] mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.7 }}
          className="relative rounded-[28px] overflow-hidden border border-white/[0.14] bg-[#101b31] shadow-[0_24px_80px_rgba(0,0,0,0.38)]"
        >
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_62%_70%_at_18%_10%,rgba(56,189,248,0.15),transparent_60%)]" />
          <div className="absolute inset-0 bg-[linear-gradient(120deg,rgba(56,139,253,0.14),rgba(9,13,22,0.98)_58%)]" />

          <div className="relative px-8 py-14 lg:px-14 lg:py-16">
            <div className="max-w-[760px] mx-auto text-center">
              <span className="inline-flex px-3 py-1 rounded-full text-[11px] tracking-[0.06em] uppercase border border-sky-300/35 text-sky-100 bg-sky-300/[0.12]">
                {copy.eyebrow}
              </span>

              <h2 className="mt-5 text-[clamp(1.9rem,4.6vw,3.35rem)] font-semibold leading-[1.06] tracking-[-0.03em] text-white">
                {copy.titleTop}
                <br />
                <span className="bg-gradient-to-r from-white via-sky-200 to-cyan-100 bg-clip-text text-transparent">
                  {copy.titleBottom}
                </span>
              </h2>

              <p className="mt-6 text-[18px] leading-[1.74] text-slate-200/95">{copy.subtitle}</p>
              <p className="mt-3 text-[15px] leading-[1.72] text-slate-300/90">{copy.description}</p>

              <div className="mt-10 flex flex-wrap items-center justify-center gap-3.5">
                <a
                  href="#"
                  className="inline-flex items-center gap-2.5 px-6 py-3 text-[14px] font-semibold text-[#07080C] bg-white hover:bg-slate-200 rounded-lg transition-colors group"
                >
                  {copy.explore}
                  <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
                </a>
                <a
                  href="#"
                  className="inline-flex items-center gap-2 px-6 py-3 text-[14px] font-medium text-slate-100 bg-white/[0.06] hover:bg-white/[0.1] border border-white/[0.14] rounded-lg transition-colors"
                >
                  <BookOpen className="w-3.5 h-3.5 text-slate-100" />
                  {copy.docs}
                </a>
              </div>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}

