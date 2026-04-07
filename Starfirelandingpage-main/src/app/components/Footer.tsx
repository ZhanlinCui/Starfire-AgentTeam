import { Github } from "lucide-react";

export function Footer() {
  return (
    <footer className="border-t border-white/[0.08] py-12 px-6 bg-[#0b1424]">
      <div className="max-w-[1200px] mx-auto">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-8 mb-12">
          {/* Brand */}
          <div className="col-span-2 md:col-span-1">
            <div className="flex items-center gap-2 mb-4">
              <span className="w-7 h-7 rounded-[7px] overflow-hidden border border-white/[0.14] bg-[#081022] flex items-center justify-center">
                <img
                  src="/branding/starfire-logo.png"
                  alt="Starfire logo"
                  className="w-full h-full object-contain scale-[3.1]"
                  loading="lazy"
                />
              </span>
              <span className="text-[14px] font-semibold text-white tracking-[-0.01em]">
                Starfire
              </span>
            </div>
            <p className="text-[12px] text-gray-600 leading-[1.6] max-w-[200px]">
              The organizational operating system for AI agents.
            </p>
          </div>

          {/* Product */}
          <div>
            <h4 className="text-[12px] font-medium text-gray-400 mb-4">Product</h4>
            <ul className="space-y-2.5">
              {["Platform", "Agent Teams", "Architecture", "Changelog"].map((item) => (
                <li key={item}>
                  <a href="#" className="text-[13px] text-gray-600 hover:text-gray-300 transition-colors">
                    {item}
                  </a>
                </li>
              ))}
            </ul>
          </div>

          {/* Resources */}
          <div>
            <h4 className="text-[12px] font-medium text-gray-400 mb-4">Resources</h4>
            <ul className="space-y-2.5">
              {["Documentation", "API Reference", "Guides", "Community"].map((item) => (
                <li key={item}>
                  <a href="#" className="text-[13px] text-gray-600 hover:text-gray-300 transition-colors">
                    {item}
                  </a>
                </li>
              ))}
            </ul>
          </div>

          {/* Company */}
          <div>
            <h4 className="text-[12px] font-medium text-gray-400 mb-4">Company</h4>
            <ul className="space-y-2.5">
              {["About", "Blog", "Careers", "Contact"].map((item) => (
                <li key={item}>
                  <a href="#" className="text-[13px] text-gray-600 hover:text-gray-300 transition-colors">
                    {item}
                  </a>
                </li>
              ))}
            </ul>
          </div>

          {/* Legal */}
          <div>
            <h4 className="text-[12px] font-medium text-gray-400 mb-4">Legal</h4>
            <ul className="space-y-2.5">
              {["Privacy", "Terms", "Security"].map((item) => (
                <li key={item}>
                  <a href="#" className="text-[13px] text-gray-600 hover:text-gray-300 transition-colors">
                    {item}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Bottom bar */}
        <div className="pt-8 border-t border-white/[0.04] flex flex-col md:flex-row items-center justify-between gap-4">
          <span className="text-[12px] text-gray-700">
            &copy; 2026 Starfire Technologies, Inc.
          </span>
          <a
            href="#"
            className="flex items-center gap-1.5 text-[12px] text-gray-600 hover:text-gray-400 transition-colors"
          >
            <Github className="w-3.5 h-3.5" />
            GitHub
          </a>
        </div>
      </div>
    </footer>
  );
}
