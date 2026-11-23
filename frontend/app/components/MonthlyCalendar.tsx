"use client";

import { useEffect, useMemo, useState } from "react";
import { MapPin } from "lucide-react";

type CalendarEvent = {
  id?: string;
  event_date: string;
  start_time_utc?: string | null;
  end_time_utc?: string | null;
  is_all_day?: boolean;
  title: string;
  description?: string;
  location?: string;
  audience_tag?: string;
};

type CalendarResponse = {
  month: string;
  events: CalendarEvent[];
  count: number;
};

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const DEFAULT_CALENDAR_AREA = "Georgetown, TX";

function monthTitle(month: string) {
  return new Intl.DateTimeFormat(undefined, { month: "long", year: "numeric" }).format(
    new Date(`${month}-01T00:00:00Z`),
  );
}

function eventDate(event: CalendarEvent) {
  return event.event_date.slice(0, 10);
}

function displayTime(event: CalendarEvent) {
  if (event.is_all_day || !event.start_time_utc) return "All day";
  return new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" }).format(
    new Date(event.start_time_utc),
  );
}

function googleDate(value: Date) {
  return value.toISOString().replace(/[-:]/g, "").replace(".000", "");
}

function calendarLocation(event: CalendarEvent) {
  const location = event.location?.trim();
  if (!location) return DEFAULT_CALENDAR_AREA;
  if (/georgetown|texas|\btx\b/i.test(location)) return location;
  return `${location}, ${DEFAULT_CALENDAR_AREA}`;
}

function googleCalendarUrl(event: CalendarEvent) {
  const startDate = new Date(`${eventDate(event)}T00:00:00Z`);
  const endDate = new Date(startDate);
  endDate.setUTCDate(endDate.getUTCDate() + 1);

  const dates = event.is_all_day || !event.start_time_utc
    ? `${startDate.toISOString().slice(0, 10).replaceAll("-", "")}/${endDate.toISOString().slice(0, 10).replaceAll("-", "")}`
    : `${googleDate(new Date(event.start_time_utc))}/${googleDate(new Date(event.end_time_utc ?? event.start_time_utc))}`;

  const params = new URLSearchParams({
    action: "TEMPLATE",
    text: event.title,
    dates,
    details: event.description ?? "",
    location: calendarLocation(event),
  });
  return `https://calendar.google.com/calendar/render?${params.toString()}`;
}

export function MonthlyCalendar({ apiUrl }: { apiUrl: string }) {
  const [calendar, setCalendar] = useState<CalendarResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  async function loadCalendar() {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${apiUrl}/api/v1/calendar/current-month`);
      if (!response.ok) throw new Error("Calendar could not be loaded.");
      setCalendar(await response.json());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Calendar could not be loaded.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadCalendar();
  }, [apiUrl]);

  const eventsByDay = useMemo(() => {
    const grouped = new Map<string, CalendarEvent[]>();
    for (const event of calendar?.events ?? []) {
      const events = grouped.get(eventDate(event)) ?? [];
      events.push(event);
      grouped.set(eventDate(event), events);
    }
    return grouped;
  }, [calendar]);

  const days = useMemo(() => {
    if (!calendar) return [];
    const first = new Date(`${calendar.month}-01T00:00:00Z`);
    const start = new Date(first);
    start.setUTCDate(1 - first.getUTCDay());
    const last = new Date(`${calendar.month}-01T00:00:00Z`);
    last.setUTCMonth(last.getUTCMonth() + 1, 0);
    const total = Math.ceil((start.getTime() - last.getTime()) / -86400000 / 7) * 7;
    return Array.from({ length: total }, (_, index) => {
      const day = new Date(start);
      day.setUTCDate(start.getUTCDate() + index);
      return day;
    });
  }, [calendar]);

  return (
    <section className="calendar-panel panel" aria-labelledby="monthly-calendar-title">
      <div className="calendar-heading">
        <div>
          <div className="eyebrow">Community rhythm</div>
          <h2 id="monthly-calendar-title">{calendar ? monthTitle(calendar.month) : "This month"}</h2>
        </div>
      </div>
      {error && <p className="calendar-error">{error}</p>}
      {loading && !calendar && <p className="small">Loading this month&apos;s events...</p>}
      {calendar && (
        <>
          <div className="calendar-meta"><strong>{calendar.count}</strong> events this month</div>
          <div className="month-grid">
            {WEEKDAYS.map((day) => <div className="weekday" key={day}>{day}</div>)}
            {days.map((day) => {
              const date = day.toISOString().slice(0, 10);
              const dayEvents = eventsByDay.get(date) ?? [];
              const inMonth = date.startsWith(calendar.month);
              return (
                <div className={`calendar-day${inMonth ? "" : " outside"}`} key={date}>
                  <time dateTime={date}>{day.getUTCDate()}</time>
                  <div className="day-events">
                    {dayEvents.map((event, index) => (
                      <a
                        className="event-chip"
                        href={googleCalendarUrl(event)}
                        target="_blank"
                        rel="noreferrer"
                        key={event.id ?? `${date}-${event.title}-${index}`}
                        title="Add to Google Calendar"
                        aria-label={`${event.title}, ${displayTime(event)}${event.location ? `, at ${event.location}` : ""}. Add to Google Calendar`}
                      >
                        <span className="event-time">{displayTime(event)}</span>
                        <strong>{event.title}</strong>
                        {event.location && <span className="event-location"><MapPin size={11} aria-hidden="true" />{event.location}</span>}
                        <span className="event-add">Open details</span>
                      </a>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}
    </section>
  );
}
