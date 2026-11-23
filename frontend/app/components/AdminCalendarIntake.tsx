"use client";

import { ChangeEvent, DragEvent, useState } from "react";
import { CheckCircle2, FileUp, Plus, Trash2, Upload, AlertCircle, RefreshCw } from "lucide-react";

export type HostType = "hoa_event" | "food_truck" | "paid_fitness" | "homeowner_hosted" | "hoa_announcement" | "community";
export type AudienceTag = "kids_friendly" | "adult_friendly" | "all_ages" | "unspecified";

export type ExtractedCalendarEvent = {
  id?: string;
  community_id: string;
  event_date: string;
  day_of_week: string;
  start_time_utc: string | null;
  end_time_utc: string | null;
  is_all_day: boolean;
  title: string;
  description: string;
  location: string;
  host_type: HostType;
  fee_required: boolean;
  rsvp_required: boolean;
  audience_tag: AudienceTag;
  is_kids_friendly: boolean;
  is_adult_friendly: boolean;
  notes: string;
};

type AdminCalendarIntakeProps = {
  apiUrl: string;
  accessToken: string;
  onSaved?: () => void;
};

export function AdminCalendarIntake({ apiUrl, accessToken, onSaved }: AdminCalendarIntakeProps) {
  const [stage, setStage] = useState<"idle" | "extracting" | "review" | "saving" | "success" | "error">("idle");
  const [isDragging, setIsDragging] = useState(false);
  const [extractedEvents, setExtractedEvents] = useState<ExtractedCalendarEvent[]>([]);
  const [saveResult, setSaveResult] = useState<{ inserted: number; updated: number } | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);

  async function handleExtract(file: File) {
    if (!file) return;
    setFileName(file.name);
    setStage("extracting");
    setErrorMessage(null);

    const formData = new FormData();
    formData.append("image", file);

    try {
      const response = await fetch(`${apiUrl}/api/v1/admin/calendar/extract`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail ?? `Extraction failed with status ${response.status}`);
      }

      const data = (await response.json()) as { events: ExtractedCalendarEvent[]; count: number };
      setExtractedEvents(data.events);
      setStage("review");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Image extraction failed.");
      setStage("error");
    }
  }

  async function handleBatchSave() {
    if (extractedEvents.length === 0) return;
    setStage("saving");
    setErrorMessage(null);

    try {
      const response = await fetch(`${apiUrl}/api/v1/admin/calendar/batch-upsert`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },
        body: JSON.stringify({ events: extractedEvents }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail ?? `Saving failed with status ${response.status}`);
      }

      const result = (await response.json()) as { inserted: number; updated: number };
      setSaveResult(result);
      setStage("success");
      onSaved?.();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to save events to database.");
      setStage("error");
    }
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) void handleExtract(file);
  }

  function handleDragOver(e: DragEvent) {
    e.preventDefault();
    setIsDragging(true);
  }

  function handleDragLeave(e: DragEvent) {
    e.preventDefault();
    setIsDragging(false);
  }

  function handleDrop(e: DragEvent) {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) void handleExtract(file);
  }

  function updateEvent(index: number, updates: Partial<ExtractedCalendarEvent>) {
    setExtractedEvents((prev) => {
      const next = [...prev];
      next[index] = { ...next[index], ...updates };
      return next;
    });
  }

  function removeEvent(index: number) {
    setExtractedEvents((prev) => prev.filter((_, i) => i !== index));
  }

  function addManualEvent() {
    const today = new Date().toISOString().slice(0, 10);
    const newEvent: ExtractedCalendarEvent = {
      community_id: "wolf_ranch",
      event_date: today,
      day_of_week: "",
      start_time_utc: null,
      end_time_utc: null,
      is_all_day: false,
      title: "New Event",
      description: "",
      location: "Wolf Ranch",
      host_type: "community",
      fee_required: false,
      rsvp_required: false,
      audience_tag: "all_ages",
      is_kids_friendly: true,
      is_adult_friendly: true,
      notes: "",
    };
    setExtractedEvents((prev) => [...prev, newEvent]);
  }

  function resetIntake() {
    setStage("idle");
    setExtractedEvents([]);
    setSaveResult(null);
    setErrorMessage(null);
    setFileName(null);
  }

  return (
    <section className="panel admin-intake-panel" aria-labelledby="admin-intake-title">
      <div className="intake-header">
        <div>
          <div className="eyebrow">Admin Portal</div>
          <h2 id="admin-intake-title">Calendar Intake & OCR</h2>
          <p className="small">Upload flyer images, review extracted events, and approve database insertion.</p>
        </div>
        {stage === "review" && (
          <button className="text-button" type="button" onClick={resetIntake}>
            <RefreshCw size={14} aria-hidden="true" /> <span>Start Over</span>
          </button>
        )}
      </div>

      {stage === "idle" && (
        <div
          className={`intake-dropzone ${isDragging ? "is-dragging" : ""}`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        >
          <FileUp size={36} className="dropzone-icon" aria-hidden="true" />
          <h3>Drag & Drop Calendar Flyer or PDF</h3>
          <p className="small">Upload JPEG, PNG, WEBP, or PDF calendar flyers. OpenAI Vision will extract structured event data.</p>
          <label className="primary dropzone-browse-btn" htmlFor="calendar-file-upload">
            <Upload size={16} aria-hidden="true" /> <span>Choose File</span>
            <input
              id="calendar-file-upload"
              type="file"
              className="sr-only"
              accept="image/*,application/pdf"
              onChange={handleFileChange}
            />
          </label>
        </div>
      )}

      {stage === "extracting" && (
        <div className="intake-processing" role="status" aria-live="polite">
          <div className="loading-dots" aria-hidden="true">
            <i /><i /><i />
          </div>
          <p><strong>Processing &quot;{fileName}&quot;</strong></p>
          <p className="small">Vision AI is reading event dates, times, titles, locations, and audience tags...</p>
        </div>
      )}

      {stage === "review" && (
        <div className="intake-review-flow">
          <div className="review-banner">
            <div>
              <strong>Extracted {extractedEvents.length} event(s) from {fileName}</strong>
              <p className="small">Verify details or edit fields below before inserting into the Supabase calendar database.</p>
            </div>
            <div className="review-banner-actions">
              <button className="icon-button" type="button" onClick={addManualEvent} title="Add another event" aria-label="Add another event">
                <Plus size={16} aria-hidden="true" /> <span>Add Event</span>
              </button>
              <button className="primary" type="button" onClick={handleBatchSave}>
                <CheckCircle2 size={16} aria-hidden="true" /> <span>Approve & Save to Database ({extractedEvents.length})</span>
              </button>
            </div>
          </div>

          <div className="review-event-list">
            {extractedEvents.map((event, index) => (
              <div className="review-event-card" key={index}>
                <div className="review-card-header">
                  <span className="event-index-badge">#{index + 1}</span>
                  <label htmlFor={`event-title-${index}`} className="sr-only">
                    Event #{index + 1} Title
                  </label>
                  <input
                    id={`event-title-${index}`}
                    className="review-input-title"
                    value={event.title}
                    placeholder="Event Title"
                    aria-label={`Event #${index + 1} Title`}
                    onChange={(e) => updateEvent(index, { title: e.target.value })}
                  />
                  <button
                    className="icon-button delete-btn"
                    type="button"
                    title="Remove event"
                    aria-label={`Remove event #${index + 1}: ${event.title || "Untitled"}`}
                    onClick={() => removeEvent(index)}
                  >
                    <Trash2 size={15} aria-hidden="true" />
                  </button>
                </div>

                <div className="review-card-grid">
                  <div>
                    <label htmlFor={`event-date-${index}`} className="field-label">Date (YYYY-MM-DD)</label>
                    <input
                      id={`event-date-${index}`}
                      type="date"
                      className="review-input"
                      value={event.event_date.slice(0, 10)}
                      onChange={(e) => updateEvent(index, { event_date: e.target.value })}
                    />
                  </div>

                  <div>
                    <label htmlFor={`event-location-${index}`} className="field-label">Location</label>
                    <input
                      id={`event-location-${index}`}
                      className="review-input"
                      value={event.location}
                      placeholder="e.g. The Den, River Camp"
                      onChange={(e) => updateEvent(index, { location: e.target.value })}
                    />
                  </div>

                  <div>
                    <label htmlFor={`event-host-${index}`} className="field-label">Host Type</label>
                    <select
                      id={`event-host-${index}`}
                      className="review-input"
                      value={event.host_type}
                      onChange={(e) => updateEvent(index, { host_type: e.target.value as HostType })}
                    >
                      <option value="hoa_event">HOA Event</option>
                      <option value="food_truck">Food Truck</option>
                      <option value="paid_fitness">Paid Fitness</option>
                      <option value="homeowner_hosted">Homeowner Hosted</option>
                      <option value="hoa_announcement">HOA Announcement</option>
                      <option value="community">Community</option>
                    </select>
                  </div>

                  <div>
                    <label htmlFor={`event-audience-${index}`} className="field-label">Audience Tag</label>
                    <select
                      id={`event-audience-${index}`}
                      className="review-input"
                      value={event.audience_tag}
                      onChange={(e) => updateEvent(index, {
                        audience_tag: e.target.value as AudienceTag,
                        is_kids_friendly: e.target.value === "kids_friendly" || e.target.value === "all_ages",
                        is_adult_friendly: e.target.value === "adult_friendly" || e.target.value === "all_ages",
                      })}
                    >
                      <option value="all_ages">All Ages</option>
                      <option value="kids_friendly">Kids Friendly</option>
                      <option value="adult_friendly">Adult Friendly</option>
                      <option value="unspecified">Unspecified</option>
                    </select>
                  </div>
                </div>

                <div className="review-card-flags">
                  <label className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={event.is_all_day}
                      onChange={(e) => updateEvent(index, { is_all_day: e.target.checked })}
                    />
                    <span>All Day</span>
                  </label>

                  <label className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={event.fee_required}
                      onChange={(e) => updateEvent(index, { fee_required: e.target.checked })}
                    />
                    <span>Fee Required</span>
                  </label>

                  <label className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={event.rsvp_required}
                      onChange={(e) => updateEvent(index, { rsvp_required: e.target.checked })}
                    />
                    <span>RSVP Required</span>
                  </label>
                </div>

                <div className="review-card-fullwidth">
                  <label htmlFor={`event-desc-${index}`} className="field-label">Description / Details</label>
                  <textarea
                    id={`event-desc-${index}`}
                    rows={2}
                    className="review-textarea"
                    value={event.description}
                    placeholder="Sub-details, performers, food vendors, rules..."
                    onChange={(e) => updateEvent(index, { description: e.target.value })}
                  />
                </div>
              </div>
            ))}
          </div>

          <div className="review-bottom-actions">
            <button className="primary" type="button" onClick={handleBatchSave}>
              <CheckCircle2 size={16} aria-hidden="true" /> <span>Approve & Save {extractedEvents.length} Event(s)</span>
            </button>
            <button className="text-button" type="button" onClick={resetIntake}>
              Discard
            </button>
          </div>
        </div>
      )}

      {stage === "saving" && (
        <div className="intake-processing" role="status" aria-live="polite">
          <div className="loading-dots" aria-hidden="true">
            <i /><i /><i />
          </div>
          <p><strong>Inserting events into database...</strong></p>
        </div>
      )}

      {stage === "success" && (
        <div className="intake-success-banner" role="status" aria-live="polite">
          <CheckCircle2 size={32} className="success-icon" aria-hidden="true" />
          <h3>Calendar Events Successfully Saved</h3>
          <p>
            Successfully processed {extractedEvents.length} events (<strong>{saveResult?.inserted ?? 0}</strong> newly inserted, <strong>{saveResult?.updated ?? 0}</strong> updated) into Supabase.
          </p>
          <div className="success-actions">
            <button className="primary" type="button" onClick={resetIntake}>
              Ingest Another Calendar
            </button>
          </div>
        </div>
      )}

      {stage === "error" && (
        <div className="intake-error-banner" role="alert">
          <AlertCircle size={28} className="error-icon" aria-hidden="true" />
          <div>
            <strong>Error processing intake</strong>
            <p className="small">{errorMessage}</p>
          </div>
          <button className="text-button" type="button" onClick={resetIntake}>
            Try Again
          </button>
        </div>
      )}
    </section>
  );
}
