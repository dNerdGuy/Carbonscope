import { Link, useLocation } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { useTheme } from "@/lib/theme-context";

/** Derive initials from a full name or email fallback. */
function getInitials(name: string, email: string): string {
  if (name) {
    const parts = name.trim().split(/\s+/).filter(Boolean).slice(0, 2);
    if (parts.length >= 2)
      return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
    if (parts[0].length > 0) return parts[0].slice(0, 2).toUpperCase();
  }
  return email ? email[0].toUpperCase() : "?";
}

/** Consistent avatar background derived from the user's email. */
function avatarColor(email: string): string {
  const colors = [
    "#16a34a",
    "#2563eb",
    "#9333ea",
    "#ea580c",
    "#0891b2",
    "#db2777",
    "#ca8a04",
  ];
  let hash = 0;
  for (let i = 0; i < email.length; i++)
    hash = email.charCodeAt(i) + ((hash << 5) - hash);
  return colors[Math.abs(hash) % colors.length];
}

export default function Navbar() {
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const { pathname } = useLocation();
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  // Close on outside click
  useEffect(() => {
    function onPointerDown(e: PointerEvent) {
      if (
        menuRef.current &&
        !menuRef.current.contains(e.target as Node) &&
        !triggerRef.current?.contains(e.target as Node)
      ) {
        setOpen(false);
      }
    }
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, []);

  // Close on route change
  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  // Close on Escape
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  if (!user) return null;

  const initials = getInitials(user.full_name, user.email);
  const bg = avatarColor(user.email);
  const isDark = theme === "dark";

  return (
    <header className="navbar-bar" role="banner">
      {/* Left: page breadcrumb / logo placeholder — empty space for sidebar alignment */}
      <div />

      {/* Right: avatar button */}
      <div className="relative">
        <button
          ref={triggerRef}
          onClick={() => setOpen((v) => !v)}
          aria-haspopup="true"
          aria-expanded={open}
          aria-label="Open account menu"
          className="navbar-avatar"
          style={{ backgroundColor: bg }}
        >
          {initials}
        </button>

        {/* Dropdown */}
        {open && (
          <div
            ref={menuRef}
            role="menu"
            aria-label="Account menu"
            className="navbar-dropdown"
          >
            {/* User info */}
            <div className="navbar-dropdown-header">
              <div
                className="navbar-dropdown-avatar"
                style={{ backgroundColor: bg }}
                aria-hidden="true"
              >
                {initials}
              </div>
              <div className="min-w-0">
                {user.full_name && (
                  <p className="navbar-dropdown-name">{user.full_name}</p>
                )}
                <p className="navbar-dropdown-email">{user.email}</p>
                <p className="navbar-dropdown-role">{user.role}</p>
              </div>
            </div>

            <div className="navbar-dropdown-divider" />

            {/* Account & Settings */}
            <Link
              to="/settings"
              role="menuitem"
              className="navbar-dropdown-item"
            >
              <svg
                width="15"
                height="15"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <path d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                <circle cx="12" cy="12" r="3" />
              </svg>
              Settings
            </Link>

            <Link
              to="/billing"
              role="menuitem"
              className="navbar-dropdown-item"
            >
              <svg
                width="15"
                height="15"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <path d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" />
              </svg>
              Billing
            </Link>

            <div className="navbar-dropdown-divider" />

            {/* Theme toggle */}
            <button
              role="menuitem"
              onClick={toggleTheme}
              className="navbar-dropdown-item w-full text-left"
              aria-label={`Switch to ${isDark ? "light" : "dark"} mode`}
            >
              {isDark ? (
                <svg
                  width="15"
                  height="15"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  <circle cx="12" cy="12" r="5" />
                  <line x1="12" y1="1" x2="12" y2="3" />
                  <line x1="12" y1="21" x2="12" y2="23" />
                  <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
                  <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
                  <line x1="1" y1="12" x2="3" y2="12" />
                  <line x1="21" y1="12" x2="23" y2="12" />
                  <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
                  <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
                </svg>
              ) : (
                <svg
                  width="15"
                  height="15"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  <path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z" />
                </svg>
              )}
              {isDark ? "Light Mode" : "Dark Mode"}
            </button>

            <div className="navbar-dropdown-divider" />

            {/* Logout */}
            <button
              role="menuitem"
              onClick={async () => {
                setOpen(false);
                try {
                  await logout();
                } catch {
                  window.location.href = "/login";
                }
              }}
              className="navbar-dropdown-item navbar-dropdown-item-danger w-full text-left"
            >
              <svg
                width="15"
                height="15"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4" />
                <polyline points="16 17 21 12 16 7" />
                <line x1="21" y1="12" x2="9" y2="12" />
              </svg>
              Logout
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
