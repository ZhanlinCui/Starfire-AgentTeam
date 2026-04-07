import { motion } from "motion/react";

const layers = [
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
];

const outcomes = [
  "Sibling workspaces remain isolated by default",
  "Parent-child memory sharing follows org topology",
  "Human approvals and authority escalation map to hierarchy",
  "Designed for auditability and enterprise data boundaries",
];

export function MemoryArchitecture() {
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
            Core Innovation
          </span>
          <h2 className="mt-5 text-[clamp(2rem,4.9vw,3.3rem)] font-semibold leading-[1.1] tracking-[-0.03em] text-white">
            Hierarchical Memory Architecture
          </h2>
          <p className="mt-4 text-[16px] md:text-[17px] leading-[1.75] text-slate-300/88">
            Starfire replaces flat global memory with topology-aware isolation. Memory follows your organization,
            so collaboration stays fast while boundaries stay enforceable.
          </p>
        </motion.div>

        <div className="grid md:grid-cols-3 gap-4 mb-7">
          {layers.map((layer, index) => (
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
          <h3 className="text-[16px] font-semibold text-white mb-3">Why This Wins In Production</h3>
          <div className="grid md:grid-cols-2 gap-2.5">
            {outcomes.map((item) => (
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
