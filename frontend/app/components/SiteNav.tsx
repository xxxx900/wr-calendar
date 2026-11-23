"use client";

import Link from "next/link";
import { CalendarDays, MessageCircle, Send, Upload } from "lucide-react";
import { usePathname } from "next/navigation";
import { useAuth } from "../context/AuthContext";
import { ThemeToggle } from "./ThemeToggle";

type SiteNavProps = {
  userEmail?: string | null;
  userName?: string | null;
  authLoading?: boolean;
  isAdmin?: boolean;
  onSignIn?: () => void;
  onSignOut?: () => void;
};

const baseLinks = [
  { href: "/", label: "Calendar", icon: CalendarDays },
  { href: "/ask", label: "Ask AI", icon: MessageCircle },
  { href: "/contact", label: "Contact", icon: Send },
];

export function SiteNav({
  userEmail: suppliedEmail,
  userName: suppliedName,
  authLoading: suppliedLoading,
  isAdmin: suppliedIsAdmin,
  onSignIn: suppliedSignIn,
  onSignOut: suppliedSignOut,
}: SiteNavProps = {}) {
  const pathname = usePathname();
  const auth = useAuth();

  const userEmail = suppliedEmail !== undefined ? suppliedEmail : auth.session?.user.email;
  const userName =
    suppliedName !== undefined
      ? suppliedName
      : auth.session?.user.user_metadata?.full_name ?? auth.session?.user.user_metadata?.name;
  const authLoading = suppliedLoading !== undefined ? suppliedLoading : auth.authLoading;
  const isAdmin = suppliedIsAdmin !== undefined ? suppliedIsAdmin : auth.isAdmin;

  function handleSignIn() {
    if (suppliedSignIn) return suppliedSignIn();
    void auth.signIn();
  }

  function handleSignOut() {
    if (suppliedSignOut) return suppliedSignOut();
    void auth.signOut();
  }

  const links = isAdmin
    ? [...baseLinks, { href: "/admin/intake", label: "Admin Intake", icon: Upload }]
    : baseLinks;

  return (
    <nav className="site-nav" aria-label="Main navigation">
      <Link className="brand" href="/" aria-label="Wolf Ranch Community Calendar home">
        <span className="brand-mark">WR</span>
        <span>Community Calendar</span>
      </Link>
      <div className="nav-links">
        {links.map(({ href, label, icon: Icon }) => (
          <Link
            className={pathname === href ? "nav-link active" : "nav-link"}
            href={href}
            key={href}
            aria-current={pathname === href ? "page" : undefined}
          >
            <Icon size={16} aria-hidden="true" />
            <span>{label}</span>
          </Link>
        ))}
      </div>
      <div className="account-status">
        {authLoading ? (
          <span className="auth-status">Checking sign-in...</span>
        ) : userEmail ? (
          <>
            <span className="signed-in-label">Signed in</span>
            <span className="account-name">{userName ?? userEmail}</span>
            <button className="nav-link" onClick={handleSignOut} type="button">
              Sign out
            </button>
          </>
        ) : (
          <button className="nav-link" onClick={handleSignIn} type="button">
            Sign in with Google
          </button>
        )}
      </div>
      <ThemeToggle />
    </nav>
  );
}
