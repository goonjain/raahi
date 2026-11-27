import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import MultiDayItinerary from "@/components/musafir/MultiDayItinerary";
import PlannerWizard from "@/components/musafir/PlannerWizard";
import type { ItineraryRequest } from "@/lib/itinerary-request";

describe("MultiDayItinerary", () => {
  const baseRequest: ItineraryRequest = {
    startDate: "2026-12-01",
    endDate: "2026-12-03",
    locationType: "hotel",
    interests: ["heritage", "photography"],
    mustVisit: ["amber"],
    foodPreference: "none",
    dietaryRestrictions: "",
    groupType: "friends",
    groupSize: 2,
    budget: 5000,
    travelPace: "balanced",
    crowdTolerance: "avoid",
    hiddenGemsPreference: "yes",
  };

  it("renders Day 1, Day 2, Day 3 cards, AI insights, and supports Replace and Undo", () => {
    const onReplace = vi.fn();
    const onUndo = vi.fn();

    render(
      <MultiDayItinerary
        byDay={{
          "2026-12-01": ["amber", "panna"],
          "2026-12-02": ["hawa", "jantar"],
          "2026-12-03": ["nahargarh"],
        }}
        request={baseRequest}
        observations={[]}
        onOptimizeDay={vi.fn()}
        onReplace={onReplace}
        onUndo={onUndo}
        canUndoByDay={{ "2026-12-01": true }}
        foodSelections={{}}
        onSelectFood={vi.fn()}
        onRemoveFood={vi.fn()}
        feedback={{}}
        aiProposals={[
          {
            attraction_ids: ["amber"],
            restaurant_ids: [],
            reason: "Early morning visit avoids peak tour bus congestion.",
            evidence_refs: [],
          },
        ]}
      />,
    );

    expect(screen.getByText(/Day 1 —/)).toBeInTheDocument();
    expect(screen.getByText(/Day 2 —/)).toBeInTheDocument();
    expect(screen.getByText(/Day 3 —/)).toBeInTheDocument();
    expect(screen.getByText(/AI insight: Early morning visit avoids peak tour bus congestion\./)).toBeInTheDocument();

    // Undo button works
    fireEvent.click(screen.getByText("Undo last replacement"));
    expect(onUndo).toHaveBeenCalledWith("2026-12-01");

    // View alternatives & Replace works
    const viewAltButtons = screen.getAllByText("View alternatives");
    fireEvent.click(viewAltButtons[0]);
    const replaceButtons = screen.getAllByText("Replace");
    fireEvent.click(replaceButtons[0]);
    expect(onReplace).toHaveBeenCalledTimes(1);
    expect(onReplace.mock.calls[0][0]).toBe("2026-12-01");
    expect(onReplace.mock.calls[0][1]).toBe("amber");
  });
});

describe("PlannerWizard finalize", () => {
  it("awaits onGenerateRequest without calling legacy onGenerate", async () => {
    const onGenerate = vi.fn();
    let resolveRequest!: () => void;
    const onGenerateRequest = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          resolveRequest = resolve;
        }),
    );

    const { container } = render(
      <PlannerWizard
        plan={{
          day: "Sun",
          time: "full",
          budget: 2000,
          interests: ["heritage"],
          type: "friends",
          crowd: "avoid",
          must: "amber",
        }}
        setPlan={vi.fn()}
        onGenerate={onGenerate}
        onGenerateRequest={onGenerateRequest}
      />,
    );

    // Step 1: dates and locationType
    const dateInputs = container.querySelectorAll('input[type="date"]');
    fireEvent.change(dateInputs[0], { target: { value: "2026-12-01" } });
    fireEvent.change(dateInputs[1], { target: { value: "2026-12-03" } });
    fireEvent.click(screen.getByText("Hotel / Stay"));
    fireEvent.click(screen.getByText("Continue"));

    // Step 2: interest already selected ("heritage")
    fireEvent.click(screen.getByText("Continue"));

    // Step 3: groupType, groupSize, budget, travelPace
    fireEvent.click(screen.getByText("Friends"));
    fireEvent.click(screen.getByText("+"));
    fireEvent.change(screen.getByPlaceholderText("Custom"), { target: { value: "5000" } });
    fireEvent.click(screen.getByText(/Balanced/));
    fireEvent.click(screen.getByText("Continue"));

    // Step 4: crowdPref already "avoid", select hiddenGemsPreference
    fireEvent.click(screen.getByText("Yes, surprise me"));
    fireEvent.click(screen.getByText("Plan My Jaipur Trip"));

    expect(onGenerateRequest).toHaveBeenCalledTimes(1);
    expect(onGenerate).not.toHaveBeenCalled();

    resolveRequest();
    await waitFor(() => {
      expect(screen.getByText("Plan My Jaipur Trip")).toBeInTheDocument();
    });
    expect(onGenerate).not.toHaveBeenCalled();
  });
});

