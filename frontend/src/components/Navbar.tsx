"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard", icon: "📊" },
  { href: "/upload", label: "Upload Data", icon: "📤" },
  { href: "/reports", label: "Reports", icon: "📋" },
  { href: "/questionnaires", label: "Questionnaires", icon: "📝" },
  { href: "/scenarios", label: "Scenarios", icon: "🔮" },
  { href: "/supply-chain", label: "Supply Chain", icon: "🔗" },
  { href: "/compliance", label: "Compliance", icon: "📑" },
  { href: "/settings", label: "Settings", icon: "⚙️" },
];

export default function Navbar() {
  const { user, logout } = useAuth();
  const pathname = usePathname();

  if (!user) return null;

  return (
    <nav className="flex items-center justify-between px-6 py-3 border-b border-[var(--card-border)] bg-[var(--card)]">
      <div className="flex items-center gap-8">
        <Link
          href="/dashboard"
          className="text-lg font-bold text-[var(--primary)]"
        >
          🌿 CarbonScope
        </Link>
        <div className="flex gap-1">
          {NAV_ITEMS.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                pathname === item.href
                  ? "bg-[var(--primary)] text-black"
                  : "text-[var(--muted)] hover:text-[var(--foreground)]"
              }`}
            >
              {item.icon} {item.label}
            </Link>
          ))}
        </div>
      </div>
      <div className="flex items-center gap-4">
        <span className="text-sm text-[var(--muted)]">{user.email}</span>
        <button
          onClick={logout}
          className="text-sm text-[var(--muted)] hover:text-[var(--danger)] transition-colors"
        >
          Logout
        </button>
      </div>
    </nav>
  );
}
