"use client";

import { useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { useAuth } from "@/lib/auth";
import {
  LogOut,
  Settings,
  Briefcase,
  User as UserIcon,
  Shield,
  FileStack,
  Database,
  Scale,
  FileCheck,
  Menu,
  X,
} from "lucide-react";

export default function Navbar() {
  const { user, logout } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);

  if (!user) return null;

  const navLinks = [
    { href: "/dashboard", label: "Уголовные дела", icon: Briefcase, adminOnly: false },
    { href: "/representations", label: "Представления", icon: FileCheck, adminOnly: false },
    { href: "/templates", label: "Шаблоны", icon: FileStack, adminOnly: true },
    { href: "/legislation", label: "Законодательство", icon: Scale, adminOnly: true },
    { href: "/knowledge-base", label: "База знаний", icon: Database, adminOnly: true },
    { href: "/settings", label: "Настройки", icon: Settings, adminOnly: true },
  ];

  const visibleLinks = navLinks.filter(
    (l) => !l.adminOnly || user.role === "admin"
  );

  return (
    <header className="sticky top-0 z-50">
      <div className="govt-bar text-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-14">
            <Link href="/dashboard" className="flex items-center gap-2.5">
              <Image
                src="/mvd-logo.png"
                alt="МВД РК"
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
            <nav className="hidden md:flex items-center gap-1">
              {visibleLinks.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-white/80 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
                >
                  <link.icon className="w-4 h-4" />
                  {link.label}
                </Link>
              ))}
            </nav>

            <div className="flex items-center gap-3">
              <div className="hidden sm:flex items-center gap-2 bg-white/10 rounded-lg px-3 py-1.5">
                <div className="w-6 h-6 bg-white/20 rounded-full flex items-center justify-center">
                  {user.role === "admin" ? (
                    <Shield className="w-3.5 h-3.5 text-accent-200" />
                  ) : (
                    <UserIcon className="w-3.5 h-3.5 text-white/70" />
                  )}
                </div>
                <div className="text-right">
                  <p className="text-xs font-medium text-white leading-none">
                    {user.full_name}
                  </p>
                  <p className="text-[10px] text-white/50">
                    {user.role === "admin" ? "Администратор" : "Следователь"}
                  </p>
                </div>
              </div>
              <button
                onClick={logout}
                className="p-2 text-white/60 hover:text-white hover:bg-white/10 transition-colors rounded-lg"
                title="Выйти"
              >
                <LogOut className="w-4 h-4" />
              </button>

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
        <div className="md:hidden govt-bar border-t border-white/10">
          <nav className="max-w-7xl mx-auto px-4 py-2 space-y-1">
            {visibleLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                onClick={() => setMobileOpen(false)}
                className="flex items-center gap-2 px-3 py-2.5 text-sm text-white/80 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
              >
                <link.icon className="w-4 h-4" />
                {link.label}
              </Link>
            ))}
            <div className="flex items-center gap-2 px-3 py-2 mt-2 border-t border-white/10">
              <div className="w-6 h-6 bg-white/20 rounded-full flex items-center justify-center">
                {user.role === "admin" ? (
                  <Shield className="w-3.5 h-3.5 text-accent-200" />
                ) : (
                  <UserIcon className="w-3.5 h-3.5 text-white/70" />
                )}
              </div>
              <span className="text-xs text-white/70">{user.full_name}</span>
            </div>
          </nav>
        </div>
      )}
    </header>
  );
}
