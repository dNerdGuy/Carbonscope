"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import Breadcrumbs from "@/components/Breadcrumbs";
import { useAuth } from "@/lib/auth-context";
import { uploadData, createEstimate } from "@/lib/api";
import { PageSkeleton } from "@/components/Skeleton";

const CURRENT_YEAR = new Date().getFullYear();

export default function UploadPage() {
  useDocumentTitle("Upload Data");
  const { user, loading } = useAuth();
  const router = useRouter();
  const [year, setYear] = useState(CURRENT_YEAR - 1);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  // Scope 1 fields
  const [naturalGas, setNaturalGas] = useState("");
  const [diesel, setDiesel] = useState("");
  const [gasoline, setGasoline] = useState("");
  const [propane, setPropane] = useState("");
  const [fleetMiles, setFleetMiles] = useState("");

  // Scope 2 fields
  const [electricityKwh, setElectricityKwh] = useState("");
  const [gridRegion, setGridRegion] = useState("");
  const [steamMmbtu, setSteamMmbtu] = useState("");

  // Scope 3 / context fields
  const [employeeCount, setEmployeeCount] = useState("");
  const [revenueUsd, setRevenueUsd] = useState("");
  const [purchasedGoodsUsd, setPurchasedGoodsUsd] = useState("");
  const [businessTravelMiles, setBusinessTravelMiles] = useState("");
  const [wasteMetricTons, setWasteMetricTons] = useState("");
  const [freightTonMiles, setFreightTonMiles] = useState("");

  const [notes, setNotes] = useState("");

  if (loading) return <PageSkeleton />;

  if (!loading && !user) {
    router.replace("/login");
    return null;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSuccess("");
    setSubmitting(true);
    try {
      const provided_data: Record<string, unknown> = {};
      const addNum = (key: string, val: string) => {
        const n = parseFloat(val);
        if (!isNaN(n) && n > 0) provided_data[key] = n;
      };

      addNum("natural_gas_therms", naturalGas);
      addNum("diesel_gallons", diesel);
      addNum("gasoline_gallons", gasoline);
      addNum("propane_gallons", propane);
      addNum("fleet_miles", fleetMiles);
      addNum("electricity_kwh", electricityKwh);
      if (gridRegion) provided_data["grid_region"] = gridRegion;
      addNum("steam_mmbtu", steamMmbtu);
      addNum("employee_count", employeeCount);
      addNum("revenue_usd", revenueUsd);
      addNum("purchased_goods_usd", purchasedGoodsUsd);
      addNum("business_travel_miles", businessTravelMiles);
      addNum("waste_metric_tons", wasteMetricTons);
      addNum("freight_ton_miles", freightTonMiles);

      const upload = await uploadData({
        year,
        provided_data,
        notes: notes || undefined,
      });

      // Trigger estimation
      const report = await createEstimate(upload.id);
      setSuccess(
        `Estimation complete! Total: ${report.total.toLocaleString()} tCO₂e (${(report.confidence * 100).toFixed(0)}% confidence)`,
      );
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-3xl mx-auto p-8">
      <Breadcrumbs
        items={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Upload Data" },
        ]}
      />
      <h1 className="text-2xl font-bold mb-2">Upload Operational Data</h1>
      <p className="text-[var(--muted)] mb-8">
        Enter your company&apos;s operational data. CarbonScope will estimate
        emissions across all three scopes.
      </p>

      <form onSubmit={handleSubmit} className="space-y-8">
        {error && (
          <div className="text-sm text-[var(--danger)] bg-[var(--danger)]/10 rounded-md p-3">
            {error}
          </div>
        )}
        {success && (
          <div className="text-sm text-[var(--primary)] bg-[var(--primary)]/10 rounded-md p-3">
            {success}{" "}
            <button
              type="button"
              onClick={() => router.push("/reports")}
              className="underline ml-2"
            >
              View Reports →
            </button>
          </div>
        )}

        {/* Year selector */}
        <div>
          <label htmlFor="reporting-year" className="label">
            Reporting Year
          </label>
          <select
            id="reporting-year"
            className="input w-40"
            value={year}
            onChange={(e) => setYear(Number(e.target.value))}
          >
            {Array.from(
              { length: CURRENT_YEAR - 2000 + 1 },
              (_, i) => CURRENT_YEAR - i,
            ).map((y) => (
              <option key={y} value={y}>
                {y}
              </option>
            ))}
          </select>
        </div>

        {/* Scope 1: Direct emissions */}
        <fieldset className="card space-y-4">
          <legend
            className="text-lg font-semibold"
            style={{ color: "var(--scope1)" }}
          >
            Scope 1 — Direct Emissions
          </legend>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <NumField
              id="natural-gas"
              label="Natural Gas (therms)"
              value={naturalGas}
              onChange={setNaturalGas}
            />
            <NumField
              id="diesel"
              label="Diesel (gallons)"
              value={diesel}
              onChange={setDiesel}
            />
            <NumField
              id="gasoline"
              label="Gasoline (gallons)"
              value={gasoline}
              onChange={setGasoline}
            />
            <NumField
              id="propane"
              label="Propane (gallons)"
              value={propane}
              onChange={setPropane}
            />
            <NumField
              id="fleet-miles"
              label="Fleet Vehicle Miles"
              value={fleetMiles}
              onChange={setFleetMiles}
            />
          </div>
        </fieldset>

        {/* Scope 2: Indirect energy */}
        <fieldset className="card space-y-4">
          <legend
            className="text-lg font-semibold"
            style={{ color: "var(--scope2)" }}
          >
            Scope 2 — Purchased Energy
          </legend>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <NumField
              id="electricity-kwh"
              label="Electricity (kWh)"
              value={electricityKwh}
              onChange={setElectricityKwh}
            />
            <div>
              <label htmlFor="grid-region" className="label">
                Grid Region (e.g. RFCW, CAMX)
              </label>
              <input
                id="grid-region"
                type="text"
                className="input"
                value={gridRegion}
                onChange={(e) => setGridRegion(e.target.value)}
                placeholder="Optional"
              />
            </div>
            <NumField
              id="steam-mmbtu"
              label="Steam / Heating (MMBtu)"
              value={steamMmbtu}
              onChange={setSteamMmbtu}
            />
          </div>
        </fieldset>

        {/* Scope 3 / context */}
        <fieldset className="card space-y-4">
          <legend
            className="text-lg font-semibold"
            style={{ color: "var(--scope3)" }}
          >
            Scope 3 & Context
          </legend>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <NumField
              id="employee-count"
              label="Employee Count"
              value={employeeCount}
              onChange={setEmployeeCount}
            />
            <NumField
              id="revenue-usd"
              label="Revenue (USD)"
              value={revenueUsd}
              onChange={setRevenueUsd}
            />
            <NumField
              id="purchased-goods-usd"
              label="Purchased Goods & Services (USD)"
              value={purchasedGoodsUsd}
              onChange={setPurchasedGoodsUsd}
            />
            <NumField
              id="business-travel-miles"
              label="Business Travel (miles)"
              value={businessTravelMiles}
              onChange={setBusinessTravelMiles}
            />
            <NumField
              id="waste-metric-tons"
              label="Waste Generated (metric tons)"
              value={wasteMetricTons}
              onChange={setWasteMetricTons}
            />
            <NumField
              id="freight-ton-miles"
              label="Freight Transport (ton-miles)"
              value={freightTonMiles}
              onChange={setFreightTonMiles}
            />
          </div>
        </fieldset>

        {/* Notes */}
        <div>
          <label htmlFor="notes" className="label">
            Notes (optional)
          </label>
          <textarea
            id="notes"
            className="input min-h-[80px]"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Any additional context about data quality, methodology notes, etc."
          />
        </div>

        <button type="submit" className="btn-primary" disabled={submitting}>
          {submitting ? (
            <span className="inline-flex items-center gap-2">
              <svg
                className="animate-spin h-4 w-4"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                />
              </svg>
              Estimating emissions…
            </span>
          ) : (
            "Upload & Estimate"
          )}
        </button>
      </form>
    </div>
  );
}

function NumField({
  label,
  value,
  onChange,
  id,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  id: string;
}) {
  return (
    <div>
      <label htmlFor={id} className="label">
        {label}
      </label>
      <input
        id={id}
        type="number"
        className="input"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        min={0}
        step="any"
        placeholder="0"
      />
    </div>
  );
}
