"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { Send, CheckCircle2 } from "lucide-react";
import type { Session } from "@supabase/supabase-js";
import { CalendarBoard } from "../components/CalendarBoard";
import { SiteNav } from "../components/SiteNav";
import { useAuth } from "../context/AuthContext";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
type EventRow = { id?: string; event_date: string; start_time_utc?: string; end_time_utc?: string; is_all_day?: boolean; title: string; location?: string; audience_tag?: string; description?: string };
type ResponsePayload = { answer?: string; rows?: EventRow[] };
type QuotaStatus = { is_unlimited: boolean; limit: number | null; used: number; remaining: number | null; window: string; resets_at: string | null };
const EXAMPLE_QUESTIONS = [
  "Show me kids-friendly events",
  "Help me find events for adults",
  "Provide events where I can make friends",
  "Any workout events?",
  "Coffee related events",
];

function resultStartMonth(rows: EventRow[] | undefined) {
  if (!rows?.length) return undefined;
  return rows.reduce((earliest, row) => row.event_date < earliest ? row.event_date : earliest, rows[0].event_date).slice(0, 7);
}

async function hashKey(value: string) {
  const bytes = new TextEncoder().encode(value);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

export default function AskPage() {
  const { session, authLoading, signIn, signOut } = useAuth();
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<ResponsePayload | null>(null);
  const [busy, setBusy] = useState(false);
  const [quota, setQuota] = useState<QuotaStatus | null>(null);
  const [authDialogOpen, setAuthDialogOpen] = useState(false);
  const [quotaDialogOpen, setQuotaDialogOpen] = useState(false);
  const [turnId, setTurnId] = useState<string | null>(null);
  const [feedbackRating, setFeedbackRating] = useState<"thumbs_up" | "thumbs_down" | null>(null);
  const [feedbackComment, setFeedbackComment] = useState("");
  const [feedbackStatus, setFeedbackStatus] = useState("");
  const [feedbackSubmitted, setFeedbackSubmitted] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const lastSubmitTimeRef = useRef<number>(0);

  useEffect(() => () => abortRef.current?.abort(), []);

  useEffect(() => {
    document.title = "Ask the Calendar - Wolf Ranch Community Calendar";
  }, []);

  useEffect(() => {
    if (!authDialogOpen && !quotaDialogOpen) return;
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        setAuthDialogOpen(false);
        setQuotaDialogOpen(false);
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [authDialogOpen, quotaDialogOpen]);

  async function refreshQuota(activeSession: Session) {
    try {
      const response = await fetch(`${API_URL}/api/v1/chat/quota`, {
        headers: { Authorization: `Bearer ${activeSession.access_token}` },
      });
      if (!response.ok) return;
      const body = (await response.json()) as { quota: QuotaStatus };
      setQuota(body.quota);
    } catch {
      // Ignore network errors on initial background quota fetch
    }
  }

  useEffect(() => {
    if (!session) {
      setQuota(null);
      return;
    }
    void refreshQuota(session);
  }, [session]);

  async function askQuestion(value: string) {
    const nextQuestion = value.trim();
    const now = Date.now();
    if (now - lastSubmitTimeRef.current < 1000) return;
    if (busy || (!quota?.is_unlimited && quota?.remaining === 0) || !nextQuestion) return;
    lastSubmitTimeRef.current = now;
    if (!session) {
      setAuthDialogOpen(true);
      return;
    }
    setBusy(true);
    setResult(null);
    setFeedbackSubmitted(false);
    abortRef.current = new AbortController();
    setQuestion(nextQuestion);
    const normalized = nextQuestion.toLowerCase();
    const hour = new Date().toISOString().slice(0, 13);
    const key = await hashKey(`${session.user.id}:${normalized}:${hour}`);
    try {
      const headers = { "Content-Type": "application/json", "Idempotency-Key": key, Authorization: `Bearer ${session.access_token}` };
      const response = await fetch(`${API_URL}/api/v1/chat/query`, { method: "POST", signal: abortRef.current.signal, headers, body: JSON.stringify({ question: nextQuestion }) });
      if (response.status === 401) {
        setAuthDialogOpen(true);
        return;
      }
      if (!response.ok) {
        const body = await response.json();
        if (response.status === 429) {
          await refreshQuota(session);
          setQuotaDialogOpen(true);
        }
        throw new Error(body.detail ?? "Request failed");
      }
      const body = await response.json();
      setResult(body.payload);
      if (body.quota) {
        setQuota(body.quota);
        if (!body.quota.is_unlimited && body.quota.remaining === 0) setQuotaDialogOpen(true);
      }
      setTurnId(body.turn_id ?? null);
      setFeedbackRating(null);
      setFeedbackComment("");
      setFeedbackStatus("");
    } catch (reason) {
      setFeedbackStatus(reason instanceof Error ? reason.message : "Request failed");
    } finally {
      setBusy(false);
      abortRef.current = null;
    }
  }

  async function submitFeedback() {
    if (!turnId || !feedbackRating || !session) return;
    try {
      const response = await fetch(`${API_URL}/api/v1/chat/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${session.access_token}` },
        body: JSON.stringify({ turn_id: turnId, rating: feedbackRating, comment: feedbackComment.trim() || null }),
      });
      if (response.ok) {
        setFeedbackSubmitted(true);
        setFeedbackStatus("Thank you for your feedback!");
      } else {
        setFeedbackStatus("Feedback could not be recorded.");
      }
    } catch {
      setFeedbackStatus("Feedback could not be recorded.");
    }
  }

  async function ask(event: FormEvent) {
    event.preventDefault();
    await askQuestion(question);
  }

  const quotaExhausted = !quota?.is_unlimited && quota?.remaining === 0;
  const quotaLabel = quota?.is_unlimited
    ? `Admin access: ${quota?.used ?? 0} question${quota?.used === 1 ? "" : "s"} asked (unlimited)`
    : `7-day quota: ${quota?.used ?? 0} / ${quota?.limit ?? 5}`;
  const quotaReset = quota?.resets_at
    ? new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(quota.resets_at))
    : null;

  return (
    <div className="shell">
      <SiteNav />
      <main id="main-content">
        <header className="masthead">
          <div>
            <div className="eyebrow">Wolf Ranch / Community desk</div>
            <h1>Find your next neighborhood moment.</h1>
          </div>
          <div className="quota" role="status" aria-label="Question quota">{quotaLabel}</div>
        </header>

        <div className="vertical-flow">
          {busy && (
            <section className="panel query-loading" role="status" aria-live="polite">
              <span className="loading-dots" aria-hidden="true"><i /><i /><i /></span>
              <span>Searching the community calendar...</span>
            </section>
          )}

          {result?.rows?.length ? (
            <div className="result-calendar-enter">
              <CalendarBoard apiUrl={API_URL} mode="month" eventsOnly={result.rows} initialMonth={resultStartMonth(result.rows)} heading="Search results" />
            </div>
          ) : null}

          <section className="panel ask-panel">
            <h2>Ask the calendar</h2>
            <form className="ask" onSubmit={ask}>
              <label htmlFor="ask-input" className="sr-only">Ask a question about the calendar</label>
              <input
                id="ask-input"
                value={question}
                readOnly={busy}
                onChange={(event) => setQuestion(event.target.value)}
                placeholder="What is happening this weekend?"
                aria-label="What is happening this weekend?"
              />
              <button className="primary" disabled={busy || quotaExhausted} type="submit">
                <Send size={16} aria-hidden="true" />
                <span>{busy ? "Searching" : quotaExhausted ? "Quota reached" : "Ask"}</span>
              </button>
            </form>
            <div className="example-questions" aria-label="Example questions">
              <span className="small">Try asking:</span>
              <div className="example-question-list">
                {EXAMPLE_QUESTIONS.map((example) => (
                  <button className="example-question" disabled={busy || quotaExhausted} key={example} onClick={() => void askQuestion(example)} type="button">
                    {example}
                  </button>
                ))}
              </div>
            </div>
            {result?.answer && (
              <div role="status" aria-live="polite">
                <p className="answer response-answer">{result.answer}</p>
              </div>
            )}
            {turnId && (
              <div className="feedback-section" aria-label="Answer feedback">
                {!feedbackSubmitted ? (
                  <form
                    className="feedback-form"
                    onSubmit={(e) => {
                      e.preventDefault();
                      void submitFeedback();
                    }}
                  >
                    <div className="feedback-rating-row" role="group" aria-label="Answer helpfulness">
                      <span className="small">Was this answer helpful?</span>
                      <button
                        type="button"
                        className="feedback-rating-btn"
                        aria-pressed={feedbackRating === "thumbs_up"}
                        onClick={() => setFeedbackRating("thumbs_up")}
                      >
                        👍 Helpful
                      </button>
                      <button
                        type="button"
                        className="feedback-rating-btn"
                        aria-pressed={feedbackRating === "thumbs_down"}
                        onClick={() => setFeedbackRating("thumbs_down")}
                      >
                        👎 Not helpful
                      </button>
                    </div>
                    {feedbackRating && (
                      <div className="feedback-comment-box">
                        <label htmlFor="feedback-comment" className="sr-only">Feedback comment</label>
                        <textarea
                          id="feedback-comment"
                          className="feedback-textarea"
                          rows={3}
                          value={feedbackComment}
                          maxLength={4000}
                          placeholder="Provide details about how the search performed (press Enter to send)..."
                          aria-label="Provide details about how the search performed"
                          onChange={(event) => setFeedbackComment(event.target.value)}
                          onKeyDown={(event) => {
                            if (event.key === "Enter" && !event.shiftKey) {
                              event.preventDefault();
                              void submitFeedback();
                            }
                          }}
                        />
                        <div className="feedback-actions">
                          <button className="primary" type="submit">
                            Submit Feedback
                          </button>
                        </div>
                      </div>
                    )}
                    {feedbackStatus && <span className="small error" role="alert">{feedbackStatus}</span>}
                  </form>
                ) : (
                  <div className="feedback-success-msg" role="status">
                    <CheckCircle2 size={16} aria-hidden="true" style={{ color: "var(--success-text)" }} />
                    <span className="small">Thank you for your feedback!</span>
                  </div>
                )}
              </div>
            )}
            {result?.rows?.length ? <p className="small result-note">The matching events are highlighted on this week&apos;s calendar.</p> : null}
          </section>

          <CalendarBoard apiUrl={API_URL} mode="week" />
        </div>
        {authDialogOpen && <div className="dialog-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setAuthDialogOpen(false); }}>
          <section className="auth-dialog" role="dialog" aria-modal="true" aria-labelledby="auth-dialog-title">
            <button className="dialog-close" type="button" aria-label="Close sign-in dialog" onClick={() => setAuthDialogOpen(false)}>×</button>
            <div className="eyebrow">Account required</div>
            <h2 id="auth-dialog-title">Sign in to ask the calendar</h2>
            <p>Google Sign-in is required to send a query. It helps us protect the calendar from automated attacks and keep each person&apos;s seven-day limit and feedback tied to the right account.</p>
            <div className="dialog-actions"><button className="primary" type="button" onClick={() => { setAuthDialogOpen(false); void signIn(); }}>Continue with Google</button><button className="text-button" type="button" onClick={() => setAuthDialogOpen(false)}>Maybe later</button></div>
          </section>
        </div>}
        {quotaDialogOpen && <div className="dialog-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setQuotaDialogOpen(false); }}>
          <section className="auth-dialog" role="dialog" aria-modal="true" aria-labelledby="quota-dialog-title">
            <button className="dialog-close" type="button" aria-label="Close quota dialog" onClick={() => setQuotaDialogOpen(false)}>×</button>
            <div className="eyebrow">Question limit reached</div>
            <h2 id="quota-dialog-title">You&apos;ve used this week&apos;s questions.</h2>
            <p>Community accounts can ask up to five questions in any rolling seven-day period.{quotaReset ? ` Your next question becomes available ${quotaReset}.` : " Please check back soon."}</p>
            <div className="dialog-actions"><button className="primary" type="button" onClick={() => setQuotaDialogOpen(false)}>Got it</button></div>
          </section>
        </div>}
      </main>
    </div>
  );
}
