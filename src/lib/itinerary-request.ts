// src/lib/itinerary-request.ts
/**
 * Types representing the full set of questionnaire inputs needed to generate an itinerary.
 */
import { TripPreferences } from '@/components/musafir/TripPreferences';
import { Plan } from '@/components/musafir/PlannerWizard';

export interface ItineraryRequest {
  // Dates (ISO strings)
  startDate: string; // e.g., "2026-11-27"
  endDate: string; // inclusive
  startTime?: string; // optional start-of-trip local clock time HH:mm
  endTime?: string; // optional end-of-trip local clock time HH:mm
  // Starting location type (hotel, station, other) and optional custom location
  locationType: string;
  customLocation?: string;
  // Vibe interests (array of vibe IDs like "heritage", "photography", etc.)
  interests: string[];
  // Must‑visit attraction IDs (from PLACES)
  mustVisit: string[];
  // Food preference (none, vegetarian, vegan, nonVegetarian, jain)
  foodPreference: string;
  // Dietary restrictions free‑form text
  dietaryRestrictions: string;
  // Group details
  groupType: string;
  groupSize: number;
  // Budget (numeric, assumed in INR)
  budget: number;
  // Travel pace (relaxed, balanced, packed)
  travelPace: string;
  // Crowd tolerance (avoid, neutral, any)
  crowdTolerance: string;
  // Hidden gems preference (yes, maybe, no)
  hiddenGemsPreference: string;
  // Additional notes from each step (free‑form)
  notesStep1?: string;
  notesStep2?: string;
  notesStep3?: string;
  notesStep4?: string;
}

/**
 * Helper to convert the component state (Plan + TripPreferences) into an ItineraryRequest.
 * This function lives here to keep UI components thin.
 */
export function buildRequest(plan: Plan, prefs: TripPreferences): ItineraryRequest {
  return {
    startDate: prefs.startDateTime.split('T')[0],
    endDate: prefs.endDateTime.split('T')[0],
    startTime: prefs.startDateTime.split('T')[1] || undefined,
    endTime: prefs.endDateTime.split('T')[1] || undefined,
    locationType: prefs.locationType,
    customLocation: prefs.customLocation,
    interests: plan.interests,
    mustVisit: prefs.mustVisit,
    foodPreference: prefs.foodPreference,
    dietaryRestrictions: prefs.dietaryRestrictions,
    groupType: prefs.groupType,
    groupSize: prefs.groupSize,
    budget: prefs.budget,
    travelPace: prefs.travelPace,
    crowdTolerance: prefs.crowdTolerance,
    hiddenGemsPreference: prefs.hiddenGemsPreference,
    notesStep1: prefs.notesStep1,
    notesStep2: prefs.notesStep2,
    notesStep3: prefs.notesStep3,
    notesStep4: prefs.notesStep4,
  };
}

