import { motion } from "motion/react";

const signals = [
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
];

export function MarketMomentum() {
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
            Market Momentum
          </span>
          <h2 className="mt-4 text-[clamp(1.7rem,3.8vw,2.6rem)] font-semibold leading-[1.15] tracking-[-0.02em] text-white">
            Why AI Agent Teams Are A Category Now
          </h2>
        </motion.div>

        <div className="grid md:grid-cols-2 xl:grid-cols-4 gap-3.5">
          {signals.map((signal, index) => (
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
