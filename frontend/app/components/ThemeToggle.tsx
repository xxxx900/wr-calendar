"use client";

import { useEffect, useSyncExternalStore } from "react";
import { Moon, Sun } from "lucide-react";
import {
  THEME_KEY,
  applyTheme,
  readStoredTheme,
  resolveTheme,
  storeTheme,
  systemTheme,
  watchSystemTheme,
  type Theme,
} from "../lib/theme";

function subscribe(onChange: () => void) {
  const observer = new MutationObserver(onChange);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  return () => observer.disconnect();
}

function getTheme(): Theme | null {
  const value = document.documentElement.dataset.theme;
  return value === "light" || value === "dark" ? value : null;
}

export function ThemeToggle() {
  // The server cannot know the theme, so null renders a stable placeholder until hydration.
  const theme = useSyncExternalStore(subscribe, getTheme, () => null);

  useEffect(() => {
    const followSystem = () => {
      if (!readStoredTheme()) applyTheme(systemTheme());
    };
    const onStorage = (event: StorageEvent) => {
      if (event.key === null || event.key === THEME_KEY) applyTheme(resolveTheme());
    };
    window.addEventListener("storage", onStorage);
    const stopWatching = watchSystemTheme(followSystem);
    return () => {
      window.removeEventListener("storage", onStorage);
      stopWatching();
    };
  }, []);

  if (!theme) {
    return <button className="nav-link theme-toggle" type="button" disabled aria-label="Switch theme" />;
  }

  const next: Theme = theme === "dark" ? "light" : "dark";
  const Icon = theme === "dark" ? Moon : Sun;

  return (
    <button
      className="nav-link theme-toggle"
      type="button"
      aria-label={`Switch to ${next} theme`}
      onClick={() => {
        applyTheme(next);
        storeTheme(next);
      }}
    >
      <Icon size={16} aria-hidden="true" />
      <span>{theme === "dark" ? "Dark" : "Light"}</span>
    </button>
  );
}
