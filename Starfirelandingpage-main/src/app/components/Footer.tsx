import { Github } from "lucide-react";
import type { Locale } from "../i18n";

type FooterProps = {
  locale: Locale;
};

const copyByLocale = {
  en: {
    brandDescription: "The organizational operating system for AI agents.",
    sections: {
      product: { title: "Product", items: ["Platform", "Agent Teams", "Architecture", "Changelog"] },
      resources: { title: "Resources", items: ["Documentation", "API Reference", "Guides", "Community"] },
      company: { title: "Company", items: ["About", "Blog", "Careers", "Contact"] },
      legal: { title: "Legal", items: ["Privacy", "Terms", "Security"] },
    },
    copyright: "© 2026 Starfire Technologies, Inc.",
    github: "GitHub",
  },
  zh: {
    brandDescription: "面向 AI Agent 团队的组织操作系统。",
    sections: {
      product: { title: "产品", items: ["平台", "Agent 团队", "架构", "更新日志"] },
      resources: { title: "资源", items: ["文档中心", "API 参考", "使用指南", "社区"] },
      company: { title: "公司", items: ["关于我们", "博客", "招聘", "联系我们"] },
      legal: { title: "法务", items: ["隐私政策", "服务条款", "安全"] },
    },
    copyright: "© 2026 Starfire Technologies, Inc.",
    github: "GitHub",
  },
} satisfies Record<
  Locale,
  {
    brandDescription: string;
    sections: {
      product: { title: string; items: string[] };
      resources: { title: string; items: string[] };
      company: { title: string; items: string[] };
      legal: { title: string; items: string[] };
    };
    copyright: string;
    github: string;
  }
>;

export function Footer({ locale }: FooterProps) {
  const copy = copyByLocale[locale];
  const sectionList = [copy.sections.product, copy.sections.resources, copy.sections.company, copy.sections.legal];

  return (
    <footer className="border-t border-white/[0.08] py-12 px-6 bg-[#0b1424]">
      <div className="max-w-[1200px] mx-auto">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-8 mb-12">
          <div className="col-span-2 md:col-span-1">
            <div className="flex items-center gap-2 mb-4">
              <span className="w-7 h-7 rounded-[7px] overflow-hidden border border-white/[0.14] bg-[#081022] flex items-center justify-center">
                <img
                  src="/branding/starfire-logo.png"
                  alt="Starfire logo"
                  className="w-full h-full object-contain"
                  loading="lazy"
                />
              </span>
              <span className="text-[14px] font-semibold text-white tracking-[-0.01em]">Starfire</span>
            </div>
            <p className="text-[12px] text-gray-500 leading-[1.6] max-w-[200px]">{copy.brandDescription}</p>
          </div>

          {sectionList.map((section) => (
            <div key={section.title}>
              <h4 className="text-[12px] font-medium text-gray-300 mb-4">{section.title}</h4>
              <ul className="space-y-2.5">
                {section.items.map((item) => (
                  <li key={item}>
                    <a href="#" className="text-[13px] text-gray-400 hover:text-gray-200 transition-colors">
                      {item}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="pt-8 border-t border-white/[0.04] flex flex-col md:flex-row items-center justify-between gap-4">
          <span className="text-[12px] text-gray-500">{copy.copyright}</span>
          <a href="#" className="flex items-center gap-1.5 text-[12px] text-gray-400 hover:text-gray-200 transition-colors">
            <Github className="w-3.5 h-3.5" />
            {copy.github}
          </a>
        </div>
      </div>
    </footer>
  );
}
