"use client";

import React, { createContext, useContext } from "react";
import { User } from "@/types";

/* ── Authentication is disabled ──
   The platform operates without login/registration.
   A permanent admin user is always active.
   ────────────────────────────────────────────── */

interface AuthContextValue {
  user: User;
  loading: false;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const PERMANENT_USER: User = {
  id: "system-user",
  email: "investigator@mvd.kz",
  full_name: "Следователь",
  role: "admin",
  created_at: new Date().toISOString(),
};

export function AuthProvider({ children }: { children: React.ReactNode }) {
  return (
    <AuthContext.Provider value={{ user: PERMANENT_USER, loading: false }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
