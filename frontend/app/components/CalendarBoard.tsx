"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, MapPin, Maximize2, Minimize2, RotateCcw } from "lucide-react";
import { EventReviews, formatRating } from "./EventReviews";
import { useCalendarSwipe } from "../hooks/useCalendarSwipe";

type DayShelfData = {
  date: Date;
  dateStr: string;
  events: CalendarEvent[];
};

export type CalendarEvent = {
  id?: string;
  event_date: string;
  start_time_utc?: string | null;
  end_time_utc?: string | null;
  is_all_day?: boolean;
  title: string;
  description?: string;
  location?: string;
  audience_tag?: string;
  notes?: string;
  is_kids_friendly?: boolean;
  is_adult_friendly?: boolean;
  review_count?: number;
  average_rating?: number | null;
  attended_count?: number;
  reaction_counts?: { going: number; love: number; helpful: number };
};

type CalendarResponse = { month: string; events: CalendarEvent[]; count: number };
type CalendarBoardProps = { apiUrl: string; mode: "week" | "month"; initialMonth?: string; eventsOnly?: CalendarEvent[]; heading?: string };

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const DEFAULT_CALENDAR_AREA = "Georgetown, TX";

function monthTitle(month: string) {
  return new Intl.DateTimeFormat(undefined, { month: "long", year: "numeric", timeZone: "UTC" }).format(new Date(`${month}-01T00:00:00Z`));
}

function toDate(value: string) {
  return new Date(`${value.slice(0, 10)}T00:00:00Z`);
}

function dateKey(value: Date) {
  return value.toISOString().slice(0, 10);
}

function displayTime(event: CalendarEvent) {
  if (event.is_all_day || !event.start_time_utc) return "All day";
  return new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" }).format(new Date(event.start_time_utc));
}

function googleDate(value: Date) {
  return value.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "Z");
}

function icsText(value: string) {
  return value.replace(/\\/g, "\\\\").replace(/;/g, "\\;").replace(/,/g, "\\,").replace(/\r?\n/g, "\\n");
}

function icsDate(value: Date) {
  return value.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "Z");
}

function calendarLocation(event: CalendarEvent) {
  const location = event.location?.trim();
  if (!location) return DEFAULT_CALENDAR_AREA;
  if (/georgetown|texas|\btx\b/i.test(location)) return location;
  return `${location}, ${DEFAULT_CALENDAR_AREA}`;
}

export function appleCalendarIcs(event: CalendarEvent) {
  const eventDay = toDate(event.event_date);
  const nextDay = new Date(eventDay);
  nextDay.setUTCDate(nextDay.getUTCDate() + 1);
  const uid = `${event.id ?? `${event.event_date}-${event.title}`}@wolf-ranch-calendar`;
  const lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Wolf Ranch Community Calendar//EN", "BEGIN:VEVENT", `UID:${icsText(uid)}`, `DTSTAMP:${icsDate(new Date())}`, `SUMMARY:${icsText(event.title)}`, `DESCRIPTION:${icsText(event.description ?? "")}`, `LOCATION:${icsText(calendarLocation(event))}`];
  if (event.is_all_day || !event.start_time_utc) {
    lines.push(`DTSTART;VALUE=DATE:${dateKey(eventDay).replaceAll("-", "")}`);
    lines.push(`DTEND;VALUE=DATE:${dateKey(nextDay).replaceAll("-", "")}`);
  } else {
    const start = new Date(event.start_time_utc);
    const end = event.end_time_utc ? new Date(event.end_time_utc) : new Date(start.getTime() + 60 * 60 * 1000);
    lines.push(`DTSTART:${icsDate(start)}`, `DTEND:${icsDate(end)}`);
  }
  return `${lines.concat("END:VEVENT", "END:VCALENDAR", "").join("\r\n")}`;
}

function downloadAppleCalendarEvent(event: CalendarEvent) {
  const blob = new Blob([appleCalendarIcs(event)], { type: "text/calendar;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${event.title.replace(/[^a-z0-9]+/gi, "-").replace(/^-|-$/g, "") || "event"}.ics`;
  link.rel = "noopener";
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function googleCalendarUrl(event: CalendarEvent) {
  const eventDay = toDate(event.event_date);
  const nextDay = new Date(eventDay);
  nextDay.setUTCDate(nextDay.getUTCDate() + 1);
  let dates: string;
  if (event.is_all_day || !event.start_time_utc) {
    dates = `${dateKey(eventDay).replaceAll("-", "")}/${dateKey(nextDay).replaceAll("-", "")}`;
  } else {
    const start = new Date(event.start_time_utc);
    const end = event.end_time_utc ? new Date(event.end_time_utc) : new Date(start.getTime() + 60 * 60 * 1000);
    dates = `${googleDate(start)}/${googleDate(end)}`;
  }
  const params = new URLSearchParams({
    action: "TEMPLATE",
    text: event.title,
    dates,
    details: event.description ?? "",
    location: calendarLocation(event),
  });
  return `https://calendar.google.com/calendar/render?${params.toString()}`;
}

function monthShift(month: string, amount: number) {
  const date = new Date(`${month}-01T00:00:00Z`);
  date.setUTCMonth(date.getUTCMonth() + amount);
  return date.toISOString().slice(0, 7);
}

function getInitialWeekStart() {
  const current = new Date();
  const weekStart = new Date(current);
  weekStart.setUTCDate(current.getUTCDate() - current.getUTCDay());
  weekStart.setUTCHours(0, 0, 0, 0);
  return weekStart;
}

function weekShift(start: Date, weeks: number) {
  const shifted = new Date(start);
  shifted.setUTCDate(shifted.getUTCDate() + weeks * 7);
  return shifted;
}

function weekTitle(start: Date) {
  const end = new Date(start);
  end.setUTCDate(start.getUTCDate() + 6);
  const startFormat = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", timeZone: "UTC" }).format(start);
  const endFormat = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" }).format(end);
  return `Week of ${startFormat} – ${endFormat}`;
}

function buildDays(month: string, mode: CalendarBoardProps["mode"], weekStart: Date) {
  if (mode === "week") {
    return Array.from({ length: 7 }, (_, index) => {
      const day = new Date(weekStart);
      day.setUTCDate(weekStart.getUTCDate() + index);
      return day;
    });
  }
  const first = new Date(`${month}-01T00:00:00Z`);
  const start = new Date(first);
  start.setUTCDate(1 - first.getUTCDay());
  const last = new Date(`${month}-01T00:00:00Z`);
  last.setUTCMonth(last.getUTCMonth() + 1, 0);
  const total = Math.ceil((last.getUTCDate() + first.getUTCDay()) / 7) * 7;
  return Array.from({ length: total }, (_, index) => {
    const day = new Date(start);
    day.setUTCDate(start.getUTCDate() + index);
    return day;
  });
}

export function CalendarBoard({ apiUrl, mode, initialMonth, eventsOnly, heading }: CalendarBoardProps) {
  const currentMonth = new Date().toISOString().slice(0, 7);
  const todayKey = dateKey(new Date());
  const [month, setMonth] = useState(initialMonth ?? currentMonth);
  const [weekStart, setWeekStart] = useState<Date>(getInitialWeekStart);
  const [calendar, setCalendar] = useState<CalendarResponse | null>(eventsOnly ? { month: initialMonth ?? currentMonth, events: eventsOnly, count: eventsOnly.length } : null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailEvent, setDetailEvent] = useState<CalendarEvent | null>(null);
  const [selectedLocation, setSelectedLocation] = useState("all");
  const [selectedAudience, setSelectedAudience] = useState<"all" | "kids" | "adults" | "all_ages">("all");
  const [selectedDayShelf, setSelectedDayShelf] = useState<DayShelfData | null>(null);
  const [highlightToday, setHighlightToday] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);

  const shelfTouchStartRef = useRef<number | null>(null);
  const shelfTouchDeltaRef = useRef<number>(0);

  const openDayShelf = (date: Date, dateStr: string, events: CalendarEvent[]) => {
    if (typeof window !== "undefined" && window.innerWidth <= 780) {
      window.history.pushState({
        calendarFullscreen: isFullscreen,
        dayShelf: true,
      }, "");
      setSelectedDayShelf({ date, dateStr, events });
    }
  };

  const closeDayShelf = () => {
    if (typeof window !== "undefined" && window.history.state?.dayShelf) {
      window.history.back();
    } else {
      setSelectedDayShelf(null);
    }
  };

  const openDetailEvent = (event: CalendarEvent) => {
    if (typeof window !== "undefined" && window.innerWidth <= 780) {
      window.history.pushState({
        calendarFullscreen: isFullscreen,
        dayShelf: Boolean(selectedDayShelf),
        detailModal: true,
      }, "");
    }
    setDetailEvent(event);
  };

  const closeDetailEvent = () => {
    if (typeof window !== "undefined" && window.history.state?.detailModal) {
      window.history.back();
    } else {
      setDetailEvent(null);
    }
  };

  function handleShelfTouchStart(e: React.TouchEvent) {
    shelfTouchStartRef.current = e.touches[0].clientY;
    shelfTouchDeltaRef.current = 0;
  }

  function handleShelfTouchMove(e: React.TouchEvent) {
    if (shelfTouchStartRef.current === null) return;
    shelfTouchDeltaRef.current = e.touches[0].clientY - shelfTouchStartRef.current;
  }

  function handleShelfTouchEnd() {
    if (shelfTouchStartRef.current !== null && shelfTouchDeltaRef.current > 60) {
      closeDayShelf();
    }
    shelfTouchStartRef.current = null;
    shelfTouchDeltaRef.current = 0;
  }

  function handleMonthShift(delta: number) {
    triggerSlideAnimation(delta > 0 ? "slide-left" : "slide-right");
    setMonth((prev) => monthShift(prev, delta));
  }

  function handleWeekShift(delta: number) {
    triggerSlideAnimation(delta > 0 ? "slide-left" : "slide-right");
    const next = weekShift(weekStart, delta);
    setWeekStart(next);
    const nextMonth = next.toISOString().slice(0, 7);
    if (nextMonth !== month) {
      setMonth(nextMonth);
    }
  }

  const { slideAnimation, triggerSlideAnimation, touchHandlers } = useCalendarSwipe({
    mode,
    disabled: Boolean(selectedDayShelf || detailEvent),
    onNavigate: (delta) => {
      if (mode === "week") {
        handleWeekShift(delta);
      } else {
        handleMonthShift(delta);
      }
    },
  });

  function handleWeekReset() {
    const current = getInitialWeekStart();
    const diff = current.getTime() - weekStart.getTime();
    if (diff !== 0) {
      triggerSlideAnimation(diff > 0 ? "slide-left" : "slide-right");
    }
    setWeekStart(current);
    const currentM = current.toISOString().slice(0, 7);
    if (currentM !== month) {
      setMonth(currentM);
    }
  }

  function handleMonthToday() {
    if (month !== currentMonth) {
      triggerSlideAnimation(month < currentMonth ? "slide-left" : "slide-right");
      setMonth(currentMonth);
    }
    setHighlightToday(true);
  }

  useEffect(() => {
    if (!highlightToday) return;
    const timer = setTimeout(() => setHighlightToday(false), 2600);
    return () => clearTimeout(timer);
  }, [highlightToday]);

  async function loadCalendar(requestedMonth: string) {
    if (eventsOnly) {
      setCalendar({ month: requestedMonth, events: eventsOnly, count: eventsOnly.length });
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${apiUrl}/api/v1/calendar/current-month?month=${requestedMonth}`);
      if (!response.ok) throw new Error("Calendar could not be loaded.");
      setCalendar(await response.json());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Calendar could not be loaded.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (eventsOnly) {
      setCalendar({ month, events: eventsOnly, count: eventsOnly.length });
      setLoading(false);
      return;
    }
    void loadCalendar(month);
  }, [apiUrl, month, eventsOnly]);

  function matchesAudience(event: CalendarEvent, filter: "all" | "kids" | "adults" | "all_ages"): boolean {
    if (filter === "all") return true;
    if (filter === "kids") {
      return Boolean(event.is_kids_friendly || event.audience_tag === "kids_friendly" || event.audience_tag === "all_ages");
    }
    if (filter === "adults") {
      return Boolean(event.is_adult_friendly || event.audience_tag === "adult_friendly");
    }
    if (filter === "all_ages") {
      return event.audience_tag === "all_ages";
    }
    return true;
  }

  const eventsByDay = useMemo(() => {
    const grouped = new Map<string, CalendarEvent[]>();
    const visibleEvents = (calendar?.events ?? []).filter((event) => {
      const matchesLoc = selectedLocation === "all" || event.location === selectedLocation;
      const matchesAud = matchesAudience(event, selectedAudience);
      return matchesLoc && matchesAud;
    });
    for (const event of visibleEvents) grouped.set(event.event_date.slice(0, 10), [...(grouped.get(event.event_date.slice(0, 10)) ?? []), event]);
    return grouped;
  }, [calendar, selectedLocation, selectedAudience]);

  const locations = useMemo(() => {
    const sourceEvents = eventsOnly ?? calendar?.events ?? [];
    return Array.from(new Set(sourceEvents.map((event) => event.location?.trim()).filter((location): location is string => Boolean(location)))).sort((left, right) => left.localeCompare(right));
  }, [calendar, eventsOnly]);

  useEffect(() => {
    if (selectedLocation !== "all" && !locations.includes(selectedLocation)) setSelectedLocation("all");
  }, [locations, selectedLocation]);

  const days = useMemo(() => buildDays(month, mode, weekStart), [month, mode, weekStart]);
  const numWeeks = useMemo(() => Math.max(1, Math.ceil(days.length / 7)), [days]);
  const displayedEvents = mode === "week" ? days.flatMap((day) => eventsByDay.get(dateKey(day)) ?? []) : calendar?.events ?? [];

  const toggleFullscreen = () => {
    setIsFullscreen((prev) => {
      const next = !prev;
      if (next) {
        window.history.pushState({ calendarFullscreen: true }, "");
      } else if (window.history.state?.calendarFullscreen) {
        window.history.back();
      }
      return next;
    });
  };

  const exitFullscreen = () => {
    if (isFullscreen) {
      if (window.history.state?.calendarFullscreen) {
        window.history.back();
      } else {
        setIsFullscreen(false);
      }
    }
  };

  // Unified popstate and Escape key listener handling the full navigation stack
  useEffect(() => {
    const handlePopState = () => {
      const state = window.history.state;

      // 1. If detail modal is open but state no longer has detailModal, close detail modal
      if (detailEvent && !state?.detailModal) {
        setDetailEvent(null);
        return;
      }

      // 2. If day shelf is open but state no longer has dayShelf, close day shelf
      if (selectedDayShelf && !state?.dayShelf) {
        setSelectedDayShelf(null);
        return;
      }

      // 3. If in fullscreen but state no longer has calendarFullscreen, exit fullscreen
      if (isFullscreen && !state?.calendarFullscreen) {
        setIsFullscreen(false);
        return;
      }
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        if (detailEvent) {
          closeDetailEvent();
        } else if (selectedDayShelf) {
          closeDayShelf();
        } else if (isFullscreen) {
          exitFullscreen();
        }
      }
    };

    window.addEventListener("popstate", handlePopState);
    window.addEventListener("keydown", handleKeyDown);

    return () => {
      window.removeEventListener("popstate", handlePopState);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [detailEvent, selectedDayShelf, isFullscreen]);

  // Lock body scroll while in full screen mode
  useEffect(() => {
    if (!isFullscreen) return;
    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = originalOverflow;
    };
  }, [isFullscreen]);

  return (
    <section
      className={`calendar-panel panel ${isFullscreen ? "is-fullscreen" : ""}`}
      style={isFullscreen && mode === "month" ? ({ "--grid-rows": numWeeks } as React.CSSProperties) : undefined}
      aria-labelledby={`${mode}-calendar-title`}
    >
      <div className="calendar-heading">
        <div className="calendar-heading-main">
          <div className="eyebrow">{heading ?? "Community rhythm"}</div>
          <div className="title-with-count">
            <h2 id={`${mode}-calendar-title`}>{monthTitle(calendar?.month ?? month)}</h2>
            {isFullscreen && (
              <span className="calendar-subtitle-inline">({calendar?.count ?? 0} events)</span>
            )}
          </div>
          {!isFullscreen && (
            <p className="calendar-subtitle">{mode === "week" ? weekTitle(weekStart) : `${calendar?.count ?? 0} events across the month`}</p>
          )}
        </div>
        <div className="calendar-header-actions">
          {mode === "month" && isFullscreen && (
            <div className="calendar-controls fs-controls">
              <button className="icon-button" title="Previous month" aria-label="Previous month" onClick={() => handleMonthShift(-1)}><ChevronLeft size={14} aria-hidden="true" /></button>
              <button className="today-button" onClick={handleMonthToday}>Today</button>
              <button className="icon-button" title="Next month" aria-label="Next month" onClick={() => handleMonthShift(1)}><ChevronRight size={14} aria-hidden="true" /></button>
            </div>
          )}
          {isFullscreen && (
            <div className="audience-filter-pills fs-audience-pills" role="radiogroup" aria-label="Filter events by audience">
              <button
                type="button"
                role="radio"
                aria-checked={selectedAudience === "all"}
                className={`audience-pill ${selectedAudience === "all" ? "is-active" : ""}`}
                onClick={() => setSelectedAudience("all")}
              >
                All
              </button>
              <button
                type="button"
                role="radio"
                aria-checked={selectedAudience === "kids"}
                className={`audience-pill ${selectedAudience === "kids" ? "is-active" : ""}`}
                onClick={() => setSelectedAudience("kids")}
              >
                🧒 Kids
              </button>
              <button
                type="button"
                role="radio"
                aria-checked={selectedAudience === "adults"}
                className={`audience-pill ${selectedAudience === "adults" ? "is-active" : ""}`}
                onClick={() => setSelectedAudience("adults")}
              >
                🍸 Adults
              </button>
              <button
                type="button"
                role="radio"
                aria-checked={selectedAudience === "all_ages"}
                className={`audience-pill ${selectedAudience === "all_ages" ? "is-active" : ""}`}
                onClick={() => setSelectedAudience("all_ages")}
              >
                👨‍👩‍👧 All Ages
              </button>
            </div>
          )}
          {locations.length > 0 && isFullscreen && (
            <div className="location-filter fs-location-filter">
              <label htmlFor={`${mode}-location-filter-fs`}>Location</label>
              <select id={`${mode}-location-filter-fs`} value={selectedLocation} onChange={(event) => setSelectedLocation(event.target.value)}>
                <option value="all">All locations</option>
                {locations.map((location) => <option value={location} key={location}>{location}</option>)}
              </select>
            </div>
          )}
          {isFullscreen && (selectedLocation !== "all" || selectedAudience !== "all") && (
            <button
              type="button"
              className="reset-filters-btn fs-reset-btn"
              onClick={() => {
                setSelectedLocation("all");
                setSelectedAudience("all");
              }}
              title="Reset all filters"
              aria-label="Reset all filters"
            >
              <RotateCcw size={11} aria-hidden="true" /> <span>Reset</span>
            </button>
          )}
          {mode === "month" && (
            <button
              className={isFullscreen ? "fullscreen-exit-button" : "fullscreen-toggle-button"}
              type="button"
              onClick={isFullscreen ? exitFullscreen : toggleFullscreen}
              title={isFullscreen ? "Exit full screen (Esc)" : "Expand to full screen (100% viewport)"}
              aria-label={isFullscreen ? "Exit full screen" : "Expand to full screen"}
            >
              {isFullscreen ? (
                <>
                  <Minimize2 size={13} aria-hidden="true" />
                  <span>Exit</span>
                  <kbd className="esc-key-badge">Esc</kbd>
                </>
              ) : (
                <>
                  <Maximize2 size={15} aria-hidden="true" />
                  <span>Full Screen</span>
                </>
              )}
            </button>
          )}
        </div>
      </div>
      {mode === "month" && !isFullscreen && (
        <div className="calendar-controls">
          <button className="icon-button" title="Previous month" aria-label="Previous month" onClick={() => handleMonthShift(-1)}><ChevronLeft size={17} aria-hidden="true" /></button>
          <button className="today-button" onClick={handleMonthToday}>Today</button>
          <button className="icon-button" title="Next month" aria-label="Next month" onClick={() => handleMonthShift(1)}><ChevronRight size={17} aria-hidden="true" /></button>
        </div>
      )}
      {mode === "week" && (
        <div className="calendar-controls">
          <button className="icon-button" title="Previous week" aria-label="Previous week" onClick={() => handleWeekShift(-1)}><ChevronLeft size={17} aria-hidden="true" /></button>
          <button className="today-button" onClick={handleWeekReset}>This week</button>
          <button className="icon-button" title="Next week" aria-label="Next week" onClick={() => handleWeekShift(1)}><ChevronRight size={17} aria-hidden="true" /></button>
        </div>
      )}
      {!isFullscreen && (
        <div className="calendar-filter-toolbar">
          <div className="audience-filter-pills" role="radiogroup" aria-label="Filter events by audience">
            <button
              type="button"
              role="radio"
              aria-checked={selectedAudience === "all"}
              className={`audience-pill ${selectedAudience === "all" ? "is-active" : ""}`}
              onClick={() => setSelectedAudience("all")}
            >
              All Events
            </button>
            <button
              type="button"
              role="radio"
              aria-checked={selectedAudience === "kids"}
              className={`audience-pill ${selectedAudience === "kids" ? "is-active" : ""}`}
              onClick={() => setSelectedAudience("kids")}
            >
              🧒 Kids Friendly
            </button>
            <button
              type="button"
              role="radio"
              aria-checked={selectedAudience === "adults"}
              className={`audience-pill ${selectedAudience === "adults" ? "is-active" : ""}`}
              onClick={() => setSelectedAudience("adults")}
            >
              🍸 Adults Only
            </button>
            <button
              type="button"
              role="radio"
              aria-checked={selectedAudience === "all_ages"}
              className={`audience-pill ${selectedAudience === "all_ages" ? "is-active" : ""}`}
              onClick={() => setSelectedAudience("all_ages")}
            >
              👨‍👩‍👧 All Ages
            </button>
          </div>

          <div className="filter-dropdown-group">
            {locations.length > 0 && (
              <div className="location-filter">
                <label htmlFor={`${mode}-location-filter`}>Location</label>
                <select id={`${mode}-location-filter`} value={selectedLocation} onChange={(event) => setSelectedLocation(event.target.value)}>
                  <option value="all">All locations</option>
                  {locations.map((location) => <option value={location} key={location}>{location}</option>)}
                </select>
              </div>
            )}
            {(selectedLocation !== "all" || selectedAudience !== "all") && (
              <button
                type="button"
                className="reset-filters-btn"
                onClick={() => {
                  setSelectedLocation("all");
                  setSelectedAudience("all");
                }}
                title="Reset all filters"
                aria-label="Reset all filters"
              >
                <RotateCcw size={12} aria-hidden="true" /> <span>Reset</span>
              </button>
            )}
          </div>
        </div>
      )}
      {error && <p className="calendar-error">{error}</p>}
      {loading && !calendar && <p className="small">Loading events...</p>}
      {calendar && <div
        className={`calendar-board ${mode === "week" ? "week-board" : "month-board"} ${slideAnimation ?? ""}`}
        {...touchHandlers}
      >
        {WEEKDAYS.map((day) => <div className="weekday" key={day}>{day}</div>)}
        {days.map((day) => {
          const date = dateKey(day);
          const dayEvents = eventsByDay.get(date) ?? [];
          const inMonth = date.startsWith(month);
          const isToday = date === todayKey;
          const isPulsing = isToday && highlightToday && mode === "month";
          const dayLabel = `${new Intl.DateTimeFormat(undefined, { weekday: "long", month: "short", day: "numeric", timeZone: "UTC" }).format(day)}, ${dayEvents.length} event${dayEvents.length === 1 ? "" : "s"}`;
          return <div
            className={`calendar-day${inMonth ? "" : " outside"}${isToday ? " is-today" : ""}${isPulsing ? " is-today-highlight" : ""}`}
            key={date}
            role="button"
            tabIndex={0}
            aria-label={dayLabel}
            onClick={() => openDayShelf(day, date, dayEvents)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                openDayShelf(day, date, dayEvents);
              }
            }}
          >
            <div className="day-header">
              <time dateTime={date}>{day.getUTCDate()}</time>
              <span className="day-weekday">{WEEKDAYS[day.getUTCDay()]}</span>
            </div>
            <div className="day-events">{dayEvents.map((event, index) => {
              const eventKey = event.id ?? `${date}-${event.title}-${index}`;
              const isOverflowMobile = index >= 2;
              return <div className={`event-chip ${isFullscreen ? "event-chip-fullscreen" : ""} ${isOverflowMobile ? "chip-overflow-mobile" : ""}`} key={eventKey}>
                <button
                  className="event-summary"
                  type="button"
                  aria-label={`${event.title}, ${displayTime(event)}${event.location ? `, at ${event.location}` : ""}`}
                  onClick={(clickEvent) => {
                    if (typeof window !== "undefined" && window.innerWidth <= 780) {
                      clickEvent.stopPropagation();
                      openDayShelf(day, date, dayEvents);
                    } else {
                      setDetailEvent(event);
                    }
                  }}
                >
                  <div className="event-chip-header">
                    <span className="event-time">{displayTime(event)}</span>
                  </div>
                  <strong className={isFullscreen ? "event-title-full" : ""}>{event.title}</strong>
                  {event.location && <span className="event-location"><MapPin size={11} aria-hidden="true" />{event.location}</span>}
                </button>
                <div className="event-actions">
                  {!isFullscreen && <span className="event-time">{displayTime(event)}</span>}
                  <button
                    className="event-add"
                    type="button"
                    aria-label={`Open details for ${event.title}`}
                    onClick={(clickEvent) => {
                      clickEvent.stopPropagation();
                      if (typeof window !== "undefined" && window.innerWidth <= 780) {
                        openDayShelf(day, date, dayEvents);
                      } else {
                        setDetailEvent(event);
                      }
                    }}
                  >
                    Open details
                  </button>
                </div>
              </div>;
            })}
            {dayEvents.length > 2 && (
              <div
                className="more-events-badge"
                role="button"
                tabIndex={0}
                aria-label={`View ${dayEvents.length - 2} more events for ${date}`}
                onClick={(e) => {
                  e.stopPropagation();
                  openDayShelf(day, date, dayEvents);
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    e.stopPropagation();
                    openDayShelf(day, date, dayEvents);
                  }
                }}
              >
                +{dayEvents.length - 2} more
              </div>
            )}
            </div>
          </div>;
        })}
      </div>}
      {mode === "week" && calendar && displayedEvents.length === 0 && <p className="empty-state">No events scheduled this week.</p>}

      {/* Mobile Day Shelf (Bottom Drawer) */}
      {selectedDayShelf && (
        <div
          className="mobile-day-shelf-backdrop"
          role="presentation"
          onClick={(e) => {
            if (e.target === e.currentTarget) closeDayShelf();
          }}
        >
          <section
            className="mobile-day-shelf"
            role="dialog"
            aria-modal="true"
            aria-label={`Events for ${selectedDayShelf.dateStr}`}
            onTouchStart={handleShelfTouchStart}
            onTouchMove={handleShelfTouchMove}
            onTouchEnd={handleShelfTouchEnd}
          >
            <div className="shelf-drag-handle" aria-hidden="true" />
            <div className="shelf-header">
              <div className="shelf-title-group">
                <span className="shelf-eyebrow">
                  {new Intl.DateTimeFormat(undefined, {
                    weekday: "long",
                    month: "short",
                    day: "numeric",
                    year: "numeric",
                    timeZone: "UTC",
                  }).format(selectedDayShelf.date)}
                </span>
                <h3 className="shelf-title">
                  {selectedDayShelf.events.length}{" "}
                  {selectedDayShelf.events.length === 1 ? "Event" : "Events"}
                </h3>
              </div>
              <button
                className="dialog-close"
                type="button"
                aria-label="Close day shelf"
                onClick={closeDayShelf}
              >
                ×
              </button>
            </div>

            <div className="shelf-content">
              {selectedDayShelf.events.length === 0 ? (
                <p className="empty-reviews-state">No events scheduled for this day.</p>
              ) : (
                <div className="shelf-event-list">
                  {selectedDayShelf.events.map((event, idx) => (
                    <button
                      key={event.id ?? `${event.title}-${idx}`}
                      type="button"
                      className="shelf-event-card"
                      onClick={() => openDetailEvent(event)}
                    >
                      <div className="shelf-card-top">
                        <span className="shelf-event-time">{displayTime(event)}</span>
                        <div className="shelf-card-badges">
                          {(event.is_kids_friendly || event.audience_tag === "kids_friendly") && (
                            <span className="card-badge badge-kids">🧒 Kids</span>
                          )}
                          {(event.is_adult_friendly || event.audience_tag === "adult_friendly") && (
                            <span className="card-badge badge-adults">🍸 Adults</span>
                          )}
                          {(!event.is_kids_friendly && !event.is_adult_friendly && event.audience_tag === "all_ages") && (
                            <span className="card-badge badge-all-ages">👨‍👩‍👧 All Ages</span>
                          )}
                        </div>
                      </div>

                      <div className="shelf-card-title">{event.title}</div>

                      {event.location && (
                        <div className="shelf-card-location">
                          <MapPin size={12} />
                          <span>{event.location}</span>
                        </div>
                      )}

                      {/* Reaction / Review counts */}
                      {((event.reaction_counts?.going ?? 0) > 0 ||
                        (event.reaction_counts?.love ?? 0) > 0 ||
                        (event.reaction_counts?.helpful ?? 0) > 0 ||
                        (event.review_count ?? 0) > 0) && (
                        <div className="chip-reactions-summary">
                          {(event.reaction_counts?.going ?? 0) > 0 && (
                            <span className="chip-rx-pill" title={`${event.reaction_counts?.going} planning to go`}>
                              🗓️ {event.reaction_counts?.going}
                            </span>
                          )}
                          {(event.reaction_counts?.love ?? 0) > 0 && (
                            <span className="chip-rx-pill" title={`${event.reaction_counts?.love} love this`}>
                              ❤️ {event.reaction_counts?.love}
                            </span>
                          )}
                          {(event.reaction_counts?.helpful ?? 0) > 0 && (
                            <span className="chip-rx-pill" title={`${event.reaction_counts?.helpful} helpful`}>
                              💡 {event.reaction_counts?.helpful}
                            </span>
                          )}
                          {(event.review_count ?? 0) > 0 && (
                            <span className="chip-rx-pill chip-rx-star" title={`${event.review_count} reviews`}>
                              ⭐ {formatRating(event.average_rating)} ({event.review_count})
                            </span>
                          )}
                        </div>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </section>
        </div>
      )}

      {detailEvent && <div className="mobile-event-backdrop" role="presentation" onMouseDown={(mouseEvent) => { if (mouseEvent.target === mouseEvent.currentTarget) closeDetailEvent(); }}>
        <section className="mobile-event-dialog" role="dialog" aria-modal="true" aria-labelledby="mobile-event-title">
          <button className="dialog-close" type="button" aria-label="Close event details" onClick={closeDetailEvent}>×</button>
          <div className="eyebrow">Event details</div>
          <h3 id="mobile-event-title">{detailEvent.title}</h3>
          <dl className="event-detail-list">
            <div><dt>Date</dt><dd>{detailEvent.event_date.slice(0, 10)}</dd></div>
            <div><dt>Time</dt><dd>{displayTime(detailEvent)}</dd></div>
            {detailEvent.location && <div><dt>Location</dt><dd>{detailEvent.location}</dd></div>}
            {detailEvent.audience_tag && <div><dt>Audience</dt><dd>{detailEvent.audience_tag.replaceAll("_", " ")}</dd></div>}
            {detailEvent.notes && <div><dt>Notes</dt><dd>{detailEvent.notes}</dd></div>}
            {detailEvent.description && <div><dt>Description</dt><dd>{detailEvent.description}</dd></div>}
          </dl>
          <div className="mobile-event-actions">
            <a className="primary" href={googleCalendarUrl(detailEvent)} target="_blank" rel="noopener noreferrer" aria-label={`Add ${detailEvent.title} to Google Calendar`}>Google Calendar</a>
            <button className="text-button" type="button" aria-label={`Export ${detailEvent.title} to Apple Calendar (.ics)`} onClick={() => downloadAppleCalendarEvent(detailEvent)}>Apple Calendar</button>
          </div>
          <hr className="modal-section-divider" />
          <EventReviews
            event={detailEvent}
            apiUrl={apiUrl}
            onInteractionsUpdated={(eventId, counts, avgRating, revCount) => {
              setCalendar((prev) => {
                if (!prev) return prev;
                return {
                  ...prev,
                  events: prev.events.map((e) =>
                    e.id === eventId
                      ? {
                          ...e,
                          reaction_counts: counts,
                          average_rating: avgRating,
                          review_count: revCount,
                        }
                      : e
                  ),
                };
              });
              setDetailEvent((prev) =>
                prev && prev.id === eventId
                  ? {
                      ...prev,
                      reaction_counts: counts,
                      average_rating: avgRating,
                      review_count: revCount,
                    }
                  : prev
              );
              setSelectedDayShelf((prev) => {
                if (!prev) return prev;
                return {
                  ...prev,
                  events: prev.events.map((e) =>
                    e.id === eventId
                      ? {
                          ...e,
                          reaction_counts: counts,
                          average_rating: avgRating,
                          review_count: revCount,
                        }
                      : e
                  ),
                };
              });
            }}
          />
        </section>
      </div>}
    </section>
  );
}
