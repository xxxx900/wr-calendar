import type { Metadata } from "next";
import { AuthProvider } from "./context/AuthContext";
// CSS is processed by Next.js and does not need a TypeScript module declaration.
// @ts-ignore -- Next.js resolves this side-effect stylesheet import at build time.
import "./globals.css";
import { themeInitScript } from "./lib/theme";

export const metadata: Metadata = {
  title: "Wolf Ranch Calendar",
  description: "Community events and calendar assistant",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body>
        <a href="#main-content" className="skip-link">
          Skip to main content
        </a>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
