"use client";

import { useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import {
  Menu,
  X,
  FolderOpen,
  FileSignature,
  LayoutGrid,
  Database,
  Settings,
  Home,
} from "lucide-react";

const NAV_LINKS = [
  { href: "/dashboard", label: "Уголовные дела", icon: FolderOpen },
  { href: "/representations", label: "Представления", icon: FileSignature },
  { href: "/templates", label: "Шаблоны", icon: LayoutGrid },
  { href: "/knowledge-base", label: "База знаний", icon: Database },
  { href: "/settings", label: "Настройки", icon: Settings },
];

export default function Navbar() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const pathname = usePathname();

  const isActive = (href: string) => {
    if (href === "/dashboard") return pathname === "/dashboard" || pathname.startsWith("/matters");
    return pathname.startsWith(href);
  };

  return (
    <header className="sticky top-0 z-50">
      <div className="govt-bar text-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            {/* Logo */}
            <Link href="/dashboard" className="flex items-center gap-2.5 flex-shrink-0 mr-6">
              <Image
                src="/mvd-logo.png"
                alt="МВД Республики Казахстан"
                width={36}
                height={36}
                className="rounded-full object-contain"
              />
              <div className="flex items-baseline gap-1">
                <span className="text-lg font-bold tracking-tight">
                  Представление
                </span>
                <span className="text-lg font-bold text-accent-300">Ai</span>
              </div>
            </Link>

            {/* Desktop nav */}
            <nav className="hidden md:flex items-center gap-0.5 flex-1">
              {NAV_LINKS.map((link) => {
                const active = isActive(link.href);
                const Icon = link.icon;
                return (
                  <Link
                    key={link.href}
                    href={link.href}
                    className={`relative flex items-center gap-1.5 px-3.5 py-2 text-sm font-medium rounded-lg transition-all duration-200
                      ${active
                        ? "text-white bg-white/15"
                        : "text-white/70 hover:text-white hover:bg-white/8"
                      }`}
                  >
                    <Icon className={`w-4 h-4 ${active ? "text-accent-300" : ""}`} strokeWidth={1.75} />
                    <span className="whitespace-nowrap">{link.label}</span>
                    {active && (
                      <span className="absolute bottom-0 left-3 right-3 h-0.5 rounded-full bg-accent-300 shadow-[0_0_8px_rgba(100,200,255,0.6)]" />
                    )}
                  </Link>
                );
              })}
            </nav>

            <div className="flex items-center gap-2">
              {/* Home link */}
              <Link
                href="/"
                className="hidden md:flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-white/60 hover:text-white hover:bg-white/10 rounded-lg transition-all duration-200"
                title="На главную"
              >
                <Home className="w-4 h-4" strokeWidth={1.75} />
                <span className="whitespace-nowrap">На главную</span>
              </Link>

              {/* Mobile menu button */}
              <button
                onClick={() => setMobileOpen(!mobileOpen)}
                className="md:hidden p-2 text-white/60 hover:text-white hover:bg-white/10 transition-colors rounded-lg"
                aria-label="Меню"
              >
                {mobileOpen ? (
                  <X className="w-5 h-5" />
                ) : (
                  <Menu className="w-5 h-5" />
                )}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Mobile nav dropdown */}
      {mobileOpen && (
        <div className="md:hidden govt-bar border-t border-white/10 animate-fade-in">
          <nav className="max-w-7xl mx-auto px-4 py-2 space-y-1">
            {NAV_LINKS.map((link) => {
              const active = isActive(link.href);
              const Icon = link.icon;
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  onClick={() => setMobileOpen(false)}
                  className={`flex items-center gap-2 px-3 py-2.5 text-sm rounded-lg transition-colors
                    ${active
                      ? "text-white bg-white/15 font-medium"
                      : "text-white/80 hover:text-white hover:bg-white/10"
                    }`}
                >
                  <Icon className={`w-4 h-4 ${active ? "text-accent-300" : ""}`} strokeWidth={1.75} />
                  {link.label}
                </Link>
              );
            })}
            <Link
              href="/"
              onClick={() => setMobileOpen(false)}
              className="flex items-center gap-2 px-3 py-2.5 text-sm rounded-lg transition-colors text-white/80 hover:text-white hover:bg-white/10"
            >
              <Home className="w-4 h-4" strokeWidth={1.75} />
              На главную
            </Link>
          </nav>
        </div>
      )}
    </header>
  );
}
