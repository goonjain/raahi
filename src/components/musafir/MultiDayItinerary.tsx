import type { ItineraryRequest } from "@/lib/itinerary-request";
import { PLACES } from "@/lib/jaipur-data";
import { predictCrowd, type VerifiedObservation } from "@/lib/crowd-service";
import { Badge } from "./Sections";
import { sightseeingBounds, visitStepHours } from "@/lib/itinerary-planner";

type Props = {
  byDay: Record<string, string[]>;
  request: ItineraryRequest;
  observations: VerifiedObservation[];
  onOptimizeDay: (date: string) => void;
  feedback: Record<string, string>;
};

function formatHour(hour: number): string {
  const h = Math.floor(hour);
  const m = Math.round((hour - h) * 60);
  return `${(h % 12) || 12}:${String(m).padStart(2, "0")} ${h < 12 ? "AM" : "PM"}`;
}

export default function MultiDayItinerary({ byDay, request, observations, onOptimizeDay, feedback }: Props) {
  const dates = Object.keys(byDay).sort();
  return (
    <div className="space-y-7">
      <div className="rounded-2xl border bg-card p-5 shadow">
        <h3 className="font-display text-2xl text-primary">Your Jaipur itinerary</h3>
        <p className="mt-1 text-sm text-muted-foreground">
          {dates.length} calendar day{dates.length === 1 ? "" : "s"} · {request.groupSize} traveller{request.groupSize === 1 ? "" : "s"} · ₹{request.budget.toLocaleString("en-IN")} total group budget
        </p>
        <p className="mt-2 text-xs text-muted-foreground">Timings are planning estimates; travel times, venue hours and admission availability are not verified here.</p>
      </div>
      {dates.map((date, dayIndex) => {
        const ids = byDay[date];
        const { start, end } = sightseeingBounds(request, date);
        const step = visitStepHours(request.travelPace);
        const weekday = new Intl.DateTimeFormat("en-US", { weekday: "short", timeZone: "UTC" }).format(new Date(`${date}T12:00:00Z`));
        const formattedDate = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" }).format(new Date(`${date}T12:00:00Z`));
        return (
          <section key={date} className="rounded-2xl border bg-card p-5 shadow md:p-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h4 className="font-display text-xl text-primary">Day {dayIndex + 1} — {formattedDate}</h4>
                <p className="text-xs text-muted-foreground">{weekday} · {formatHour(start)}–{formatHour(end)} suggested sightseeing window</p>
              </div>
              <button type="button" onClick={() => onOptimizeDay(date)} disabled={ids.length < 3}
                className="rounded-full bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground disabled:cursor-not-allowed disabled:opacity-50">
                Optimize Day {dayIndex + 1}
              </button>
            </div>
            {feedback[date] && <p className="mt-3 text-sm text-muted-foreground" role="status">{feedback[date]}</p>}
            {ids.length === 0 ? (
              <p className="mt-5 text-sm text-muted-foreground">No attractions fit this day's available time or preferences. This is free time; adjust your dates or preferences to include more stops.</p>
            ) : (
              <ol className="mt-5 space-y-4 border-l-2 border-dashed border-primary pl-6">
                {ids.map((id, i) => {
                  const place = PLACES.find((p) => p.id === id);
                  if (!place) return null;
                  const hour = start + i * step;
                  const prediction = predictCrowd(id, { day: weekday, hour: Math.floor(hour), observations });
                  return (
                    <li key={id} className="relative">
                      <span className="absolute -left-[33px] top-1 block h-4 w-4 rounded-full bg-saffron ring-4 ring-background" />
                      <div className="flex flex-wrap items-center gap-3">
                        <span className="font-display text-primary">{formatHour(hour)}</span>
                        <span className="font-semibold">{place.name}</span>
                        {place.gem && <span className="rounded-full bg-gem px-2 py-0.5 text-xs text-primary-foreground">Hidden gem</span>}
                        <Badge score={prediction.score} type={prediction.predictionType} />
                      </div>
                      <p className="mt-1 text-xs text-muted-foreground">Estimated visit slot · approximately {Math.round(step * 60)} minutes including transition buffer</p>
                    </li>
                  );
                })}
              </ol>
            )}
          </section>
        );
      })}
    </div>
  );
}
