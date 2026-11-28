import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import hero from "@/assets/hero-jaipur.jpg";
import { api, BACKEND_ORIGIN, type DestinationItem } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import {
  SectionTitle,
  Planner,
  Itinerary,
  Forecast,
  HiddenGems,
  LiveMap,
  Pulse,
  Extras,
  type Plan,
  type Report,
} from "@/components/musafir/Sections";
import { byId } from "@/lib/jaipur-data";
import { applyStopReplacement, removeStopReplacement } from "@/lib/recommendation";
import { generateItinerary, optimizeDayStops } from "@/lib/itinerary-planner";
import type { ItineraryRequest } from "@/lib/itinerary-request";
import MultiDayItinerary from "@/components/musafir/MultiDayItinerary";
import { observationsRepository, type CrowdReportRecord } from "@/lib/observations-repository";
import type { VerifiedObservation } from "@/lib/crowd-service";
import { BellRing } from "lucide-react";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Raahi — Crowd-Aware Travel for Jaipur" },
      {
        name: "description",
        content:
          "Plan a low-crowd day in the Pink City with explainable crowd forecasting, smart diversion routes, and verified hidden gems.",
      },
      { property: "og:title", content: "Raahi — Crowd-Aware Travel for Jaipur" },
      {
        property: "og:description",
        content:
          "Smart crowd dispersal, live verified monument observations, and cultural hidden gems across Jaipur.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Index,
});

const NAV: [string, string][] = [
  ["planner", "Planner"],
  ["forecast", "Forecast"],
  ["gems", "Hidden Gems"],
  ["map", "Live Map"],
  ["pulse", "Pulse"],
  ["rewards", "Rewards"],
];

function computeAdjustments(reps: Report[]): Record<string, number> {
  const adj: Record<string, number> = {};
  for (const r of reps) {
    if (r.moderation_status && r.moderation_status !== "approved") continue;
    const p = r.place || r.destination_id;
    if (p && !(p in adj)) {
      const s = r.status || r.crowd_level;
      adj[p] = s === "Busy" ? 15 : s === "Packed" ? 25 : s === "Quiet" ? -15 : 0;
    }
  }
  return adj;
}

function Index() {
  const { user: currentUser, logout } = useAuth();
  const [plan, setPlan] = useState<Plan>({
    day: "Sun",
    time: "full",
    budget: 2000,
    interests: ["heritage", "photography"],
    type: "friends",
    crowd: "avoid",
    must: "amber",
  });

  const handleSelectFood = (date: string, restaurantId: string) => {
    setFoodSelections((prev) => ({ ...prev, [date]: restaurantId }));
  };

  const handleRemoveFood = (date: string) => {
    setFoodSelections((prev) => {
      const next = { ...prev };
      delete next[date];
      return next;
    });
  };
  const [foodSelections, setFoodSelections] = useState<Record<string, string | undefined>>({});

  const [shown, setShown] = useState(false);
  const [optimized, setOptimized] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  // Rewards balance
  const [points, setPoints] = useState<number>(() => observationsRepository.getUserProfile().points);

  // Community Pulse data
  const [communityReports, setCommunityReports] = useState<Report[]>([]);
  const [destinations, setDestinations] = useState<DestinationItem[]>([]);
  const [loadingReports, setLoadingReports] = useState(true);
  const [reportsError, setReportsError] = useState<string | null>(null);
  const [pulseAdj, setPulseAdj] = useState<Record<string, number>>({});

  // Local persistent observation repository state
  const [, setRepoReports] = useState<CrowdReportRecord[]>(() =>
    observationsRepository.getReports("all"),
  );
  const [observations, setObservations] = useState<VerifiedObservation[]>(() =>
    observationsRepository.getActiveObservations(),
  );
  const [adminOverrides, setAdminOverrides] = useState<Record<string, number>>(() =>
    observationsRepository.getAdminOverrides(),
  );
  const [activeBroadcast, setActiveBroadcast] = useState<string | null>(() =>
    observationsRepository.getActiveBroadcast(),
  );

  // State for multi‑day itinerary
  const [itineraryByDay, setItineraryByDay] = useState<Record<string, string[]> | null>(null);
  const [itineraryRequest, setItineraryRequest] = useState<ItineraryRequest | null>(null);
  const [aiProposals, setAiProposals] = useState<any[]>([]);
  const [optimizationFeedback, setOptimizationFeedback] = useState<Record<string, string>>({});
  const [previousDayBeforeReplace, setPreviousDayBeforeReplace] = useState<Record<string, string[]>>({});
  const multiDayRef = useRef<HTMLDivElement | null>(null);
  const legacyItineraryRef = useRef<HTMLDivElement | null>(null);
  const pendingItineraryScrollRef = useRef(false);
  const pendingLegacyScrollRef = useRef(false);

  useEffect(() => {
    if (pendingItineraryScrollRef.current && itineraryByDay && itineraryRequest) {
      pendingItineraryScrollRef.current = false;
      multiDayRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [itineraryByDay, itineraryRequest]);

  useEffect(() => {
    if (pendingLegacyScrollRef.current && shown) {
      pendingLegacyScrollRef.current = false;
      legacyItineraryRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [shown]);


  // Callback from PlannerWizard with full request – now integrates Groq recommendations
  const handleGenerateRequest = async (req: ItineraryRequest) => {
    let preferredIds: string[] | undefined = undefined;
    let proposals: any[] = [];
    try {
      const res = await fetch(`${BACKEND_ORIGIN}/v1/itinerary/recommendations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(req),
      });
      if (res.ok) {
        const json = await res.json();
        if (json && Array.isArray(json.proposals) && json.proposals.length) {
          proposals = json.proposals;
          const ids = json.proposals.flatMap((p: any) => p.attraction_ids ?? []);
          const seen = new Set<string>();
          const validIds = ids.filter((id: string) => {
            const ok = byId(id) && !seen.has(id);
            if (ok) seen.add(id);
            return ok;
          });
          if (validIds.length) preferredIds = validIds;
        }
      }
    } catch (e) {
      // fallback – ignore and use deterministic generation
    }
    // Store AI proposals for UI explanations (even if empty)
    setAiProposals(proposals);
    const result = generateItinerary(req, preferredIds);
    const optimizedResult: Record<string, string[]> = {};
    for (const [date, ids] of Object.entries(result)) {
      optimizedResult[date] = optimizeDayStops(ids);
    }
    pendingItineraryScrollRef.current = true;
    setItineraryByDay(optimizedResult);
    setItineraryRequest(req);
    setOptimizationFeedback({});
    setPreviousDayBeforeReplace({});
  };

  const handleOptimizeDay = (date: string) => {
    const oldIds = itineraryByDay?.[date];
    if (!oldIds) return;
    const optimizedIds = optimizeDayStops(oldIds);
    const changed = optimizedIds.join("|") !== oldIds.join("|");
    if (changed) setItineraryByDay((previous) => (previous ? { ...previous, [date]: optimizedIds } : previous));
    setOptimizationFeedback((previous) => ({
      ...previous,
      [date]: changed
        ? "Stops reordered using approximate geographic proximity."
        : "This route is already as short as the available approximation can find.",
    }));
  };

  const handleReplaceMultiDay = (
    date: string,
    hotspotId: string,
    alternativeId: string,
  ) => {
    const currentIds = itineraryByDay?.[date];
    if (!currentIds) return;

    const index = currentIds.indexOf(hotspotId);
    if (index === -1 || currentIds.includes(alternativeId)) return;

    // Remember the day before replacement.
    setPreviousDayBeforeReplace((prev) => ({
      ...prev,
      [date]: [...currentIds],
    }));

    // Replace the attraction.
    const updatedIds = [...currentIds];
    updatedIds[index] = alternativeId;

    // Reorder the updated stops geographically.
    const optimizedIds = optimizeDayStops(updatedIds);

    // Update only the affected day.
    setItineraryByDay((prev) =>
      prev ? { ...prev, [date]: optimizedIds } : prev
    );

    setOptimizationFeedback((prev) => ({
      ...prev,
      [date]:
        "Attraction replaced and stop order recalculated using approximate geographic proximity.",
    }));
  };

  const handleUndoMultiDay = (date: string) => {
    const previousIds = previousDayBeforeReplace[date];
    if (!previousIds) return;

    // Re‑optimize the restored stops.
    const optimizedIds = optimizeDayStops(previousIds);
    setItineraryByDay((prev) =>
      prev ? { ...prev, [date]: optimizedIds } : prev
    );

    setPreviousDayBeforeReplace((prev) => ({
      ...prev,
      [date]: undefined,
    }));

    setOptimizationFeedback((prev) => ({
      ...prev,
      [date]: "Previous itinerary restored and re‑optimized.",
    }));
  };

  // Map focus and destination selection state
  const [selectedMapPlaceId, setSelectedMapPlaceId] = useState<string | null>(null);
  const [mapFocusKey, setMapFocusKey] = useState<number>(0);

  // Synchronize state whenever persistent repository is updated
  useEffect(() => {
    const unsubscribe = observationsRepository.subscribe(() => {
      setRepoReports(observationsRepository.getReports("all"));
      setObservations(observationsRepository.getActiveObservations());
      setPoints(observationsRepository.getUserProfile().points);
      setAdminOverrides(observationsRepository.getAdminOverrides());
      setActiveBroadcast(observationsRepository.getActiveBroadcast());
    });
    return unsubscribe;
  }, []);

  const fetchDestinations = async () => {
    const list = await api.getDestinations();
    if (list && list.length > 0) {
      setDestinations(list);
    }
  };

  const fetchReports = async () => {
    setLoadingReports(true);
    setReportsError(null);
    const res = await api.getReports();
    if (res.data?.reports) {
      const fetchedReports = res.data.reports as Report[];
      setCommunityReports(fetchedReports);
      setPulseAdj(computeAdjustments(fetchedReports));
      setReportsError(null);
    } else {
      setReportsError(res.error || "Unable to connect to community backend database.");
    }
    setLoadingReports(false);
  };

  const fetchRewards = async () => {
    const res = await api.getRewardBalance();
    if (res.data) {
      const serverPoints = res.data.total_points;
      const localPoints = observationsRepository.getUserProfile().points;
      const maxPoints = Math.max(serverPoints, localPoints);
      setPoints(maxPoints);
      if (serverPoints > localPoints) {
        observationsRepository.awardPoints(serverPoints - localPoints);
      }
    }
  };

  useEffect(() => {
    fetchDestinations();
    fetchReports();

    const handleModerationSync = (e: StorageEvent) => {
      if (e.key === "raahi_moderation_sync_ts") {
        fetchReports();
        if (currentUser) fetchRewards();
      }
    };
    const handleVisibilityOrFocus = () => {
      if (document.visibilityState === "visible") {
        fetchReports();
      }
    };
    window.addEventListener("storage", handleModerationSync);
    window.addEventListener("focus", handleVisibilityOrFocus);
    document.addEventListener("visibilitychange", handleVisibilityOrFocus);
    return () => {
      window.removeEventListener("storage", handleModerationSync);
      window.removeEventListener("focus", handleVisibilityOrFocus);
      document.removeEventListener("visibilitychange", handleVisibilityOrFocus);
    };
  }, [currentUser]);

  useEffect(() => {
    if (currentUser) {
      fetchRewards();
    }
  }, [currentUser]);

  const reward = (n: number, msg = `+${n} Raahi points!`) => {
    observationsRepository.awardPoints(n);
    setPoints((p) => p + n);
    setToast(msg);
    setTimeout(() => setToast(null), 2500);
  };

  const go = (id: string) => document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });

  const handleShowOnMap = (placeId: string) => {
    setSelectedMapPlaceId(placeId);
    setMapFocusKey((k) => k + 1);
    go("map");
  };

  const handleReplaceInRoute = (hotspotId: string, gemId: string) => {
    setPlan((prevPlan) => applyStopReplacement(prevPlan, hotspotId, gemId));
    setShown(true);
    reward(20, `Added ${byId(gemId).name} to itinerary! (+20 pts)`);
  };

  const handleRemoveFromRoute = (hotspotId: string) => {
    setPlan((prevPlan) => removeStopReplacement(prevPlan, hotspotId));
    setToast(`Restored original stop for ${byId(hotspotId).name}`);
    setTimeout(() => setToast(null), 2000);
  };

  const handleResetReplacements = () => {
    setPlan((prevPlan) => ({
      ...prevPlan,
      stopReplacements: undefined,
    }));
    setToast("Reset all itinerary stops to original");
    setTimeout(() => setToast(null), 2000);
  };

  const handleSubmitReport = async (payload: {
    destination_id: string;
    crowd_level: "Quiet" | "Moderate" | "Busy" | "Packed";
    vs_forecast?: "Quieter" | "About right" | "Busier";
    wait_minutes?: number;
    tip?: string;
    image?: string;
    user_name?: string;
  }) => {
    const res = await api.submitReport(payload);
    if (!res.data || !res.data.success) {
      const errorMsg = res.error || "Check-in failed. Please verify your details and try again.";
      setToast(`⚠ ${errorMsg}`);
      setTimeout(() => setToast(null), 3500);
      return { success: false, error: errorMsg };
    }

    const newReport = res.data.report as Report;

    // Only insert into the public verified feed if already approved; pending reports await admin verification
    if (newReport.moderation_status === "approved") {
      setCommunityReports((prev) => {
        if (prev.some((r) => r.id === newReport.id)) return prev;
        return [newReport, ...prev];
      });
      const shift =
        payload.crowd_level === "Busy"
          ? 15
          : payload.crowd_level === "Packed"
          ? 25
          : payload.crowd_level === "Quiet"
          ? -15
          : 0;
      setPulseAdj((a) => ({ ...a, [payload.destination_id]: shift }));
    }

    const successMsg =
      newReport.moderation_status === "approved"
        ? res.data.message || `Check-in shared · +${res.data.points_awarded ?? 20} pts!`
        : `Report #${newReport.id} submitted (Pending Review). It will appear in the Shared Community Feed once verified by an admin.`;
    setToast(successMsg);
    setTimeout(() => setToast(null), 2500);
    return { success: true, message: successMsg };
  };

  const handleVoteAccuracy = async (reportId: number) => {
    const res = await api.voteAccuracy(reportId, 1);
    if (res.data?.success) {
      setCommunityReports((prev) =>
        prev.map((r) =>
          r.id === reportId
            ? { ...r, accuracy_votes_count: (r.accuracy_votes_count || 0) + 1, trust_weight: res.data!.trust_weight }
            : r,
        ),
      );
      setToast("Accuracy verified! Trust weight updated.");
      setTimeout(() => setToast(null), 2200);
    } else if (res.error) {
      setToast(res.error);
      setTimeout(() => setToast(null), 2200);
    }
  };

  const handleFlagReport = async (reportId: number) => {
    const res = await api.flagReport(reportId);
    if (res.data?.success) {
      setCommunityReports((prev) =>
        prev.map((r) => (r.id === reportId ? { ...r, moderation_status: "flagged" } : r)),
      );
      setToast("Report flagged for moderation review.");
      setTimeout(() => setToast(null), 2200);
    }
  };

  return (
    <div className="min-h-screen">
      {/* Active City Broadcast Advisory Banner */}
      {activeBroadcast && (
        <div className="sticky top-0 z-50 bg-gradient-to-r from-amber-900 via-red-900 to-amber-900 border-b border-amber-500/40 px-4 py-2 text-xs text-amber-100 flex items-center justify-between shadow-md">
          <div className="flex items-center gap-2 overflow-hidden mx-auto max-w-7xl w-full">
            <BellRing className="w-4 h-4 text-amber-300 shrink-0 animate-bounce" />
            <span className="font-bold uppercase tracking-wider text-[10px] bg-red-600 px-1.5 py-0.5 rounded text-white">
              Official DoT Advisory:
            </span>
            <span className="truncate font-medium">{activeBroadcast}</span>
          </div>
        </div>
      )}

      {/* Main Top Header */}
      <header
        className={`sticky ${activeBroadcast ? "top-[37px]" : "top-0"} z-40 border-b bg-background/90 backdrop-blur`}
      >
        <div className="mx-auto flex max-w-7xl items-center gap-6 px-4 py-3">
          <button onClick={() => go("top")} className="flex items-baseline gap-2">
            <span className="font-display text-2xl text-primary font-bold">राही</span>
            <span className="text-base font-semibold text-foreground">Raahi</span>
            <span className="text-xs text-muted-foreground hidden sm:inline">| जयपुर</span>
          </button>
          <nav className="hidden flex-1 justify-center gap-5 text-sm md:flex">
            {NAV.map(([id, l]) => (
              <button
                key={id}
                onClick={() => go(id)}
                className="hover:text-primary transition font-medium"
              >
                {l}
              </button>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-2.5 md:ml-0">
            <span
              className="rounded-full bg-gold px-3 py-1 text-sm font-bold text-foreground shadow-sm"
              title="Your persisted Raahi reward balance"
            >
              🪙 {points} pts
            </span>
            {currentUser ? (
              <>
                <span
                  className="hidden sm:inline-flex items-center gap-1.5 rounded-full bg-secondary px-3 py-1 text-xs font-semibold text-secondary-foreground border border-border"
                  title={`Signed in as ${currentUser.email}`}
                >
                  <span>{currentUser.name}</span>
                  {currentUser.role === "admin" && (
                    <span className="rounded bg-primary/15 px-1.5 py-0.5 text-[10px] font-bold uppercase text-primary">
                      Admin
                    </span>
                  )}
                </span>
                {currentUser.role === "admin" && (
                  <Link
                    to="/admin"
                    className="inline-flex items-center gap-1.5 rounded-full bg-neutral-900 px-3 py-1 text-xs font-semibold text-amber-400 border border-amber-500/40 hover:bg-neutral-800 transition shadow-sm"
                    title="Open Rajasthan Tourism Command Center"
                  >
                    <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
                    DoT Admin
                  </Link>
                )}
                <button
                  type="button"
                  onClick={() => void logout()}
                  className="rounded-full border border-border bg-card px-3 py-1 text-xs font-semibold text-foreground hover:bg-secondary transition"
                >
                  Sign Out
                </button>
              </>
            ) : (
              <Link
                to="/login"
                className="inline-flex items-center gap-1.5 rounded-full bg-primary px-3.5 py-1 text-xs font-semibold text-primary-foreground hover:bg-primary/90 transition shadow-sm"
              >
                Sign In
              </Link>
            )}
          </div>
        </div>
        <div className="border-bandhani" />
      </header>

      {/* Hero Section */}
      <section id="top" className="relative flex min-h-[88vh] items-center overflow-hidden">
        <img
          src={hero}
          alt="Hawa Mahal at sunrise, Jaipur"
          width={1600}
          height={912}
          className="absolute inset-0 h-full w-full object-cover"
        />
        <div className="absolute inset-0 bg-gradient-to-r from-indigo-deep/90 via-indigo-deep/60 to-transparent" />
        <div className="relative mx-auto w-full max-w-7xl px-4 text-primary-foreground">
          <p className="font-display text-xl text-gold">पधारो म्हारे देस · Welcome to the Pink City</p>
          <h1 className="mt-3 max-w-3xl text-5xl leading-tight md:text-7xl font-bold">
            Same city, same day. <span className="text-saffron">Half the crowd.</span>
          </h1>
          <p className="mt-5 max-w-xl text-lg opacity-90 leading-relaxed">
            Raahi predicts tourist congestion across Jaipur and redirects you to rich cultural gems
            that match your vibe — from early Amer Fort mornings to tranquil stepwells.
          </p>
          <div className="mt-8 flex flex-wrap gap-4">
            <button
              onClick={() => go("planner")}
              className="rounded-full bg-primary px-8 py-3.5 font-display text-lg text-primary-foreground shadow-xl transition hover:scale-105 hover:bg-saffron"
            >
              Plan my Jaipur day
            </button>
            <button
              onClick={() => go("map")}
              className="rounded-full border-2 border-white/40 bg-white/10 backdrop-blur px-6 py-3.5 text-base font-semibold text-white hover:bg-white/20 transition"
            >
              Explore Live Map 🗺
            </button>
          </div>
          <div className="mt-12 flex flex-wrap gap-8 text-sm">
            {[
              ["428+ Cr", "domestic tourist visits in 2025"],
              ["16", "curated Jaipur monuments"],
              ["-45%", "crowd exposure via Smart Route"],
            ].map(([a, b]) => (
              <div key={b}>
                <p className="font-serif text-3xl text-gold">{a}</p>
                <p className="opacity-80">{b}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Main Interactive Workflows */}
      <main className="jaali">
        {/* Step 1: Personalized Trip Planner */}
        <section id="planner" className="mx-auto max-w-7xl scroll-mt-20 px-4 py-20">
          <SectionTitle
            kicker="Step 1 · यात्रा योजना"
            title="Personalized Trip Planner"
            sub="Tell us who you are. Raahi builds a feasible Jaipur day that balances time, budget, and crowd pressure."
          />
          <Planner
            plan={plan}
            setPlan={(p) => {
              setPlan(p);
              setOptimized(false);
            }}
            onGenerate={() => {
              pendingLegacyScrollRef.current = true;
              setShown(true);
              setOptimized(false);
            }}
            onGenerateRequest={handleGenerateRequest}
          />
          {itineraryByDay && itineraryRequest && (
            <div id="itinerary" ref={multiDayRef} className="mt-14 scroll-mt-24">
              <MultiDayItinerary
                byDay={itineraryByDay}
                request={itineraryRequest}
                observations={observations}
                onOptimizeDay={handleOptimizeDay}
                onReplace={handleReplaceMultiDay}
                onUndo={handleUndoMultiDay}
                canUndoByDay={Object.fromEntries(
                  Object.keys(previousDayBeforeReplace).map((date) => [date, true])
                )}
                foodSelections={foodSelections}
                onSelectFood={handleSelectFood}
                onRemoveFood={handleRemoveFood}
                feedback={optimizationFeedback}
                aiProposals={aiProposals}
              />
            </div>
          )}
          <div className="mt-8 flex justify-center">
            <button
              type="button"
              onClick={() => {
                if (!shown) {
                  pendingLegacyScrollRef.current = true;
                  setShown(true);
                } else {
                  setShown(false);
                }
              }}
              className="text-sm underline text-muted-foreground hover:text-primary"
            >
              {shown ? "Hide 1-day crowd diversion comparison" : "View 1-day crowd diversion comparison (Before vs after)"}
            </button>
          </div>
          {shown && (
            <div id="legacy-itinerary" ref={legacyItineraryRef} className="mt-8 scroll-mt-24">
              <Itinerary
                plan={plan}
                optimized={optimized}
                setOptimized={setOptimized}
                observations={observations}
                onReward={(n) => reward(n, "Smart Route unlocked · +80 Raahi points!")}
                onResetReplacements={handleResetReplacements}
              />
            </div>
          )}
        </section>

        {/* Step 2: Explainable Crowd Forecast */}
        <section id="forecast" className="scroll-mt-20 bg-secondary/60 py-20">
          <div className="mx-auto max-w-7xl px-4">
            <SectionTitle
              kicker="Step 2 · भीड़ पूर्वानुमान"
              title="Explainable Crowd Forecast"
              sub="Multi-factor baseline (v1.0) with verifiable factor attribution and on-ground observation adjustment."
            />
            <Forecast pulseAdj={pulseAdj} observations={observations} />
          </div>
        </section>

        {/* Step 3: Nearby Hidden Gems */}
        <section id="gems" className="mx-auto max-w-7xl scroll-mt-20 px-4 py-20">
          <SectionTitle
            kicker="Step 3 · छुपे रत्न"
            title="Nearby Hidden Gems"
            sub="Culturally comparable alternatives — when Amer Fort or Hawa Mahal peak, discover quiet architecture and heritage."
          />
          <HiddenGems
            plan={plan}
            onShowOnMap={handleShowOnMap}
            onReplaceInRoute={handleReplaceInRoute}
            onRemoveFromRoute={handleRemoveFromRoute}
            observations={observations}
          />
        </section>

        {/* Step 4: Live Map */}
        <section id="map" className="scroll-mt-20 bg-secondary/60 py-20">
          <div className="mx-auto max-w-7xl px-4">
            <SectionTitle
              kicker="Step 4 · जीवंत नक्शा"
              title="Raahi Live Map"
              sub="Geographic crowd distribution across Jaipur. Tap any marker to inspect baseline estimation and verified observations."
            />
            <LiveMap
              pulseAdj={pulseAdj}
              reports={communityReports}
              observations={observations}
              adminOverrides={adminOverrides}
              selectedPlaceId={selectedMapPlaceId}
              focusKey={mapFocusKey}
              onOptimize={(id) => {
                setPlan({ ...plan, must: id });
                pendingLegacyScrollRef.current = true;
                setShown(true);
                setOptimized(false);
              }}
            />
          </div>
        </section>

        {/* Step 5: Community Pulse */}
        <section id="pulse" className="mx-auto max-w-7xl scroll-mt-20 px-4 py-20">
          <SectionTitle
            kicker="Step 5 · समुदाय"
            title="Raahi Community Pulse"
            sub="On-ground traveler observations keep crowd intelligence honest. Submissions undergo verification."
          />
          <Pulse
            reports={communityReports}
            destinations={destinations}
            currentUser={currentUser}
            onDestinationAdded={(newDest) => setDestinations((prev) => [...prev, newDest])}
            loading={loadingReports}
            error={reportsError}
            onRetry={fetchReports}
            onSubmitReport={handleSubmitReport}
            onVoteAccuracy={handleVoteAccuracy}
            onFlagReport={handleFlagReport}
          />
        </section>

        {/* Step 6: Rewards & What-If */}
        <section id="rewards" className="scroll-mt-20 bg-secondary/60 py-20">
          <div className="mx-auto max-w-7xl px-4">
            <SectionTitle kicker="और भी · More" title="Rewards, Circle & Dispersal Simulation" />
            <Extras points={points} />
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="bg-indigo-deep py-12 text-center text-primary-foreground border-t border-gold/30">
        <div className="border-bandhani mb-8" />
        <p className="font-display text-3xl text-gold font-bold">राही · Raahi</p>
        <p className="mt-3 text-[11px] opacity-50">
          Crowd intelligence powered by Raahi Baseline v1.0. Community observations verified by DoT
          Command Center.
        </p>
      </footer>

      {/* Dynamic User Feedback Toast */}
      {toast && (
        <div className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2 rounded-full bg-gold px-6 py-3 font-semibold text-foreground shadow-2xl animate-in fade-in slide-in-from-bottom-4 border-2 border-foreground/10 text-sm">
          {toast}
        </div>
      )}
    </div>
  );
}
