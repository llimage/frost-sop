"use client";

import { useState } from "react";
import Link from "next/link";
import { useStore } from "@/lib/store";

const modes = [
  { key: "dev" as const, label: "开发", icon: "🔧" },
  { key: "create" as const, label: "创作", icon: "✍️" },
  { key: "client" as const, label: "客户", icon: "💼" },
];

const navLinks = [
  { href: "/", label: "仪表盘", icon: "📊" },
  { href: "/skills", label: "技能库", icon: "🧬" },
  { href: "/costs", label: "成本", icon: "💰" },
  { href: "/output", label: "输出", icon: "📄" },
  { href: "/schedule", label: "日程", icon: "📅" },
];

export default function Navbar() {
  const { currentMode, setMode } = useStore();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 h-14 bg-[#1E293B] text-white flex items-center px-4 shadow-lg">
      {/* Brand */}
      <Link href="/" className="flex items-center gap-2 mr-6 shrink-0">
        <span className="text-xl">🔮</span>
        <span className="font-bold text-lg tracking-tight">S-O-P</span>
        <span className="hidden sm:inline text-[10px] text-slate-400 font-normal">
          一人公司指挥台
        </span>
      </Link>

      {/* Mode switches */}
      <div className="hidden md:flex items-center gap-1 mr-4 border-r border-white/15 pr-4">
        {modes.map((m) => (
          <button
            key={m.key}
            onClick={() => setMode(m.key)}
            className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
              currentMode === m.key
                ? "bg-white/15 text-white"
                : "text-slate-400 hover:text-white hover:bg-white/8"
            }`}
          >
            <span className="mr-1">{m.icon}</span>
            {m.label}
          </button>
        ))}
      </div>

      {/* Desktop nav links */}
      <div className="hidden md:flex items-center gap-1 flex-1">
        {navLinks.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className="px-3 py-1.5 rounded-md text-sm text-slate-300 hover:text-white hover:bg-white/8 transition-colors"
          >
            <span className="mr-1">{item.icon}</span>
            {item.label}
          </Link>
        ))}
      </div>

      {/* Right side */}
      <div className="hidden md:flex items-center gap-3 ml-auto">
        <span className="flex items-center gap-1.5 text-xs text-slate-400">
          <span className="w-1.5 h-1.5 rounded-full bg-green-400"></span>
          系统正常
        </span>
        <span className="text-[10px] text-slate-500 bg-white/8 px-2 py-0.5 rounded-full">
          v1.1.0
        </span>
      </div>

      {/* Mobile hamburger */}
      <button
        className="md:hidden ml-auto p-2 text-slate-300 hover:text-white"
        onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
        aria-label="Toggle menu"
      >
        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          {mobileMenuOpen ? (
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          ) : (
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
          )}
        </svg>
      </button>

      {/* Mobile menu */}
      {mobileMenuOpen && (
        <div className="absolute top-14 left-0 right-0 bg-[#1E293B] border-t border-white/10 p-3 md:hidden space-y-1">
          {/* Mode switches (mobile) */}
          <div className="flex gap-1 mb-2 pb-2 border-b border-white/10">
            {modes.map((m) => (
              <button
                key={m.key}
                onClick={() => {
                  setMode(m.key);
                  setMobileMenuOpen(false);
                }}
                className={`flex-1 px-2 py-1.5 rounded-md text-xs transition-colors ${
                  currentMode === m.key
                    ? "bg-white/15 text-white"
                    : "text-slate-400"
                }`}
              >
                {m.icon} {m.label}
              </button>
            ))}
          </div>
          {/* Nav links (mobile) */}
          {navLinks.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="block px-4 py-2.5 rounded-md text-sm text-slate-300 hover:text-white hover:bg-white/8"
              onClick={() => setMobileMenuOpen(false)}
            >
              <span className="mr-2">{item.icon}</span>
              {item.label}
            </Link>
          ))}
        </div>
      )}
    </nav>
  );
}
