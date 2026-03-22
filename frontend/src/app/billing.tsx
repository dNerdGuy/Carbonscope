import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useRequireAuth } from "@/hooks/useRequireAuth";
import {
  getSubscription,
  getCredits,
  listPlans,
  changePlan,
  type SubscriptionOut,
  type CreditBalanceOut,
  type PlanLimits,
  ApiError,
} from "@/lib/api";
import { CardSkeleton } from "@/components/Skeleton";
import ConfirmDialog from "@/components/ConfirmDialog";
import { useToast } from "@/components/Toast";
import { ErrorCard } from "@/components/ErrorCard";
import { StatusMessage } from "@/components/StatusMessage";
import Breadcrumbs from "@/components/Breadcrumbs";

export const Route = createFileRoute("/billing")({ component: BillingPage });

function BillingPage() {
  useDocumentTitle("Billing");
  const { user, loading } = useRequireAuth();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [error, setError] = useState("");
  const [changing, setChanging] = useState(false);
  const [pendingPlan, setPendingPlan] = useState<string | null>(null);

  const subQuery = useQuery<SubscriptionOut>({
    queryKey: ["billing-subscription", user?.company_id],
    queryFn: () => getSubscription(),
    enabled: !!user && !loading,
  });

  const creditsQuery = useQuery<CreditBalanceOut>({
    queryKey: ["billing-credits", user?.company_id],
    queryFn: () => getCredits(),
    enabled: !!user && !loading,
  });

  const plansQuery = useQuery<Record<string, PlanLimits>>({
    queryKey: ["billing-plans"],
    queryFn: () => listPlans(),
    enabled: !!user && !loading,
  });

  const sub = subQuery.data ?? null;
  const credits = creditsQuery.data ?? null;
  const plans = plansQuery.data ?? null;

  // Surface errors from any of the billing queries
  useEffect(() => {
    const failCount = [subQuery, creditsQuery, plansQuery].filter(
      (q) => q.isError,
    ).length;
    if (failCount > 0) setError("Some billing data failed to load");
  }, [subQuery.isError, creditsQuery.isError, plansQuery.isError]);

  async function handleChangePlan(plan: string) {
    setChanging(true);
    setError("");
    setPendingPlan(null);
    try {
      await changePlan(plan);
      await queryClient.invalidateQueries({
        queryKey: ["billing-subscription"],
      });
      await queryClient.invalidateQueries({ queryKey: ["billing-credits"] });
      toast(`Plan changed to ${plan}`, "success");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to change plan");
    } finally {
      setChanging(false);
    }
  }

  if (loading || (subQuery.isLoading && !error)) {
    return (
      <div className="max-w-4xl mx-auto p-8 space-y-6">
        <CardSkeleton />
        <CardSkeleton />
      </div>
    );
  }

  if (error && !sub) {
    return (
      <div className="max-w-5xl mx-auto p-8">
        <ErrorCard
          message={error}
          onRetry={() => {
            subQuery.refetch();
            creditsQuery.refetch();
            plansQuery.refetch();
          }}
        />
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto p-8 space-y-8">
      <Breadcrumbs
        items={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Billing" },
        ]}
      />
      <div>
        <h1 className="text-2xl font-bold">Billing & Subscription</h1>
        <p className="text-[var(--muted)]">
          Manage your plan, view credits, and compare tiers.
        </p>
      </div>

      {error && <StatusMessage message={error} variant="error" />}

      {/* Current plan & credits */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="card p-6">
          <p className="text-sm text-[var(--muted)]">Current Plan</p>
          <p className="text-2xl font-bold capitalize mt-1">
            {sub?.plan ?? "—"}
          </p>
          <p className="text-xs text-[var(--muted)] mt-1">
            Status: {sub?.status}
          </p>
        </div>
        <div className="card p-6">
          <p className="text-sm text-[var(--muted)]">Credit Balance</p>
          <p className="text-2xl font-bold mt-1">
            {credits?.balance?.toLocaleString() ?? "—"}
          </p>
          <p className="text-xs text-[var(--muted)] mt-1">credits remaining</p>
        </div>
        <div className="card p-6">
          <p className="text-sm text-[var(--muted)]">Monthly Allowance</p>
          <p className="text-2xl font-bold mt-1">
            {plans && sub
              ? plans[sub.plan]?.monthly_credits.toLocaleString()
              : "—"}
          </p>
          <p className="text-xs text-[var(--muted)] mt-1">credits / month</p>
        </div>
      </div>

      {/* Plans comparison */}
      {plans && (
        <div>
          <h2 className="text-lg font-semibold mb-4">Available Plans</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {(["free", "pro", "enterprise"] as const).map((planKey) => {
              const p = plans[planKey];
              if (!p) return null;
              const isCurrent = sub?.plan === planKey;
              return (
                <div
                  key={planKey}
                  className={`card p-6 flex flex-col justify-between ${isCurrent ? "ring-2 ring-[var(--primary)]" : ""}`}
                >
                  <div>
                    <h3 className="text-lg font-bold capitalize">{planKey}</h3>
                    <p className="text-2xl font-bold mt-2">
                      ${p.price_usd}
                      <span className="text-sm font-normal text-[var(--muted)]">
                        /mo
                      </span>
                    </p>
                    <ul className="mt-4 space-y-2 text-sm">
                      <li>
                        {p.monthly_credits.toLocaleString()} credits/month
                      </li>
                      <li>
                        {p.max_reports_per_month === -1
                          ? "Unlimited"
                          : p.max_reports_per_month}{" "}
                        reports
                      </li>
                      <li>
                        {p.max_scenarios === -1 ? "Unlimited" : p.max_scenarios}{" "}
                        scenarios
                      </li>
                      <li>PDF Export: {p.pdf_export ? "✓" : "✗"}</li>
                      <li>Supply Chain: {p.supply_chain ? "✓" : "✗"}</li>
                      <li>Marketplace: {p.marketplace ? "✓" : "✗"}</li>
                      <li>Webhooks: {p.webhooks ? "✓" : "✗"}</li>
                    </ul>
                  </div>
                  <button
                    className={`mt-6 w-full py-2 rounded-md text-sm font-medium transition-colors ${
                      isCurrent
                        ? "bg-[var(--card-border)] text-[var(--muted)] cursor-default"
                        : "btn-primary"
                    }`}
                    disabled={isCurrent || changing}
                    onClick={() => setPendingPlan(planKey)}
                  >
                    {isCurrent
                      ? "Current Plan"
                      : changing
                        ? "Changing..."
                        : `Switch to ${planKey}`}
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Credit costs reference */}
      <div className="card p-6">
        <h2 className="text-lg font-semibold mb-3">Credit Costs</h2>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-sm">
          {[
            { op: "Estimation", cost: 10 },
            { op: "PDF Export", cost: 5 },
            { op: "Questionnaire Extract", cost: 5 },
            { op: "Scenario Compute", cost: 3 },
            { op: "Marketplace Purchase", cost: 0 },
          ].map((item) => (
            <div
              key={item.op}
              className="text-center p-3 rounded-md bg-[var(--background)]"
            >
              <p className="font-medium">{item.op}</p>
              <p className="text-[var(--muted)]">
                {item.cost === 0 ? "Listing price" : `${item.cost} credits`}
              </p>
            </div>
          ))}
        </div>
      </div>

      <ConfirmDialog
        open={!!pendingPlan}
        title="Change Plan"
        message={`Are you sure you want to switch to the ${pendingPlan} plan? Feature access may change.`}
        confirmLabel="Switch Plan"
        onConfirm={() => pendingPlan && handleChangePlan(pendingPlan)}
        onCancel={() => setPendingPlan(null)}
      />
    </div>
  );
}
