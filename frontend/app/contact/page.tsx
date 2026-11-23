import type { Metadata } from "next";
import { Mail, MessageSquare } from "lucide-react";
import { SiteNav } from "../components/SiteNav";

export const metadata: Metadata = {
  title: "Contact the Team - Wolf Ranch Calendar",
  description: "Contact the Wolf Ranch community calendar team with event submissions or feedback.",
};

export default function ContactPage() {
  return (
    <div className="shell">
      <SiteNav />
      <main id="main-content">
        <section className="contact-layout">
          <div>
            <div className="eyebrow">A real person is listening</div>
            <h1>Contact the calendar team.</h1>
            <p className="lead">
              Have an event to share, a correction to suggest, or feedback about the experience? Send us a note and we will take a look.
            </p>
          </div>
          <div className="contact-card">
            <Mail size={24} aria-hidden="true" />
            <h2>Send feedback</h2>
            <p>
              Reach us at <a href="mailto:jbk3710+wrcalendar@gmail.com">jbk3710+wrcalendar@gmail.com</a>.
            </p>
            <a
              className="primary contact-link"
              href="mailto:jbk3710+wrcalendar@gmail.com?subject=Wolf%20Ranch%20Calendar%20feedback"
            >
              <MessageSquare size={16} aria-hidden="true" />
              <span>Email the team</span>
            </a>
          </div>
        </section>
      </main>
    </div>
  );
}
