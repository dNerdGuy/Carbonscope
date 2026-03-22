import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useReducer, useMemo, useRef, useEffect } from "react";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import Breadcrumbs from "@/components/Breadcrumbs";
import { useRequireAuth } from "@/hooks/useRequireAuth";
import { uploadData, createEstimate } from "@/lib/api";
import { PageSkeleton } from "@/components/Skeleton";
import { StatusMessage } from "@/components/StatusMessage";
import { useEventSource } from "@/hooks/useEventSource";

const CURRENT_YEAR = new Date().getFullYear();

interface UploadState {
  year: number;
  submitting: boolean;
  error: string;
  success: string;
  // Scope 1
  naturalGas: string;
  diesel: string;
  gasoline: string;
  propane: string;
  fleetMiles: string;
  // Scope 2
  electricityKwh: string;
  gridRegion: string;
  steamMmbtu: string;
  // Scope 3
  employeeCount: string;
  revenueUsd: string;
  purchasedGoodsUsd: string;
  businessTravelMiles: string;
  wasteMetricTons: string;
  freightTonMiles: string;
  notes: string;
}

type UploadAction =
  | {
      type: "SET_FIELD";
      field: keyof UploadState;
      value: string | number | boolean;
    }
  | { type: "SET_SUBMITTING"; value: boolean }
  | { type: "SET_ERROR"; value: string }
  | { type: "SET_SUCCESS"; value: string };

const initialState: UploadState = {
  year: CURRENT_YEAR - 1,
  submitting: false,
  error: "",
  success: "",
  naturalGas: "",
  diesel: "",
  gasoline: "",
  propane: "",
  fleetMiles: "",
  electricityKwh: "",
  gridRegion: "",
  steamMmbtu: "",
  employeeCount: "",
  revenueUsd: "",
  purchasedGoodsUsd: "",
  businessTravelMiles: "",
  wasteMetricTons: "",
  freightTonMiles: "",
  notes: "",
};

function uploadReducer(state: UploadState, action: UploadAction): UploadState {
  switch (action.type) {
    case "SET_FIELD":
      return { ...state, [action.field]: action.value };
    case "SET_SUBMITTING":
      return { ...state, submitting: action.value };
    case "SET_ERROR":
      return { ...state, error: action.value, success: "" };
    case "SET_SUCCESS":
      return { ...state, success: action.value, error: "" };
    default:
      return state;
  }
}

export const Route = createFileRoute("/upload")({ component: UploadPage });

function UploadPage() {
  useDocumentTitle("Upload Data");
  const { user, loading } = useRequireAuth();
  const navigate = useNavigate();
  const [state, dispatch] = useReducer(uploadReducer, initialState);

  const setField = (field: keyof UploadState) => (value: string) =>
    dispatch({ type: "SET_FIELD", field, value });

  // Redirect to /reports when a background subnet estimation completes
  const mountedRef = useRef(true);
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);
  const sseHandlers = useMemo(
    () => ({
      report_ready: () => {
        if (mountedRef.current) navigate({ to: "/reports" });
      },
    }),
    [navigate],
  );
  useEventSource(sseHandlers, !!user);

  if (loading) return <PageSkeleton />;
  if (!user) return null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    dispatch({ type: "SET_ERROR", value: "" });
    dispatch({ type: "SET_SUBMITTING", value: true });
    try {
      const provided_data: Record<string, unknown> = {};
      const addNum = (key: string, val: string) => {
        const n = parseFloat(val);
        if (!isNaN(n) && n > 0) provided_data[key] = n;
      };

      addNum("natural_gas_therms", state.naturalGas);
      addNum("diesel_gallons", state.diesel);
      addNum("gasoline_gallons", state.gasoline);
      addNum("propane_gallons", state.propane);
      addNum("fleet_miles", state.fleetMiles);
      addNum("electricity_kwh", state.electricityKwh);
      if (state.gridRegion) provided_data["grid_region"] = state.gridRegion;
      addNum("steam_mmbtu", state.steamMmbtu);
      addNum("employee_count", state.employeeCount);
      addNum("revenue_usd", state.revenueUsd);
      addNum("purchased_goods_usd", state.purchasedGoodsUsd);
      addNum("business_travel_miles", state.businessTravelMiles);
      addNum("waste_metric_tons", state.wasteMetricTons);
      addNum("freight_ton_miles", state.freightTonMiles);

      const upload = await uploadData({
        year: state.year,
        provided_data,
        notes: state.notes || undefined,
      });

      // Trigger estimation
      const report = await createEstimate(upload.id);
      dispatch({
        type: "SET_SUCCESS",
        value: `Estimation complete! Total: ${report.total.toLocaleString()} tCO₂e (${(report.confidence * 100).toFixed(0)}% confidence)`,
      });
    } catch (err: unknown) {
      dispatch({
        type: "SET_ERROR",
        value: err instanceof Error ? err.message : "Upload failed",
      });
    } finally {
      dispatch({ type: "SET_SUBMITTING", value: false });
    }
  }

  return (
    <div className="max-w-6xl mx-auto p-8 animate-fade-up space-y-8">
      <Breadcrumbs
        items={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Upload Data" },
        ]}
      />
      <h1 className="text-3xl font-extrabold tracking-tight mb-2">
        Upload Operational Data
      </h1>
      <p className="text-[var(--muted)] text-base font-medium mb-8 max-w-2xl">
        Enter your company&apos;s operational data. CarbonScope will estimate
        emissions across all three scopes.
      </p>

      <form
        onSubmit={handleSubmit}
        className="space-y-8"
        aria-label="Upload operational data"
      >
        {state.error && <StatusMessage message={state.error} variant="error" />}
        {state.success && (
          <div className="text-sm text-[var(--primary)] bg-[var(--primary)]/10 rounded-md p-3">
            {state.success}{" "}
            <button
              type="button"
              onClick={() => navigate({ to: "/reports" })}
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
            value={state.year}
            onChange={(e) =>
              dispatch({
                type: "SET_FIELD",
                field: "year",
                value: Number(e.target.value),
              })
            }
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
          <legend className="text-lg font-semibold mb-4">
            Scope 1 — Direct Emissions
          </legend>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <NumField
              id="natural-gas"
              label="Natural Gas (therms)"
              value={state.naturalGas}
              onChange={setField("naturalGas")}
            />
            <NumField
              id="diesel"
              label="Diesel (gallons)"
              value={state.diesel}
              onChange={setField("diesel")}
            />
            <NumField
              id="gasoline"
              label="Gasoline (gallons)"
              value={state.gasoline}
              onChange={setField("gasoline")}
            />
            <NumField
              id="propane"
              label="Propane (gallons)"
              value={state.propane}
              onChange={setField("propane")}
            />
            <NumField
              id="fleet-miles"
              label="Fleet Vehicle Miles"
              value={state.fleetMiles}
              onChange={setField("fleetMiles")}
            />
          </div>
        </fieldset>

        {/* Scope 2: Indirect energy */}
        <fieldset className="card space-y-4">
          <legend className="text-lg font-semibold mb-4">
            Scope 2 — Purchased Energy
          </legend>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <NumField
              id="electricity-kwh"
              label="Electricity (kWh)"
              value={state.electricityKwh}
              onChange={setField("electricityKwh")}
            />
            <div>
              <label htmlFor="grid-region" className="label">
                Grid Region (e.g. RFCW, CAMX)
              </label>
              <input
                id="grid-region"
                type="text"
                className="input"
                value={state.gridRegion}
                onChange={(e) =>
                  dispatch({
                    type: "SET_FIELD",
                    field: "gridRegion",
                    value: e.target.value,
                  })
                }
                placeholder="Optional"
              />
            </div>
            <NumField
              id="steam-mmbtu"
              label="Steam / Heating (MMBtu)"
              value={state.steamMmbtu}
              onChange={setField("steamMmbtu")}
            />
          </div>
        </fieldset>

        {/* Scope 3 / context */}
        <fieldset className="card space-y-4">
          <legend className="text-lg font-semibold mb-4">
            Scope 3 & Context
          </legend>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <NumField
              id="employee-count"
              label="Employee Count"
              value={state.employeeCount}
              onChange={setField("employeeCount")}
            />
            <NumField
              id="revenue-usd"
              label="Revenue (USD)"
              value={state.revenueUsd}
              onChange={setField("revenueUsd")}
            />
            <NumField
              id="purchased-goods-usd"
              label="Purchased Goods & Services (USD)"
              value={state.purchasedGoodsUsd}
              onChange={setField("purchasedGoodsUsd")}
            />
            <NumField
              id="business-travel-miles"
              label="Business Travel (miles)"
              value={state.businessTravelMiles}
              onChange={setField("businessTravelMiles")}
            />
            <NumField
              id="waste-metric-tons"
              label="Waste Generated (metric tons)"
              value={state.wasteMetricTons}
              onChange={setField("wasteMetricTons")}
            />
            <NumField
              id="freight-ton-miles"
              label="Freight Transport (ton-miles)"
              value={state.freightTonMiles}
              onChange={setField("freightTonMiles")}
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
            value={state.notes}
            onChange={(e) =>
              dispatch({
                type: "SET_FIELD",
                field: "notes",
                value: e.target.value,
              })
            }
            placeholder="Any additional context about data quality, methodology notes, etc."
          />
        </div>

        <button
          type="submit"
          className="btn-primary"
          disabled={state.submitting}
        >
          {state.submitting ? (
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
