"use client";

import { useEffect, useRef, useState } from "react";

export type SlideAnimation = "slide-left" | "slide-right" | null;

export interface UseCalendarSwipeOptions {
  /** Mode of the calendar: "month" or "week" */
  mode: "month" | "week";
  /** Callback to navigate by delta (+1 for next/following, -1 for previous) */
  onNavigate: (delta: number) => void;
  /** Whether swiping should be disabled (e.g. when a modal or shelf is open) */
  disabled?: boolean;
  /** Minimum horizontal pixel distance to register a swipe (default 45px) */
  threshold?: number;
  /** Ratio of horizontal to vertical movement required to prevent diagonal scroll conflicts (default 1.4) */
  directionalRatio?: number;
  /** Animation duration in ms before resetting the slide class (default 320ms) */
  animationDuration?: number;
}

export interface UseCalendarSwipeReturn {
  /** Current slide animation class to apply to the calendar board ("slide-left", "slide-right", or null) */
  slideAnimation: SlideAnimation;
  /** Manually trigger a slide animation if needed (e.g. on navigation button clicks) */
  triggerSlideAnimation: (direction: SlideAnimation) => void;
  /** Touch event handlers to attach to the calendar container element */
  touchHandlers: {
    onTouchStart: (e: React.TouchEvent) => void;
    onTouchMove: (e: React.TouchEvent) => void;
    onTouchEnd: (e: React.TouchEvent) => void;
  };
}

/**
 * Unified touch swipe hook for both monthly and weekly calendar views on mobile.
 *
 * Natural carousel mapping:
 * - Swipe Left (finger drags left, deltaX < 0): advances to Next (following) week/month with "slide-left" animation.
 * - Swipe Right (finger drags right, deltaX > 0): returns to Previous week/month with "slide-right" animation.
 *
 * Automatically guards against diagonal vertical scrolls and honors the disabled prop (e.g. when day shelf or modal is open).
 */
export function useCalendarSwipe({
  mode,
  onNavigate,
  disabled = false,
  threshold = 45,
  directionalRatio = 1.4,
  animationDuration = 320,
}: UseCalendarSwipeOptions): UseCalendarSwipeReturn {
  const [slideAnimation, setSlideAnimation] = useState<SlideAnimation>(null);

  const touchStartRef = useRef<{ x: number; y: number } | null>(null);
  const touchDeltaRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });

  // Clean up slide animation class after the transition finishes
  useEffect(() => {
    if (!slideAnimation) return;
    const timer = setTimeout(() => setSlideAnimation(null), animationDuration);
    return () => clearTimeout(timer);
  }, [slideAnimation, animationDuration]);

  const triggerSlideAnimation = (direction: SlideAnimation) => {
    setSlideAnimation(direction);
  };

  const handleTouchStart = (e: React.TouchEvent) => {
    if (disabled) return;
    const touch = e.touches[0];
    touchStartRef.current = { x: touch.clientX, y: touch.clientY };
    touchDeltaRef.current = { x: 0, y: 0 };
  };

  const handleTouchMove = (e: React.TouchEvent) => {
    if (!touchStartRef.current || disabled) return;
    const touch = e.touches[0];
    touchDeltaRef.current = {
      x: touch.clientX - touchStartRef.current.x,
      y: touch.clientY - touchStartRef.current.y,
    };
  };

  const handleTouchEnd = () => {
    if (!touchStartRef.current || disabled) {
      touchStartRef.current = null;
      touchDeltaRef.current = { x: 0, y: 0 };
      return;
    }

    const { x, y } = touchDeltaRef.current;
    // Require minimum horizontal drag distance AND dominant horizontal travel over vertical
    if (Math.abs(x) > threshold && Math.abs(x) > Math.abs(y) * directionalRatio) {
      if (x < 0) {
        // Swipe Left -> Next (following) week or month
        setSlideAnimation("slide-left");
        onNavigate(1);
      } else {
        // Swipe Right -> Previous week or month
        setSlideAnimation("slide-right");
        onNavigate(-1);
      }
    }

    touchStartRef.current = null;
    touchDeltaRef.current = { x: 0, y: 0 };
  };

  return {
    slideAnimation,
    triggerSlideAnimation,
    touchHandlers: {
      onTouchStart: handleTouchStart,
      onTouchMove: handleTouchMove,
      onTouchEnd: handleTouchEnd,
    },
  };
}
