"use client";

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
} from "lucide-react";

export default function Navbar() {
  const { user, logout } = useAuth();

  if (!user) return null;

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
                <span className="text-lg font-bold tracking-tight">Представление</span>
                <span className="text-lg font-bold text-accent-300">Ai</span>
              </div>
            </Link>

            <nav className="hidden md:flex items-center gap-1">
              <Link
                href="/dashboard"
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-white/80 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
              >
                <Briefcase className="w-4 h-4" />
                Уголовные дела
              </Link>
              <Link
                href="/representations"
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-white/80 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
              >
                <FileCheck className="w-4 h-4" />
                Представления
              </Link>
              {user.role === "admin" && (
                <>
                  <Link
                    href="/templates"
                    className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-white/80 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
                  >
                    <FileStack className="w-4 h-4" />
                    Шаблоны
                  </Link>
                  <Link
                    href="/legislation"
                    className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-white/80 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
                  >
                    <Scale className="w-4 h-4" />
                    Законодательство
                  </Link>
                  <Link
                    href="/knowledge-base"
                    className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-white/80 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
                  >
                    <Database className="w-4 h-4" />
                    База знаний
                  </Link>
                  <Link
                    href="/settings"
                    className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-white/80 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
                  >
                    <Settings className="w-4 h-4" />
                    Настройки
                  </Link>
                </>
              )}
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
                  <p className="text-xs font-medium text-white leading-none">{user.full_name}</p>
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
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}
