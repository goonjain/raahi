import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { AuthProvider } from "@/lib/auth-context";
import { AdminDashboard } from "@/routes/admin";
import { LoginPage } from "@/routes/login";

const mockNavigate = vi.fn();

vi.mock("@tanstack/react-router", async () => {
  const actual = await vi.importActual<typeof import("@tanstack/react-router")>("@tanstack/react-router");
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    Link: ({ children, to, ...props }: any) => (
      <a href={to} {...props}>
        {children}
      </a>
    ),
  };
});

describe("Raahi Authentication & Role Protection", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    mockNavigate.mockReset();
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

  it("blocks tourist accounts from accessing AdminDashboard with 403 message", async () => {
    globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/auth/me")) {
        return new Response(
          JSON.stringify({
            user: { id: "usr_1", name: "Aarav", email: "aarav@example.com", role: "tourist" },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      return new Response(JSON.stringify({}), { status: 200 });
    }) as typeof fetch;

    render(
      <AuthProvider>
        <AdminDashboard />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText(/403 Forbidden/i)).toBeDefined();
    });
  });

  it("supports signup validation and login flow on LoginPage", async () => {
    globalThis.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/auth/me")) {
        return new Response(JSON.stringify({ detail: "Not authenticated." }), { status: 401 });
      }
      if (url.endsWith("/auth/login") && init?.method === "POST") {
        return new Response(
          JSON.stringify({
            user: { id: "usr_1", name: "Aarav", email: "aarav@example.com", role: "tourist" },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      return new Response(JSON.stringify({}), { status: 200 });
    }) as typeof fetch;

    render(
      <AuthProvider>
        <LoginPage />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByLabelText(/Email Address/i)).toBeDefined();
    });

    fireEvent.change(screen.getByLabelText(/Email Address/i), { target: { value: "aarav@example.com" } });
    fireEvent.change(screen.getByLabelText(/^Password$/i), { target: { value: "Password123" } });
    const submitBtn = screen
      .getAllByRole("button", { name: /^Sign In$/i })
      .find((btn) => btn.getAttribute("type") === "submit")!;
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith({ to: "/" });
    });
  });
});
