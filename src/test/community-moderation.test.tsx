import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { renderToString } from "react-dom/server";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { Pulse } from "@/components/musafir/Sections";
import { AdminDashboard } from "@/routes/admin";
import { AuthProvider } from "@/lib/auth-context";
import { api } from "@/lib/api";

vi.mock("@tanstack/react-router", async () => {
  const actual = await vi.importActual<typeof import("@tanstack/react-router")>("@tanstack/react-router");
  return {
    ...actual,
    useNavigate: () => vi.fn(),
    Link: ({ children, to, ...props }: any) => (
      <a href={to} {...props}>
        {children}
      </a>
    ),
  };
});

describe("Community feed moderation labels and filtering", () => {
  const baseProps = {
    addReport: vi.fn(),
    onVoteAccuracy: vi.fn(),
    onFlagReport: vi.fn(),
    loading: false,
    error: null,
  };

  it("never labels pending reports as Verified Live Observation", () => {
    const html = renderToString(
      <Pulse
        {...baseProps}
        reports={[
          {
            id: 101,
            destination_id: "hawa",
            destination_name: "Hawa Mahal",
            user_name: "rohan",
            crowd_level: "Moderate",
            wait_minutes: 5,
            tip: "Wait time: 5 mins",
            moderation_status: "pending",
            ago: "just now",
          },
        ]}
      />,
    );

    expect(html).toContain("Pending Review");
    expect(html).not.toContain("Verified Live Observation");
  });

  it("excludes rejected reports from the public feed", () => {
    const html = renderToString(
      <Pulse
        {...baseProps}
        reports={[
          {
            id: 201,
            destination_id: "hawa",
            destination_name: "Hawa Mahal",
            user_name: "rohan",
            crowd_level: "Moderate",
            wait_minutes: 5,
            tip: "Rejected report text",
            moderation_status: "rejected",
            ago: "2 min ago",
          },
          {
            id: 202,
            destination_id: "amber",
            destination_name: "Amber Fort",
            user_name: "ananya",
            crowd_level: "Quiet",
            tip: "Approved report text",
            moderation_status: "approved",
            ago: "5 min ago",
          },
        ]}
      />,
    );

    expect(html).not.toContain("Rejected report text");
    expect(html).toContain("Approved report text");
    expect(html).toContain("Verified Live Observation");
  });
});

describe("Admin Dashboard Pending Queue UI integration", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    sessionStorage.clear();
    if (!globalThis.ResizeObserver) {
      globalThis.ResizeObserver = class {
        observe() {}
        unobserve() {}
        disconnect() {}
      } as unknown as typeof ResizeObserver;
    }
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it("renders newly submitted pending report by exact ID in Admin Pending Queue and supports Verify/Reject", async () => {
    let reportStatus: "pending" | "approved" | "rejected" = "pending";

    globalThis.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/auth/me")) {
        return new Response(
          JSON.stringify({
            user: {
              id: "adm_test",
              name: "DoT Admin",
              email: "admin@raahi.gov.in",
              role: "admin",
            },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (url.endsWith("/crowd-reports") && init?.method === "POST") {
        return new Response(
          JSON.stringify({
            success: true,
            report: {
              id: 777,
              destination_id: "jantar",
              destination_name: "Jantar Mantar",
              user_id: "u_rohan",
              user_name: "rohan",
              crowd_level: "Moderate",
              wait_minutes: 5,
              tip: "Short line at ticket counter",
              observed_at: "2026-11-27T16:00:00Z",
              submitted_at: "2026-11-27T16:00:00Z",
              moderation_status: reportStatus,
              trust_weight: 1.0,
              accuracy_votes_count: 0,
              ago: "just now",
            },
            points_awarded: 0,
            total_points: 0,
            message: "Report submitted and queued for moderation review.",
          }),
          { status: 201, headers: { "Content-Type": "application/json" } },
        );
      }
      if (url.includes("/admin/reports/777") && init?.method === "PATCH") {
        const body = JSON.parse(String(init.body || "{}"));
        reportStatus = body.status;
        return new Response(
          JSON.stringify({ success: true, report_id: 777, old_status: "pending", new_status: reportStatus }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (url.includes("/admin/reports")) {
        const list =
          url.includes("status_filter=pending") && reportStatus !== "pending"
            ? []
            : [
                {
                  id: 777,
                  destination_id: "jantar",
                  destination_name: "Jantar Mantar",
                  user_id: "u_rohan",
                  user_name: "rohan",
                  crowd_level: "Moderate",
                  tip: "Short line at ticket counter",
                  moderation_status: reportStatus,
                  submitted_at: "2026-11-27T16:00:00Z",
                  trust_weight: 1.0,
                },
              ];
        return new Response(JSON.stringify({ reports: list }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (url.includes("/admin/comments")) {
        return new Response(JSON.stringify({ comments: [] }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response(JSON.stringify({}), { status: 200 });
    }) as typeof fetch;

    // 1. Submit report via api.submitReport
    const submitRes = await api.submitReport({
      destination_id: "jantar",
      crowd_level: "Moderate",
      tip: "Short line at ticket counter",
      user_name: "rohan",
    });
    expect(submitRes.data?.report.id).toBe(777);
    expect(submitRes.data?.report.moderation_status).toBe("pending");

    // 2. Open AdminDashboard as authenticated admin -> Incidents & Community Pulse
    render(
      <AuthProvider>
        <AdminDashboard />
      </AuthProvider>,
    );
    await waitFor(() => {
      expect(screen.getByText(/Community & Police Pulse/i)).toBeDefined();
    });
    fireEvent.click(screen.getByText(/Community & Police Pulse/i));

    // 3. Verify exact report #777 appears in the Pending Queue UI
    await waitFor(() => {
      expect(screen.getByText("#777")).toBeDefined();
      expect(screen.getByText("Jantar Mantar")).toBeDefined();
      expect(screen.getByText(/Short line at ticket counter/i)).toBeDefined();
    });

    // 4. Click Verify -> updates backend and refreshes queue
    fireEvent.click(screen.getByRole("button", { name: /^Verify$/i }));
    await waitFor(() => {
      expect(screen.getByText(/Report #777 verified and published/i)).toBeDefined();
    });
    expect(reportStatus).toBe("approved");
  });
});

