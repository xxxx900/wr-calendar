"use client";

import { useEffect, useMemo, useState } from "react";
import {
  CalendarCheck,
  Heart,
  Lightbulb,
  Star,
  CheckCircle2,
  Trash2,
  Edit3,
  MessageSquare,
  Users,
  AlertCircle,
  X,
  LogIn,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import type { CalendarEvent } from "./CalendarBoard";

export type ReactionType = "going" | "love" | "helpful";

export type ReviewItem = {
  id: string;
  event_id: string;
  rating: number;
  comment?: string | null;
  attended_event: boolean;
  is_anonymous: boolean;
  is_author: boolean;
  author_name: string;
  author_avatar?: string | null;
  created_at: string;
  updated_at: string;
  is_edited: boolean;
};

export type EventInteractions = {
  event_id: string;
  review_count: number;
  average_rating: number | null;
  attended_count: number;
  reaction_counts: { going: number; love: number; helpful: number };
  user_reaction?: string | null;
  user_review?: ReviewItem | null;
};

export function formatRating(val: number | string | null | undefined): string {
  if (val === null || val === undefined || val === "") return "";
  const num = typeof val === "number" ? val : parseFloat(String(val));
  return !isNaN(num) ? num.toFixed(1) : "";
}

type EventReviewsProps = {
  event: CalendarEvent;
  apiUrl: string;
  onInteractionsUpdated?: (
    eventId: string,
    counts: { going: number; love: number; helpful: number },
    avgRating: number | null,
    reviewCount: number
  ) => void;
};

function getEventTimeline(eventDateStr: string): "past" | "today" | "future" {
  try {
    const todayStr = new Intl.DateTimeFormat("en-CA", {
      timeZone: "America/Chicago",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).format(new Date());

    const cleanDate = eventDateStr.slice(0, 10);
    if (cleanDate < todayStr) return "past";
    if (cleanDate === todayStr) return "today";
    return "future";
  } catch {
    const today = new Date().toISOString().slice(0, 10);
    const cleanDate = eventDateStr.slice(0, 10);
    if (cleanDate < today) return "past";
    if (cleanDate === today) return "today";
    return "future";
  }
}

export function EventReviews({ event, apiUrl, onInteractionsUpdated }: EventReviewsProps) {
  const { session, user, signIn, isAdmin } = useAuth();
  const eventId = event.id;

  const [interactions, setInteractions] = useState<EventInteractions | null>(null);
  const [reviews, setReviews] = useState<ReviewItem[]>([]);
  const [starDistribution, setStarDistribution] = useState<Record<string, number>>({
    "1": 0, "2": 0, "3": 0, "4": 0, "5": 0,
  });
  const [totalReviews, setTotalReviews] = useState(0);
  const [averageRating, setAverageRating] = useState<number | null>(null);

  const [loadingInteractions, setLoadingInteractions] = useState(true);
  const [loadingReviews, setLoadingReviews] = useState(false);
  const [togglingReaction, setTogglingReaction] = useState(false);

  // Sorting & Filtering
  const [sort, setSort] = useState<"rating_desc" | "recent">("rating_desc");
  const [starFilter, setStarFilter] = useState<number | null>(null);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);

  // Review Form
  const [isWriting, setIsWriting] = useState(false);
  const [formRating, setFormRating] = useState(5);
  const [formComment, setFormComment] = useState("");
  const [formAttended, setFormAttended] = useState(false);
  const [formAnonymous, setFormAnonymous] = useState(false);
  const [submittingReview, setSubmittingReview] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // Modals
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deletingReview, setDeletingReview] = useState(false);

  const timeline = useMemo(() => getEventTimeline(event.event_date), [event.event_date]);
  const isPast = timeline === "past";
  const isFuture = timeline === "future";

  useEffect(() => {
    if (!showAuthModal && !showDeleteConfirm) return;
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        setShowAuthModal(false);
        setShowDeleteConfirm(false);
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [showAuthModal, showDeleteConfirm]);

  // Load interactions
  async function loadInteractions() {
    if (!eventId) return;
    setLoadingInteractions(true);
    try {
      const headers: Record<string, string> = {};
      if (session?.access_token) {
        headers["Authorization"] = `Bearer ${session.access_token}`;
      }
      const res = await fetch(`${apiUrl}/api/v1/events/${eventId}/interactions`, { headers });
      if (res.ok) {
        const data: EventInteractions = await res.json();
        setInteractions(data);
        if (data.user_review) {
          setFormRating(data.user_review.rating);
          setFormComment(data.user_review.comment ?? "");
          setFormAttended(data.user_review.attended_event);
          setFormAnonymous(data.user_review.is_anonymous);
        }
        if (onInteractionsUpdated) {
          onInteractionsUpdated(
            eventId,
            data.reaction_counts,
            data.average_rating,
            data.review_count
          );
        }
      }
    } catch {
      // Fail open
    } finally {
      setLoadingInteractions(false);
    }
  }

  // Load reviews page
  async function loadReviews(resetOffset = false) {
    if (!eventId) return;
    setLoadingReviews(true);
    const targetOffset = resetOffset ? 0 : offset;
    try {
      const headers: Record<string, string> = {};
      if (session?.access_token) {
        headers["Authorization"] = `Bearer ${session.access_token}`;
      }
      const params = new URLSearchParams({
        sort,
        limit: "5",
        offset: String(targetOffset),
      });
      if (starFilter !== null) {
        params.append("star_filter", String(starFilter));
      }

      const res = await fetch(`${apiUrl}/api/v1/events/${eventId}/reviews?${params.toString()}`, { headers });
      if (res.ok) {
        const data = await res.json();
        setTotalReviews(data.total_reviews);
        setAverageRating(data.average_rating);
        setStarDistribution(data.star_distribution ?? { "1": 0, "2": 0, "3": 0, "4": 0, "5": 0 });
        if (resetOffset) {
          setReviews(data.reviews);
          setOffset(5);
        } else {
          setReviews((prev) => [...prev, ...data.reviews]);
          setOffset((prev) => prev + 5);
        }
        setHasMore(targetOffset + data.reviews.length < data.total_reviews);
      }
    } catch {
      // Fail open
    } finally {
      setLoadingReviews(false);
    }
  }

  useEffect(() => {
    void loadInteractions();
  }, [eventId, session?.access_token]);

  useEffect(() => {
    void loadReviews(true);
  }, [eventId, sort, starFilter, session?.access_token]);

  // Reaction Toggle
  async function handleToggleReaction(reactionType: ReactionType) {
    if (!user) {
      setShowAuthModal(true);
      return;
    }
    if (!eventId || togglingReaction) return;

    if (reactionType === "going" && isPast) {
      return; // Disabled for past events
    }

    setTogglingReaction(true);

    // Optimistic UI update
    const previous = interactions?.user_reaction;
    const isToggleOff = previous === reactionType;
    const nextReaction = isToggleOff ? null : reactionType;

    setInteractions((prev) => {
      if (!prev) return null;
      const counts = { ...prev.reaction_counts };
      if (previous && counts[previous as ReactionType] !== undefined) {
        counts[previous as ReactionType] = Math.max(0, counts[previous as ReactionType] - 1);
      }
      if (nextReaction && counts[nextReaction] !== undefined) {
        counts[nextReaction] = (counts[nextReaction] ?? 0) + 1;
      }
      return {
        ...prev,
        user_reaction: nextReaction,
        reaction_counts: counts,
      };
    });

    try {
      const res = await fetch(`${apiUrl}/api/v1/events/${eventId}/reactions`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session?.access_token}`,
        },
        body: JSON.stringify({ reaction_type: reactionType }),
      });
      if (res.ok) {
        const data = await res.json();
        setInteractions((prev) =>
          prev
            ? {
                ...prev,
                user_reaction: data.reaction_type,
                reaction_counts: data.reaction_counts,
              }
            : null
        );
        if (onInteractionsUpdated && interactions) {
          onInteractionsUpdated(
            eventId,
            data.reaction_counts,
            interactions.average_rating,
            interactions.review_count
          );
        }
      } else {
        // Revert on failure
        void loadInteractions();
      }
    } catch {
      void loadInteractions();
    } finally {
      setTogglingReaction(false);
    }
  }

  // Review Submit
  async function handleSubmitReview(e: React.FormEvent) {
    e.preventDefault();
    if (!user) {
      setShowAuthModal(true);
      return;
    }
    if (!eventId) return;

    setSubmittingReview(true);
    setFormError(null);

    try {
      const res = await fetch(`${apiUrl}/api/v1/events/${eventId}/reviews`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session?.access_token}`,
        },
        body: JSON.stringify({
          rating: formRating,
          comment: formComment.trim() || null,
          attended_event: formAttended,
          is_anonymous: formAnonymous,
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Failed to submit review." }));
        throw new Error(err.detail || "Failed to submit review.");
      }

      setIsWriting(false);
      await loadInteractions();
      await loadReviews(true);
    } catch (err: any) {
      setFormError(err.message || "Failed to submit review.");
    } finally {
      setSubmittingReview(false);
    }
  }

  // Review Delete
  async function handleDeleteReview() {
    if (!user || !eventId) return;
    setDeletingReview(true);
    try {
      const res = await fetch(`${apiUrl}/api/v1/events/${eventId}/reviews`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${session?.access_token}`,
        },
      });
      if (res.ok) {
        setShowDeleteConfirm(false);
        setIsWriting(false);
        setFormComment("");
        setFormRating(5);
        setFormAttended(false);
        await loadInteractions();
        await loadReviews(true);
      }
    } catch {
      // Fail open
    } finally {
      setDeletingReview(false);
    }
  }

  const userReview = interactions?.user_review;

  return (
    <div className="event-interactions-section">
      {/* 1. DISTINCT REACTION TRIO */}
      <div className="reaction-bar-container">
        <span className="reaction-bar-label">Community Reactions</span>
        <div className="reaction-bar">
          {/* Planning to go (Intent) - Hidden/disabled on past events */}
          {!isPast && (
            <button
              type="button"
              className={`reaction-btn reaction-going ${
                interactions?.user_reaction === "going" ? "is-active" : ""
              }`}
              onClick={() => handleToggleReaction("going")}
              title="I'm planning to go"
            >
              <CalendarCheck size={16} />
              <span>Planning to go</span>
              <span className="reaction-badge">{interactions?.reaction_counts?.going ?? 0}</span>
            </button>
          )}

          {/* Love this (Affection) */}
          <button
            type="button"
            className={`reaction-btn reaction-love ${
              interactions?.user_reaction === "love" ? "is-active" : ""
            }`}
            onClick={() => handleToggleReaction("love")}
            title="Love this"
          >
            <Heart size={16} />
            <span>Love this</span>
            <span className="reaction-badge">{interactions?.reaction_counts?.love ?? 0}</span>
          </button>

          {/* Helpful (Utility) */}
          <button
            type="button"
            className={`reaction-btn reaction-helpful ${
              interactions?.user_reaction === "helpful" ? "is-active" : ""
            }`}
            onClick={() => handleToggleReaction("helpful")}
            title="Helpful notice"
          >
            <Lightbulb size={16} />
            <span>Helpful</span>
            <span className="reaction-badge">{interactions?.reaction_counts?.helpful ?? 0}</span>
          </button>
        </div>
      </div>

      <hr className="section-divider" />

      {/* 2. COMMUNITY RATING & ATTENDANCE HEADER */}
      <div className="reviews-header-block">
        <div className="reviews-summary-stats">
          <div className="rating-overall">
            <span className="rating-num">
              {formatRating(averageRating) || "—"}
            </span>
            <div className="stars-row" aria-label={`Rating: ${formatRating(averageRating) || 0} out of 5 stars`}>
              {[1, 2, 3, 4, 5].map((s) => {
                const numericAvg = typeof averageRating === "number" ? averageRating : parseFloat(String(averageRating ?? ""));
                const isFilled = !isNaN(numericAvg) && s <= Math.round(numericAvg);
                return (
                  <Star
                    key={s}
                    size={14}
                    className={isFilled ? "star-icon is-filled" : "star-icon is-empty"}
                  />
                );
              })}
            </div>
            <span className="review-count-text">
              ({totalReviews} {totalReviews === 1 ? "review" : "reviews"})
            </span>
          </div>

          {(interactions?.attended_count ?? 0) > 0 && (
            <div className="attended-stat-badge">
              <Users size={14} />
              <span>
                <strong>{interactions?.attended_count}</strong> {interactions?.attended_count === 1 ? "neighbor" : "neighbors"} attended
              </span>
            </div>
          )}
        </div>

        {/* Action Button to write or edit review */}
        {!isFuture && (
          <div>
            {!userReview && !isWriting && (
              <button
                type="button"
                className="write-review-trigger-btn"
                onClick={() => {
                  if (!user) {
                    setShowAuthModal(true);
                  } else {
                    setIsWriting(true);
                  }
                }}
              >
                <MessageSquare size={14} />
                <span>Write a Review</span>
              </button>
            )}
          </div>
        )}
      </div>

      {/* 3. FUTURE EVENT BANNER */}
      {isFuture && (
        <div className="future-review-banner">
          <CalendarCheck size={16} className="future-icon" />
          <p>
            Reviews and attendance unlock once this event occurs on{" "}
            <strong>{event.event_date.slice(0, 10)}</strong>. React above to share your excitement!
          </p>
        </div>
      )}

      {/* 4. AUTHOR'S REVIEW CARD */}
      {userReview && !isWriting && (
        <div className="user-review-highlight-card">
          <div className="review-card-header">
            <div className="author-info">
              <span className="author-badge">Your Review</span>
              {userReview.is_anonymous && (
                <span className="anon-indicator" title="Your identity is hidden from neighbors">
                  Anonymous to neighbors
                </span>
              )}
              {userReview.attended_event && (
                <span className="attended-pill">
                  <CheckCircle2 size={12} /> Attended
                </span>
              )}
            </div>
            <div className="card-actions">
              <button
                type="button"
                className="icon-action-btn"
                onClick={() => setIsWriting(true)}
                title="Edit review"
                aria-label="Edit your review"
              >
                <Edit3 size={14} aria-hidden="true" /> <span>Edit</span>
              </button>
              <button
                type="button"
                className="icon-action-btn danger"
                onClick={() => setShowDeleteConfirm(true)}
                title="Delete review"
                aria-label="Delete your review"
              >
                <Trash2 size={14} aria-hidden="true" /> <span>Delete</span>
              </button>
            </div>
          </div>

          <div className="stars-row">
            {[1, 2, 3, 4, 5].map((s) => (
              <Star
                key={s}
                size={13}
                aria-hidden="true"
                className={s <= userReview.rating ? "star-icon is-filled" : "star-icon is-empty"}
              />
            ))}
            {userReview.is_edited && <span className="edited-badge">(edited)</span>}
          </div>

          {userReview.comment && <p className="review-comment-body">{userReview.comment}</p>}
        </div>
      )}

      {/* 5. WRITE / EDIT REVIEW FORM */}
      {isWriting && !isFuture && (
        <form className="review-form-panel" onSubmit={handleSubmitReview}>
          <div className="form-header">
            <h3>{userReview ? "Edit Your Review" : "Write a Community Review"}</h3>
            <button
              type="button"
              className="close-form-btn"
              onClick={() => setIsWriting(false)}
              aria-label="Cancel review"
            >
              <X size={15} aria-hidden="true" />
            </button>
          </div>

          {formError && (
            <div className="form-error-banner" role="alert">
              <AlertCircle size={14} aria-hidden="true" />
              <span>{formError}</span>
            </div>
          )}

          {/* Star selector */}
          <div className="form-field">
            <label>Rating</label>
            <div className="interactive-star-selector">
              {[1, 2, 3, 4, 5].map((s) => (
                <button
                  type="button"
                  key={s}
                  className={`star-choice-btn ${s <= formRating ? "is-selected" : ""}`}
                  onClick={() => setFormRating(s)}
                  aria-label={`${s} stars`}
                >
                  <Star size={20} className={s <= formRating ? "star-icon is-filled" : "star-icon is-empty"} />
                </button>
              ))}
              <span className="star-rating-label">
                {formRating === 5 && "Excellent"}
                {formRating === 4 && "Good"}
                {formRating === 3 && "Average"}
                {formRating === 2 && "Fair"}
                {formRating === 1 && "Poor"}
              </span>
            </div>
          </div>

          {/* Attendance Checkbox */}
          <label className="form-checkbox-label">
            <input
              type="checkbox"
              checked={formAttended}
              onChange={(e) => setFormAttended(e.target.checked)}
            />
            <span>I have been to this event</span>
          </label>

          {/* Anonymous Toggle */}
          <label className="form-checkbox-label">
            <input
              type="checkbox"
              checked={formAnonymous}
              onChange={(e) => setFormAnonymous(e.target.checked)}
            />
            <span>Post anonymously to neighbors (name and profile hidden)</span>
          </label>

          {/* Comment */}
          <div className="form-field">
            <label htmlFor="review-comment">Review (optional)</label>
            <textarea
              id="review-comment"
              rows={3}
              maxLength={3000}
              placeholder="What was your favorite part? Any tips for next time?"
              value={formComment}
              onChange={(e) => setFormComment(e.target.value)}
            />
            <span className="char-count">{formComment.length} / 3000</span>
          </div>

          <div className="form-footer-actions">
            <button
              type="button"
              className="cancel-btn"
              onClick={() => setIsWriting(false)}
              disabled={submittingReview}
            >
              Cancel
            </button>
            <button type="submit" className="submit-btn" disabled={submittingReview}>
              {submittingReview ? "Submitting..." : userReview ? "Update Review" : "Publish Review"}
            </button>
          </div>
        </form>
      )}

      {/* 6. NEIGHBOR REVIEWS LIST CONTROLS */}
      {totalReviews > 0 && (
        <div className="reviews-filter-sort-bar">
          {/* Star Filter Pills */}
          <div className="star-filter-pills">
            <button
              type="button"
              className={`pill-btn ${starFilter === null ? "is-active" : ""}`}
              onClick={() => setStarFilter(null)}
            >
              All ({totalReviews})
            </button>
            {[5, 4, 3, 2, 1].map((star) => (
              <button
                type="button"
                key={star}
                className={`pill-btn ${starFilter === star ? "is-active" : ""}`}
                onClick={() => setStarFilter(starFilter === star ? null : star)}
              >
                {star}★ ({starDistribution[String(star)] ?? 0})
              </button>
            ))}
          </div>

          {/* Sort Selector */}
          <div className="sort-selector">
            <label htmlFor="reviews-sort">Sort by:</label>
            <select
              id="reviews-sort"
              value={sort}
              onChange={(e) => setSort(e.target.value as "rating_desc" | "recent")}
            >
              <option value="rating_desc">Highest Rated</option>
              <option value="recent">Most Recent</option>
            </select>
          </div>
        </div>
      )}

      {/* 7. REVIEWS LIST */}
      <div className="neighbor-reviews-list">
        {reviews.map((r) => (
          <div key={r.id} className="neighbor-review-item">
            <div className="review-item-header">
              <div className="user-meta">
                <div className="avatar-placeholder">
                  {r.author_name.charAt(0).toUpperCase()}
                </div>
                <div>
                  <div className="author-name-line">
                    <span className="author-name">{r.author_name}</span>
                    {r.attended_event && (
                      <span className="attended-pill">
                        <CheckCircle2 size={11} /> Attended
                      </span>
                    )}
                  </div>
                  <div className="review-sub-meta">
                    <div className="stars-row">
                      {[1, 2, 3, 4, 5].map((s) => (
                        <Star
                          key={s}
                          size={12}
                          className={s <= r.rating ? "star-icon is-filled" : "star-icon is-empty"}
                        />
                      ))}
                    </div>
                    <time dateTime={r.created_at}>
                      {r.created_at.slice(0, 10)}
                    </time>
                    {r.is_edited && <span className="edited-badge">(edited)</span>}
                  </div>
                </div>
              </div>

              {/* Admin moderation delete button for other users' reviews */}
              {isAdmin && !r.is_author && (
                <button
                  type="button"
                  className="icon-action-btn danger"
                  title="Moderate (Delete review)"
                  onClick={async () => {
                    if (confirm("Are you sure you want to remove this review as an admin?")) {
                      try {
                        await fetch(`${apiUrl}/api/v1/events/${eventId}/reviews`, {
                          method: "DELETE",
                          headers: { Authorization: `Bearer ${session?.access_token}` },
                        });
                        await loadInteractions();
                        await loadReviews(true);
                      } catch {
                        // Fail open
                      }
                    }
                  }}
                >
                  <Trash2 size={13} />
                </button>
              )}
            </div>

            {r.comment && <p className="review-comment-body">{r.comment}</p>}
          </div>
        ))}

        {loadingReviews && <p className="loading-state">Loading reviews...</p>}

        {!loadingReviews && reviews.length === 0 && totalReviews === 0 && !isFuture && (
          <p className="empty-reviews-state">
            No reviews yet. Be the first to share your experience with neighbors!
          </p>
        )}

        {hasMore && !loadingReviews && (
          <div className="load-more-container">
            <button
              type="button"
              className="load-more-btn"
              onClick={() => loadReviews(false)}
            >
              Load more reviews
            </button>
          </div>
        )}
      </div>

      {/* 8. AUTH PROMPT MODAL */}
      {showAuthModal && (
        <div className="inline-auth-modal-backdrop" role="presentation" onClick={() => setShowAuthModal(false)}>
          <div className="inline-auth-modal-card" role="dialog" aria-modal="true" aria-labelledby="auth-modal-title" onClick={(e) => e.stopPropagation()}>
            <button
              type="button"
              className="dialog-close"
              onClick={() => setShowAuthModal(false)}
              aria-label="Close sign in dialog"
            >
              ×
            </button>
            <div className="auth-modal-icon">
              <Heart size={28} aria-hidden="true" />
            </div>
            <h3 id="auth-modal-title">Join the Conversation</h3>
            <p>
              Sign in with Google to react, confirm attendance, and share your review with Wolf Ranch neighbors.
            </p>
            <div className="auth-modal-actions">
              <button
                type="button"
                className="google-sign-in-btn"
                onClick={async () => {
                  setShowAuthModal(false);
                  await signIn();
                }}
              >
                <LogIn size={16} aria-hidden="true" />
                <span>Sign in with Google</span>
              </button>
              <button
                type="button"
                className="cancel-btn"
                onClick={() => setShowAuthModal(false)}
              >
                Maybe later
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 9. DELETE CONFIRMATION MODAL */}
      {showDeleteConfirm && (
        <div className="inline-auth-modal-backdrop" role="presentation" onClick={() => setShowDeleteConfirm(false)}>
          <div className="inline-auth-modal-card" role="dialog" aria-modal="true" aria-labelledby="delete-modal-title" onClick={(e) => e.stopPropagation()}>
            <button
              type="button"
              className="dialog-close"
              onClick={() => setShowDeleteConfirm(false)}
              aria-label="Close delete confirmation dialog"
            >
              ×
            </button>
            <div className="auth-modal-icon danger">
              <Trash2 size={26} aria-hidden="true" />
            </div>
            <h3 id="delete-modal-title">Delete Your Review?</h3>
            <p>
              Your review and rating will be removed from this event. You can always write a new review in the future.
            </p>
            <div className="auth-modal-actions">
              <button
                type="button"
                className="confirm-delete-btn"
                onClick={handleDeleteReview}
                disabled={deletingReview}
              >
                {deletingReview ? "Deleting..." : "Yes, Delete"}
              </button>
              <button
                type="button"
                className="cancel-btn"
                onClick={() => setShowDeleteConfirm(false)}
                disabled={deletingReview}
              >
                Keep Review
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
