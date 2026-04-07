import { motion } from "motion/react";
import { Activity, ChevronLeft, ChevronRight, Clock3, Layers, ShieldCheck } from "lucide-react";
import { useState, type ComponentType } from "react";
import type { Locale } from "../i18n";

type Advantage = {
  icon: ComponentType<{ className?: string }>;
  title: string;
  description: string;
  images: string[];
};

type EnterpriseProps = {
  locale: Locale;
};

const imagesByAdvantage = {
  role: [
    "https://images.unsplash.com/photo-1552664730-d307ca884978?auto=format&fit=crop&w=1600&q=80",
    "https://images.unsplash.com/photo-1557804506-669a67965ba0?auto=format&fit=crop&w=1600&q=80",
    "https://images.unsplash.com/photo-1531482615713-2afd69097998?auto=format&fit=crop&w=1600&q=80",
  ],
  mission: [
    "https://images.unsplash.com/photo-1497215842964-222b430dc094?auto=format&fit=crop&w=1600&q=80",
    "https://images.unsplash.com/photo-1461749280684-dccba630e2f6?auto=format&fit=crop&w=1600&q=80",
    "https://images.unsplash.com/photo-1504384308090-c894fdcc538d?auto=format&fit=crop&w=1600&q=80",
  ],
  trace: [
    "https://images.unsplash.com/photo-1460925895917-afdab827c52f?auto=format&fit=crop&w=1600&q=80",
    "https://images.unsplash.com/photo-1551281044-8b1d0f2f7d6d?auto=format&fit=crop&w=1600&q=80",
    "https://images.unsplash.com/photo-1504384308090-c894fdcc538d?auto=format&fit=crop&w=1600&q=80",
  ],
  security: [
    "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=1600&q=80",
    "https://images.unsplash.com/photo-1563986768609-322da13575f3?auto=format&fit=crop&w=1600&q=80",
    "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?auto=format&fit=crop&w=1600&q=80",
  ],
} as const;

const copyByLocale: Record<
  Locale,
  {
    eyebrow: string;
    title: string;
    description: string;
    placeholderMedia: string;
    prevImage: string;
    nextImage: string;
    gotoSlide: string;
    slices: Advantage[];
  }
> = {
  en: {
    eyebrow: "Product Advantages",
    title: "Commercial-Grade AI Team Operations",
    description:
      "From team design to runtime governance, Starfire ships the capabilities enterprises need to run AI agent teams in production, not just prototypes.",
    placeholderMedia: "Placeholder Media",
    prevImage: "Previous image",
    nextImage: "Next image",
    gotoSlide: "Go to slide",
    slices: [
      {
        icon: Layers,
        title: "Role-Based Command Center",
        description:
          "Design org structures with explicit role scopes, tool permissions, and authority boundaries. Turn team design directly into executable operating logic.",
        images: imagesByAdvantage.role,
      },
      {
        icon: Clock3,
        title: "Autonomous Mission Engine",
        description:
          "Run recurring workflows with governance built in. Teams execute independently, then escalate by hierarchy when confidence, scope, or risk thresholds are crossed.",
        images: imagesByAdvantage.mission,
      },
      {
        icon: Activity,
        title: "Unified Trace & Cost Intelligence",
        description:
          "Trace every team action with latency, cost, and escalation context in one topology-aware observability layer.",
        images: imagesByAdvantage.trace,
      },
      {
        icon: ShieldCheck,
        title: "Tiered Runtime Security Boundaries",
        description:
          "Assign runtime tiers by risk profile, from browser sandbox to hardened containers, without sacrificing cross-team coordination.",
        images: imagesByAdvantage.security,
      },
    ],
  },
  zh: {
    eyebrow: "产品优势",
    title: "面向商业化落地的 AI 团队运营能力",
    description:
      "从团队设计到运行治理，Starfire 提供企业级上线所需能力，让 AI Agent 团队不止于 demo，而能稳定在生产环境运行。",
    placeholderMedia: "示例素材",
    prevImage: "上一张图片",
    nextImage: "下一张图片",
    gotoSlide: "切换到第",
    slices: [
      {
        icon: Layers,
        title: "角色化指挥中心",
        description:
          "按角色作用域、工具权限与权责边界设计组织结构，让团队设计直接转化为可执行运行逻辑。",
        images: imagesByAdvantage.role,
      },
      {
        icon: Clock3,
        title: "自治任务引擎",
        description:
          "内置治理能力执行周期任务。团队可独立推进，并在置信度、范围或风险超阈值时按层级升级。",
        images: imagesByAdvantage.mission,
      },
      {
        icon: Activity,
        title: "统一追踪与成本洞察",
        description:
          "把每次团队执行的时延、成本与升级上下文集中到同一套拓扑感知观测层。",
        images: imagesByAdvantage.trace,
      },
      {
        icon: ShieldCheck,
        title: "分层运行时安全边界",
        description:
          "按风险等级配置运行层，从 browser sandbox 到强化容器隔离，同时保持跨团队协作能力。",
        images: imagesByAdvantage.security,
      },
    ],
  },
};

function AlbumShowcase({
  images,
  alt,
  placeholderMedia,
  prevImage,
  nextImage,
  gotoSlide,
}: {
  images: string[];
  alt: string;
  placeholderMedia: string;
  prevImage: string;
  nextImage: string;
  gotoSlide: string;
}) {
  const [active, setActive] = useState(0);
  const total = images.length;

  return (
    <div className="rounded-2xl overflow-hidden border border-white/[0.12] bg-[#0a0f1d]">
      <div className="h-9 border-b border-white/[0.12] bg-white/[0.04] flex items-center px-4 gap-2">
        <span className="w-2.5 h-2.5 rounded-full bg-red-400/85" />
        <span className="w-2.5 h-2.5 rounded-full bg-amber-300/85" />
        <span className="w-2.5 h-2.5 rounded-full bg-green-400/85" />
      </div>

      <div className="relative aspect-[16/9] overflow-hidden">
        <div
          className="flex h-full w-full transition-transform duration-500 ease-out"
          style={{ transform: `translateX(-${active * 100}%)` }}
        >
          {images.map((image, imageIndex) => (
            <div key={`${alt}-${imageIndex}`} className="relative h-full w-full shrink-0">
              <img src={image} alt={`${alt} ${imageIndex + 1}`} className="w-full h-full object-cover" loading="lazy" />
              <div className="absolute inset-0 bg-[linear-gradient(to_top,rgba(6,9,18,0.35),rgba(6,9,18,0.03))]" />
              <span className="absolute top-3 right-3 px-2.5 py-1 rounded-full text-[10px] tracking-[0.04em] uppercase text-slate-200 bg-[#0b1220]/85 border border-white/[0.2]">
                {placeholderMedia}
              </span>
            </div>
          ))}
        </div>

        <button
          type="button"
          onClick={() => setActive((prev) => (prev - 1 + total) % total)}
          className="absolute left-3 md:left-4 top-1/2 -translate-y-1/2 w-9 h-9 rounded-full bg-[#081223]/85 border border-white/[0.2] flex items-center justify-center text-slate-200 hover:bg-[#10203a]"
          aria-label={prevImage}
        >
          <ChevronLeft className="w-4 h-4" />
        </button>
        <button
          type="button"
          onClick={() => setActive((prev) => (prev + 1) % total)}
          className="absolute right-3 md:right-4 top-1/2 -translate-y-1/2 w-9 h-9 rounded-full bg-[#081223]/85 border border-white/[0.2] flex items-center justify-center text-slate-200 hover:bg-[#10203a]"
          aria-label={nextImage}
        >
          <ChevronRight className="w-4 h-4" />
        </button>

        <div className="absolute bottom-3 left-1/2 -translate-x-1/2 flex items-center gap-2">
          {images.map((_, dotIndex) => (
            <button
              key={`${alt}-dot-${dotIndex}`}
              type="button"
              aria-label={`${gotoSlide} ${dotIndex + 1}`}
              onClick={() => setActive(dotIndex)}
              className={`h-2.5 rounded-full transition-all ${
                active === dotIndex ? "w-6 bg-white" : "w-2.5 bg-white/45 hover:bg-white/70"
              }`}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

export function Enterprise({ locale }: EnterpriseProps) {
  const copy = copyByLocale[locale];

  return (
    <section id="advantages" className="relative py-24 md:py-30 px-6 bg-[#101a2c] border-t border-white/[0.08]">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_65%_55%_at_50%_0%,rgba(56,189,248,0.07),transparent_66%)]" />
      <div className="max-w-[1260px] mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 18 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-70px" }}
          transition={{ duration: 0.55 }}
          className="relative text-center max-w-[920px] mx-auto mb-10 md:mb-14"
        >
          <span className="inline-flex items-center px-3 py-1 rounded-full text-[11px] tracking-[0.06em] uppercase border border-sky-300/35 text-sky-200/90 bg-sky-300/[0.08]">
            {copy.eyebrow}
          </span>
          <h2 className="mt-5 text-[clamp(2rem,4.8vw,3.2rem)] font-semibold leading-[1.12] tracking-[-0.03em] text-white">
            {copy.title}
          </h2>
          <p className="mt-4 text-[16px] leading-[1.72] text-slate-300/88">{copy.description}</p>
        </motion.div>

        <div className="relative space-y-5 md:space-y-6">
          {copy.slices.map((slice, index) => {
            const imageClass = index % 2 === 0 ? "order-1" : "order-1 lg:order-2";
            const textClass = index % 2 === 0 ? "order-2 px-2 md:px-3" : "order-2 lg:order-1 px-2 md:px-3";

            return (
              <motion.article
                key={slice.title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-40px" }}
                transition={{ duration: 0.45, delay: index * 0.06 }}
                className="rounded-[26px] border border-white/[0.13] bg-[#131f34] p-4 md:p-6 shadow-[0_18px_60px_rgba(0,0,0,0.32)]"
              >
                <div className="grid gap-6 md:gap-8 items-center lg:grid-cols-2">
                  <div className={`${imageClass} w-full`}>
                    <AlbumShowcase
                      images={slice.images}
                      alt={slice.title}
                      placeholderMedia={copy.placeholderMedia}
                      prevImage={copy.prevImage}
                      nextImage={copy.nextImage}
                      gotoSlide={copy.gotoSlide}
                    />
                  </div>
                  <div className={`${textClass} w-full`}>
                    <div className="w-11 h-11 rounded-xl border border-cyan-300/35 bg-cyan-300/[0.1] flex items-center justify-center mb-4">
                      <slice.icon className="w-5 h-5 text-cyan-200" />
                    </div>
                    <h3 className="text-[clamp(1.5rem,3.3vw,2.25rem)] font-semibold text-white leading-[1.15] tracking-[-0.02em]">
                      {slice.title}
                    </h3>
                    <p className="mt-4 text-[15px] leading-[1.72] text-slate-300/88 max-w-[560px]">{slice.description}</p>
                  </div>
                </div>
              </motion.article>
            );
          })}
        </div>
      </div>
    </section>
  );
}

