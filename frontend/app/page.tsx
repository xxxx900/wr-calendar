"use client";

import { CalendarBoard } from "./components/CalendarBoard";
import { SiteNav } from "./components/SiteNav";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function HomePage() {
  return (
    <div className="shell">
      <SiteNav />
      <main id="main-content">
        <header className="page-heading">
          <div className="eyebrow">The neighborhood, month by month</div>
          <h1>Month at a glance.</h1>
          <p>Browse every week, then add an event straight to Google Calendar.</p>
        </header>
        <CalendarBoard apiUrl={API_URL} mode="month" />
      </main>
    </div>
  );
}
