import { motion } from "motion/react";
import { Github, Menu, X } from "lucide-react";
import { useState } from "react";

export function Header() {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <motion.header
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.8, delay: 0.1 }}
      className="fixed top-0 left-0 right-0 z-50"
    >
      <div
        className="border-b border-white/[0.08]"
        style={{ backdropFilter: "blur(16px) saturate(180%)", background: "rgba(6,10,18,0.82)" }}
      >
        <div className="max-w-[1200px] mx-auto px-6">
          <div className="flex items-center justify-between h-[60px]">
            {/* Logo */}
            <a href="#" className="flex items-center shrink-0 gap-2.5">
              <span className="w-8 h-8 rounded-[8px] overflow-hidden border border-white/[0.14] bg-[#081022] flex items-center justify-center">
                <img
                  src="/branding/starfire-logo.png"
                  alt="Starfire icon"
                  className="w-full h-full object-contain scale-[3.1]"
                  loading="eager"
                />
              </span>
              <img
                src="/branding/starfire-text-logo-white.png"
                alt="Starfire"
                className="h-6 w-auto object-contain"
                loading="eager"
              />
            </a>

            {/* Desktop nav */}
            <nav className="hidden md:flex items-center gap-1">
              {[
                { label: "Home", href: "#" },
                { label: "Scenarios", href: "#scenarios" },
                { label: "Advantages", href: "#advantages" },
                { label: "Docs", href: "#docs" },
              ].map((item) => (
                <a
                  key={item.label}
                  href={item.href}
                  className="px-3 py-1.5 text-[13px] text-gray-400 hover:text-white transition-colors rounded-md hover:bg-white/[0.04]"
                >
                  {item.label}
                </a>
              ))}
              <a
                href="#"
                className="px-3 py-1.5 text-[13px] text-gray-400 hover:text-white transition-colors rounded-md hover:bg-white/[0.04] flex items-center gap-1.5"
              >
                <Github className="w-3.5 h-3.5" />
                GitHub
              </a>
            </nav>

            {/* Desktop CTA */}
            <div className="hidden md:flex items-center gap-2">
              <a
                href="#"
                className="px-3.5 py-1.5 text-[13px] text-gray-400 hover:text-white transition-colors"
              >
                Sign in
              </a>
              <a
                href="#"
                className="px-3.5 py-1.5 text-[13px] font-medium text-[#07080C] bg-white hover:bg-gray-200 rounded-md transition-colors"
              >
                Explore Platform
              </a>
            </div>

            {/* Mobile toggle */}
            <button
              className="md:hidden p-1.5 text-gray-400 hover:text-white"
              onClick={() => setMobileOpen(!mobileOpen)}
            >
              {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile nav */}
      {mobileOpen && (
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          className="md:hidden border-b border-white/[0.04]"
          style={{ backdropFilter: "blur(16px) saturate(180%)", background: "rgba(7,8,12,0.96)" }}
        >
          <div className="px-6 py-4 space-y-1">
            {[
              { label: "Home", href: "#" },
              { label: "Scenarios", href: "#scenarios" },
              { label: "Advantages", href: "#advantages" },
              { label: "Docs", href: "#docs" },
              { label: "GitHub", href: "#" },
            ].map((item) => (
              <a
                key={item.label}
                href={item.href}
                className="block px-3 py-2.5 text-[14px] text-gray-300 hover:text-white rounded-md hover:bg-white/[0.04] transition-colors"
                onClick={() => setMobileOpen(false)}
              >
                {item.label}
              </a>
            ))}
            <div className="pt-3 border-t border-white/[0.06]">
              <a
                href="#"
                className="block w-full text-center px-3.5 py-2.5 text-[14px] font-medium text-[#07080C] bg-white rounded-md"
              >
                Explore Platform
              </a>
            </div>
          </div>
        </motion.div>
      )}
    </motion.header>
  );
}
