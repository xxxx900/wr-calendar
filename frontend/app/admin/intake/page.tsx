"use client";

import { useEffect } from "react";
import { AdminCalendarIntake } from "../../components/AdminCalendarIntake";
import { SiteNav } from "../../components/SiteNav";
import { useAuth } from "../../context/AuthContext";
import { ShieldAlert } from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function AdminIntakePage() {
  const { session, authLoading, isAdmin, signIn } = useAuth();

  useEffect(() => {
    document.title = "Calendar Intake - Admin - Wolf Ranch Community Calendar";
  }, []);

  return (
    <div className="shell">
      <SiteNav />

      <main id="main-content">
        <header className="page-heading">
          <div className="eyebrow">Community Administration</div>
          <h1>Calendar Intake & Ingestion</h1>
          <p className="lead">Upload community flyer images or documents, let AI parse the events, and review before inserting into the Supabase calendar database.</p>
        </header>

        {authLoading && (
          <div className="panel query-loading" role="status" aria-live="polite">
            <div className="loading-dots" aria-hidden="true">
              <i /><i /><i />
            </div>
            <span>Checking authorization...</span>
          </div>
        )}

        {!authLoading && !session && (
          <div className="panel empty-state" role="status">
            <ShieldAlert size={36} aria-hidden="true" style={{ margin: "0 auto 12px", color: "var(--primary-color)" }} />
            <h2>Authentication Required</h2>
            <p className="small">Please sign in with an authorized admin Google account to access calendar intake.</p>
            <button className="primary" style={{ marginTop: 16 }} type="button" onClick={() => void signIn()}>
              Sign In with Google
            </button>
          </div>
        )}

        {!authLoading && session && !isAdmin && (
          <div className="panel empty-state" role="alert">
            <ShieldAlert size={36} aria-hidden="true" style={{ margin: "0 auto 12px", color: "var(--danger-text)" }} />
            <h2>Access Restricted</h2>
            <p className="small">Your account ({session.user.email}) does not have administrator permissions for calendar intake.</p>
          </div>
        )}

        {!authLoading && session && isAdmin && (
          <div className="vertical-flow">
            <AdminCalendarIntake apiUrl={API_URL} accessToken={session.access_token} />
          </div>
        )}
      </main>
    </div>
  );
}
