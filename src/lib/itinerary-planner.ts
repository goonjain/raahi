/**
 * Deterministic Jaipur planning baseline. Only geographic proximity is used;
 * this is not road routing, verified hours, or live venue availability.
 */
import { PLACES, type Place } from "@/lib/jaipur-data";
import { haversine } from "@/lib/distance";
import { predictCrowd } from "@/lib/crowd-service";
import type { ItineraryRequest } from "./itinerary-request";

const PLACE_BY_ID = new Map(PLACES.map((p) => [p.id, p]));

/** Date-only calendar arithmetic in UTC prevents timezone off-by-one errors. */
export function daysBetween(start: string, end: string): string[] {
  const valid = /^\d{4}-\d{2}-\d{2}$/;
  if (!valid.test(start) || !valid.test(end) || end < start) return [];
  const begin = new Date(`${start}T00:00:00Z`);
  const finish = new Date(`${end}T00:00:00Z`);
  if (Number.isNaN(begin.getTime()) || Number.isNaN(finish.getTime()) ||
      begin.toISOString().slice(0, 10) !== start || finish.toISOString().slice(0, 10) !== end) return [];
  const result: string[] = [];
  for (let ms = begin.getTime(); ms <= finish.getTime() && result.length < 31; ms += 86400000) {
    result.push(new Date(ms).toISOString().slice(0, 10));
  }
  return result;
}

export function sightseeingBounds(req: ItineraryRequest, date: string): { start: number; end: number } {
  const parse = (value?: string): number | undefined => {
    if (!value || !/^\d{2}:\d{2}$/.test(value)) return undefined;
    const [h, m] = value.split(":").map(Number);
    return h >= 0 && h <= 23 && m >= 0 && m <= 59 ? h + m / 60 : undefined;
  };
  const first = date === req.startDate;
  const last = date === req.endDate;
  return {
    start: first ? Math.max(9, parse(req.startTime) ?? 9) : 9,
    end: last ? Math.min(18, parse(req.endTime) ?? 18) : 18,
  };
}

export function visitStepHours(pace: string): number {
  return pace === "relaxed" ? 3 : pace === "intense" || pace === "packed" ? 1.5 : 2;
}

function distanceKm(a: string, b: string): number {
  const first = PLACE_BY_ID.get(a), second = PLACE_BY_ID.get(b);
  return first && second ? haversine(first.lat, first.lng, second.lat, second.lng) : Infinity;
}

function routeDistance(ids: string[]): number {
  return ids.slice(1).reduce((sum, id, i) => sum + distanceKm(ids[i], id), 0);
}

function nearestFromStart(ids: string[], start: string): string[] {
  const remaining = ids.filter((id) => id !== start);
  const ordered = [start];
  while (remaining.length) {
    remaining.sort((a, b) => distanceKm(ordered[ordered.length - 1], a) - distanceKm(ordered[ordered.length - 1], b));
    ordered.push(remaining.shift()!);
  }
  return ordered;
}

/** Compare starts rather than just using the first input stop. */
export function optimizeDayStops(ids: string[]): string[] {
  const distinct = [...new Set(ids)].filter((id) => PLACE_BY_ID.has(id));
  if (distinct.length < 3) return distinct;
  const candidates = distinct.map((start) => nearestFromStart(distinct, start));
  candidates.sort((a, b) => routeDistance(a) - routeDistance(b));
  // Don't claim an improvement or change the displayed order if none exists.
  return routeDistance(candidates[0]) + 0.01 < routeDistance(distinct) ? candidates[0] : distinct;
}

/** Returns a dated array of attraction IDs for every selected day, including empty days. */
export function generateItinerary(req: ItineraryRequest, preferredIds?: string[]): Record<string, string[]> {
  const days = daysBetween(req.startDate, req.endDate);
  if (days.length === 0) throw new Error("Please choose a valid trip date range (up to 31 days).");
  if (days[days.length - 1] !== req.endDate) throw new Error("Trip exceeds the supported 31-day range.");
  const matching = PLACES.filter((p: Place) => p.tags.some((tag) => req.interests.includes(tag)));
  const include = (id: string) => PLACE_BY_ID.has(id) &&
    (req.hiddenGemsPreference !== "no" || !PLACE_BY_ID.get(id)!.gem || req.mustVisit.includes(id));
  const baseCandidates = [...new Set([...req.mustVisit, ...matching.map((p) => p.id)])].filter(include);
  // Merge AI-preferred attraction IDs, preserving order and avoiding duplicates.
  const candidates = (() => {
    if (!preferredIds || preferredIds.length === 0) return baseCandidates;
    // Keep only valid IDs that pass the same inclusion filter.
    const validPref = preferredIds.filter((id) => include(id));
    const prefSet = new Set(validPref);
    // Prepend preferred IDs, then add any remaining base candidates not already included.
    return [...validPref, ...baseCandidates.filter((id) => !prefSet.has(id))];
  })();
  if (!candidates.length) candidates.push(...PLACES.filter((p) => !p.gem).slice(0, 5).map((p) => p.id));
  const plan: Record<string, string[]> = Object.fromEntries(days.map((date) => [date, []]));
  const capacity = Object.fromEntries(days.map((date) => {
    const { start, end } = sightseeingBounds(req, date);
    return [date, Math.max(0, Math.floor((end - start) / visitStepHours(req.travelPace)))];
  })) as Record<string, number>;
  let cursor = 0;
  for (const id of candidates) {
    for (let offset = 0; offset < days.length; offset++) {
      const i = (cursor + offset) % days.length;
      const day = days[i];
      if (plan[day].length >= capacity[day]) continue;
      plan[day].push(id);
      cursor = (i + 1) % days.length;
      break;
    }
  }
  // Re-rank feasible choices within each day for crowd tolerance, without dropping must-visits.
  if (req.crowdTolerance === "avoid") {
    for (const day of days) {
      const weekday = new Intl.DateTimeFormat("en-US", { weekday: "short", timeZone: "UTC" }).format(new Date(`${day}T12:00:00Z`));
      const start = sightseeingBounds(req, day).start;
      plan[day].sort((a, b) => {
        const aMust = req.mustVisit.includes(a), bMust = req.mustVisit.includes(b);
        if (aMust !== bMust) return aMust ? -1 : 1;
        return predictCrowd(a, { day: weekday, hour: Math.floor(start) }).score -
               predictCrowd(b, { day: weekday, hour: Math.floor(start) }).score;
      });
    }
  }
  return plan;
}
