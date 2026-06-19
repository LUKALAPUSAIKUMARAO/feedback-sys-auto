"use client";
import { useEffect, useState } from "react";
import { analyticsApi } from "@/lib/api";
import { HeartPulse, Loader2, CheckCircle, XCircle, AlertTriangle, RefreshCw, Database, Cpu, Mail, Zap, Activity } from "lucide-react";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

function StatusIcon({ status }: { status: string }) {
  if (status === "ok") return <CheckCircle className="w-5 h-5 text-emerald-500" />;
  if (status === "warning") return <AlertTriangle className="w-5 h-5 text-amber-500" />;
  return <XCircle className="w-5 h-5 text-red-500" />;
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    ok: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
    warning: "bg-amber-50 text-amber-700 ring-amber-600/20",
    error: "bg-red-50 text-red-700 ring-red-600/20",
  };
  const key = status?.startsWith("ok") ? "ok" : status?.startsWith("warning") || status === "not configured" ? "warning" : "error";
  return (
    <span className={cn("inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold ring-1 ring-inset", map[key] || map.warning)}>
      {status}
    </span>
  );
}

export default function HealthPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [lastChecked, setLastChecked] = useState<Date | null>(null);

  async function load() {
    setLoading(true);
    try {
      const d = await analyticsApi.healthStatus();
      setData(d);
      setLastChecked(new Date());
    } catch {
      toast.error("Failed to fetch system status");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  const serviceIcons: Record<string, any> = {
    database: Database,
    cache: Activity,
    ai_pipeline: Zap,
    email: Mail,
  };

  const serviceLabels: Record<string, string> = {
    database: "Database",
    cache: "Cache / Redis",
    ai_pipeline: "AI Pipeline (GROQ)",
    email: "Email Service",
  };

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="page-title flex items-center gap-2">
            <HeartPulse className="w-6 h-6 text-blue-600" /> System Health
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Real-time status of all platform subsystems
            {lastChecked && (
              <span className="ml-2 text-slate-400">· Last checked {lastChecked.toLocaleTimeString()}</span>
            )}
          </p>
        </div>
        <button
          onClick={load}
          disabled={loading}
          className="inline-flex items-center gap-2 px-3 py-2 bg-white border border-slate-200 text-slate-600 text-sm rounded-lg hover:bg-slate-50 transition-colors disabled:opacity-50"
        >
          <RefreshCw className={cn("w-3.5 h-3.5", loading && "animate-spin")} />
          Refresh
        </button>
      </div>

      {loading && !data ? (
        <div className="flex items-center justify-center h-64">
          <Loader2 className="w-6 h-6 text-blue-600 animate-spin" />
        </div>
      ) : data ? (
        <>
          {/* Overall status banner */}
          <div className={cn(
            "rounded-xl border px-6 py-4 flex items-center gap-4",
            data.overall === "healthy"
              ? "bg-emerald-50 border-emerald-200"
              : "bg-amber-50 border-amber-200"
          )}>
            <div className={cn(
              "w-12 h-12 rounded-full flex items-center justify-center shrink-0",
              data.overall === "healthy" ? "bg-emerald-100" : "bg-amber-100"
            )}>
              <HeartPulse className={cn("w-6 h-6", data.overall === "healthy" ? "text-emerald-600" : "text-amber-600")} />
            </div>
            <div>
              <p className={cn("font-semibold text-lg", data.overall === "healthy" ? "text-emerald-800" : "text-amber-800")}>
                Platform {data.overall === "healthy" ? "Healthy" : "Degraded"}
              </p>
              <p className="text-sm text-slate-500 mt-0.5">
                Version {data.version} · All core services operational
              </p>
            </div>
          </div>

          {/* Services grid */}
          <div className="grid grid-cols-2 gap-4">
            {Object.entries(data.services || {}).map(([key, svc]: [string, any]) => {
              const Icon = serviceIcons[key] || Cpu;
              return (
                <div key={key} className="bg-white rounded-xl border border-slate-200 p-5 shadow-card">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 rounded-lg bg-slate-100 flex items-center justify-center">
                        <Icon className="w-4.5 h-4.5 text-slate-600" />
                      </div>
                      <div>
                        <p className="font-medium text-slate-900 text-sm">{serviceLabels[key] || key}</p>
                        <p className="text-xs text-slate-400 mt-0.5">{svc.type || svc.model || svc.provider || ""}</p>
                      </div>
                    </div>
                    <StatusIcon status={svc.status?.startsWith("ok") ? "ok" : svc.status === "warning" ? "warning" : svc.status === "not configured" ? "warning" : "ok"} />
                  </div>
                  <StatusBadge status={svc.status} />
                </div>
              );
            })}
          </div>

          {/* Stats */}
          <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-card">
            <h3 className="text-sm font-semibold text-slate-800 mb-4">Platform Statistics</h3>
            <div className="grid grid-cols-3 gap-6">
              {[
                { label: "Total Trainers", value: data.stats?.trainers ?? 0 },
                { label: "Training Batches", value: data.stats?.batches ?? 0 },
                { label: "Feedback Responses", value: data.stats?.feedback_responses ?? 0 },
              ].map((s) => (
                <div key={s.label} className="text-center">
                  <p className="text-3xl font-bold text-slate-900 tabular-nums">{s.value}</p>
                  <p className="text-xs text-slate-500 mt-1">{s.label}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Last pipeline run */}
          {data.last_pipeline_run?.id && (
            <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-card">
              <h3 className="text-sm font-semibold text-slate-800 mb-3">Last AI Pipeline Run</h3>
              <div className="flex items-center gap-4">
                <StatusBadge status={data.last_pipeline_run.status || "unknown"} />
                <span className="text-xs text-slate-400">
                  Run ID: <span className="font-mono">{data.last_pipeline_run.id}</span>
                </span>
                {data.last_pipeline_run.created_at && (
                  <span className="text-xs text-slate-400">
                    at {new Date(data.last_pipeline_run.created_at).toLocaleString()}
                  </span>
                )}
              </div>
            </div>
          )}
        </>
      ) : null}
    </div>
  );
}
