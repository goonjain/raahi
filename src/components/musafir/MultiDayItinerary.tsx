// src/components/musafir/MultiDayItinerary.tsx
import type { ItineraryRequest } from "@/lib/itinerary-request";
import { PLACES } from "@/lib/jaipur-data";
import { predictCrowd, type VerifiedObservation } from "@/lib/crowd-service";
import {
  rankAlternatives,
  isReplacementFeasible,
  calculateStraightLineDistanceKm,
  type ScoredRecommendation,
} from "@/lib/recommendation";
import { Badge } from "./Sections";
import { recommendFoodForDay } from "@/lib/food-recommendation";
import { useState } from "react";
import {
  sightseeingBounds,
  visitStepHours,
} from "@/lib/itinerary-planner";

type Props = {
  byDay: Record<string, string[]>;
  request: ItineraryRequest;
  observations: VerifiedObservation[];
  onOptimizeDay: (date: string) => void;
  onReplace: (date: string, hotspotId: string, gemId: string) => void;
  onUndo: (date: string) => void;
  canUndoByDay: Record<string, boolean>;
  feedback: Record<string, string>;
  // Food handling props
  foodSelections: Record<string, string | undefined>;
  onSelectFood: (date: string, restaurantId: string) => void;
  onRemoveFood: (date: string) => void;
  // AI proposals
  aiProposals?: { attraction_ids: string[]; restaurant_ids: string[]; reason: string; evidence_refs: string[] }[];
};

function formatHour(hour: number): string {
  const h = Math.floor(hour);
  const m = Math.round((hour - h) * 60);
  return `${(h % 12) || 12}:${String(m).padStart(2, "0")} ${h < 12 ? "AM" : "PM"}`;
}

export default function MultiDayItinerary({
  byDay,
  request,
  observations,
  onOptimizeDay,
  onReplace,
  onUndo,
  canUndoByDay,
  foodSelections,
  onSelectFood,
  onRemoveFood,
  feedback,
  aiProposals = [],
}: Props) {
  // Build a quick lookup for attraction reasons from AI proposals
  const reasonMap = new Map<string, string>();
  aiProposals.forEach((p) => {
    if (Array.isArray(p.attraction_ids)) {
      p.attraction_ids.forEach((id) => {
        if (!reasonMap.has(id) && p.reason) {
          reasonMap.set(id, p.reason);
        }
      });
    }
  });
  const dates = Object.keys(byDay).sort();
  const [activeHotspot, setActiveHotspot] = useState<string | null>(null);
  const [showFood, setShowFood] = useState<Record<string, boolean>>({});

  return (
    <div className="space-y-7">
      <div className="rounded-2xl border bg-card p-5 shadow">
        <h3 className="font-display text-2xl text-primary">Your Jaipur itinerary</h3>
        <p className="mt-1 text-sm text-muted-foreground">
          {dates.length} calendar day{dates.length === 1 ? "" : "s"} · {request.groupSize} traveller{request.groupSize === 1 ? "" : "s"} ·
          ₹{request.budget.toLocaleString("en-IN")} total group budget
        </p>
        <p className="mt-2 text-xs text-muted-foreground">
          Timings are planning estimates; travel times, venue hours and admission availability are not verified here.
        </p>
      </div>

      {dates.map((date, dayIndex) => {
        const ids = byDay[date] ?? [];
        const { start, end } = sightseeingBounds(request, date);
        const step = visitStepHours(request.travelPace);
        const weekday = new Intl.DateTimeFormat("en-US", { weekday: "short", timeZone: "UTC" }).format(
          new Date(`${date}T12:00:00Z`)
        );
        const formattedDate = new Intl.DateTimeFormat("en-IN", {
          day: "numeric",
          month: "long",
          year: "numeric",
          timeZone: "UTC",
        }).format(new Date(`${date}T12:00:00Z`));

        // Food recommendations for this day
        const foodRecs = recommendFoodForDay(ids, request);

        return (
          <section key={date} className="rounded-2xl border bg-card p-5 shadow md:p-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h4 className="font-display text-xl text-primary">Day {dayIndex + 1} — {formattedDate}</h4>
                <p className="text-xs text-muted-foreground">
                  {weekday} · {formatHour(start)}–{formatHour(end)} suggested sightseeing window
                </p>
              </div>
              {canUndoByDay[date] && (
                <button type="button" onClick={() => onUndo(date)} className="text-sm underline text-primary">
                  Undo last replacement
                </button>
              )}
            </div>

            {feedback[date] && (
              <p className="mt-3 text-sm text-muted-foreground" role="status">
                {feedback[date]}
              </p>
            )}

            {/* Attraction list */}
            {ids.length === 0 ? (
              <p className="mt-5 text-sm text-muted-foreground">
                No attractions fit this day's available time or preferences. This is free time; adjust your dates or preferences to include more stops.
              </p>
            ) : (
              <ol className="mt-5 space-y-4 border-l-2 border-dashed border-primary pl-6">
                {ids.map((id, i) => {
                  const place = PLACES.find(p => p.id === id);
                  if (!place) return null;
                  const hour = start + i * step;
                  const prediction = predictCrowd(id, { day: weekday, hour: Math.floor(hour), observations });
                  const showing = activeHotspot === id;
                  const alternatives: ScoredRecommendation[] = showing
                    ? rankAlternatives(place, PLACES, {
                        userInterests: request.interests,
                        gemsOnly: false,
                        limit: PLACES.length,
                      }).filter(rec => isReplacementFeasible(id, rec.place.id, ids, 5)).slice(0, 3)
                    : [];
                  return (
                    <li key={id} className="relative">
                      <span className="absolute -left-[33px] top-1 block h-4 w-4 rounded-full bg-saffron ring-4 ring-background" />
                      <div className="flex flex-wrap items-center gap-3">
                        <span className="font-display text-primary">{formatHour(hour)}</span>
                        <span className="font-semibold">{place.name}</span>
                        {place.gem && (
                          <span className="rounded-full bg-gem px-2 py-0.5 text-xs text-primary-foreground">Hidden gem</span>
                        )}
                        <Badge score={prediction.score} type={prediction.predictionType} />
                        <button
                          type="button"
                          onClick={() => setActiveHotspot(showing ? null : id)}
                          className="text-sm underline text-primary"
                        >
                          {showing ? "Hide alternatives" : "View alternatives"}
                        </button>
                      </div>
                      {showing && (
                        <div className="mt-2 ml-4 border-l border-primary pl-4">
                          {alternatives.length === 0 ? (
                            <p className="text-xs text-muted-foreground">No suitable alternatives.</p>
                          ) : (
                            alternatives.map(rec => (
                              <div key={rec.place.id} className="flex items-center justify-between mb-2">
                                <div>
                                  <span className="font-semibold">{rec.place.name}</span>
                                  <p className="text-xs text-muted-foreground">{rec.reason}</p>
                                  <p className="text-xs text-muted-foreground">{rec.distanceLabel}</p>
                                </div>
                                <button
                                  type="button"
                                  onClick={() => {
                                    onReplace(date, id, rec.place.id);
                                    setActiveHotspot(null);
                                  }}
                                  className="rounded-full bg-emerald-600 px-3 py-1 text-xs text-white"
                                >
                                  Replace
                                </button>
                              </div>
                            ))
                          )}
                        </div>
                      )}
                      {reasonMap.get(id) && (
                        <p className="mt-1 text-xs text-emerald-700 dark:text-emerald-300">
                          AI insight: {reasonMap.get(id)}
                        </p>
                      )}
                      <p className="mt-1 text-xs text-muted-foreground">
                        Estimated visit slot · approximately {Math.round(step * 60)} minutes including transition buffer
                      </p>
                    </li>
                  );
                })}
              </ol>
            )}

            {/* Food section */}
            <div className="mt-6">
              {foodSelections[date] ? (
                <div className="flex items-center gap-2">
                  <span className="font-medium">Meal selected:</span>
                  <span>{foodSelections[date]}</span>
                  <button
                    type="button"
                    onClick={() => onRemoveFood(date)}
                    className="text-sm underline text-primary"
                  >
                    Remove
                  </button>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => setShowFood(prev => ({ ...prev, [date]: !prev[date] }))}
                  className="rounded-full bg-amber-600 px-3 py-1 text-xs text-white"
                >
                  {showFood[date] ? "Hide meals" : "Explore nearby food"}
                </button>
              )}

              {showFood[date] && (
                <ol className="mt-3 space-y-2 border-l-2 border-dashed border-amber-500 pl-4">
                  {foodRecs.map(rec => (
                    <li key={rec.restaurant.id} className="flex items-center justify-between">
                      <div>
                        <span className="font-semibold">{rec.restaurant.name}</span>
                        <p className="text-xs text-muted-foreground">{rec.reason}</p>
                        <p className="text-xs text-muted-foreground">{rec.distanceLabel}</p>
                      </div>
                      <button
                        type="button"
                        onClick={() => onSelectFood(date, rec.restaurant.id)}
                        className="rounded-full bg-emerald-600 px-3 py-1 text-xs text-white"
                      >
                        Select
                      </button>
                    </li>
                  ))}
                </ol>
              )}
            </div>
          </section>
        );
      })}
    </div>
  );
}
