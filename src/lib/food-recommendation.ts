// src/lib/food-recommendation.ts
/**
 * Simple deterministic food recommendation engine.
 * It considers the day's attractions, the user's food preference, and a
 * per‑person budget heuristic. The result is up to three nearby restaurants
 * with a short explanatory reason.
 */
import type { ItineraryRequest } from "@/lib/itinerary-request";
import { PLACES } from "@/lib/jaipur-data";
import { calculateStraightLineDistanceKm } from "@/lib/recommendation";

export interface Restaurant {
  id: string;
  name: string;
  area: string;
  lat: number | null;
  lng: number | null;
  cuisine: string;
  vegetarian: boolean;
  priceRange: string; // e.g. "200-400"
  openingHours: string;
  description: string;
  sourceTitle: string;
  sourceUrl: string;
  verificationDate: string;
  verificationStatus: string;
}


import restaurantsData from "../../backend/data/food/restaurants.json";
const RESTAURANTS: Restaurant[] = (restaurantsData as unknown) as Restaurant[];

interface FoodRecommendation {
  restaurant: Restaurant;
  distanceKm: number;
  distanceLabel: string;
  reason: string;
}

/**
 * Parses a price range like "200-400" and returns [min, max] numbers.
 */
function parsePriceRange(range: string): [number, number] {
  const parts = range.split("-");
  const min = parseInt(parts[0], 10) || 0;
  const max = parseInt(parts[1], 10) || min;
  return [min, max];
}

/**
 * Returns a human‑readable distance label.
 */
function formatDistance(km: number): string {
  if (km < 1) return `${Math.round(km * 1000)} m`;
  return `${km.toFixed(1)} km`;
}

/**
 * Recommend food for a given day.
 *
 * @param attractionIds  IDs of the attractions scheduled for the day.
 * @param request        Full itinerary request (contains foodPreference & budget).
 * @param perPersonBudget Optional budget per person for a meal.
 * @returns up to three recommendations sorted by proximity and preference.
 */
export function recommendFoodForDay(
  attractionIds: string[],
  request: ItineraryRequest,
  perPersonBudget?: number
): FoodRecommendation[] {
  // Determine vegetarian filter based on request.foodPreference
  const pref = request.foodPreference?.toLowerCase() ?? "none";
  const wantVegetarian = pref === "vegetarian" || pref === "vegan" || pref === "jain";

  // Gather coordinates of all attractions for distance calculations
  const attractionCoords = attractionIds
    .map((id) => PLACES.find((p) => p.id === id))
    .filter((p) => !!p)
    .map((p) => ({ lat: p!.lat, lng: p!.lng }));

  // Score each restaurant
  const scored = RESTAURANTS.map((rest) => {
    // Preference filter
    const vegOk = !wantVegetarian || rest.vegetarian;
    // Budget filter (if provided)
    const [minPrice] = parsePriceRange(rest.priceRange);
    const budgetOk = perPersonBudget === undefined || minPrice <= perPersonBudget;

    // Skip restaurants without reliable coordinates
    const hasCoords = rest.lat != null && rest.lng != null;
    if (!hasCoords) {
      return { restaurant: rest, distanceKm: Infinity, passes: false };
    }

    // Distance to the nearest attraction of the day
    const distances = attractionCoords.map((a) =>
      calculateStraightLineDistanceKm(a.lat, a.lng, rest.lat as number, rest.lng as number)
    );
    const minDist = distances.length ? Math.min(...distances) : Infinity;

    const passes = vegOk && budgetOk;
    return {
      restaurant: rest,
      distanceKm: minDist,
      passes,
    };
  });

  // Filter and sort
  const filtered = scored
    .filter((s) => s.passes)
    .sort((a, b) => a.distanceKm - b.distanceKm)
    .slice(0, 3);

  // Build final recommendations with reason strings
  return filtered.map((s) => {
    const label = formatDistance(s.distanceKm);
    const reasonParts: string[] = [];
    if (wantVegetarian) reasonParts.push("vegetarian-friendly");
    const [minPrice, maxPrice] = parsePriceRange(s.restaurant.priceRange);
    reasonParts.push(`₹${minPrice}-${maxPrice}`);
    return {
      restaurant: s.restaurant,
      distanceKm: s.distanceKm,
      distanceLabel: label,
      reason: reasonParts.join(", "),
    };
  });
}
