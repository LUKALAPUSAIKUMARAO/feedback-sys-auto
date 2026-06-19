"use client";
import { useEffect, useState } from "react";
import { analyticsApi, trainersApi } from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  BarChart3, Loader2, TrendingUp, TrendingDown,
  Star, Users, Award, Download, RefreshCw
} from "lucide-react";
import { toast } from "sonner";
import Link from "next/link";

function ScoreBadge({ value }: { value: number }) {
  const color =
    value >= 4 ? "text-emerald-600 bg-emerald-50" :
    value >= 3 ? "text-amber-600 bg-amber-50" :
    "text-red-600 bg-red-50";
  return (
    <span className={cn("inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold", color)}>
      <Star className="w-3 h-3" />
      {value.toFixed(2)}
    </span>
  );
}

export default function ReportsPage() {
  const [trainers, setTrainers] = useState<any[]>([]);
  const [histories, setHistories] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);
  const [dashData, setDashData] = useState<any>(null);

  async function load() {
    setLoading(true);
    try {
      const [t, dash] = await Promise.all([
        trainersApi.list({ page_size: 50 }),
        analyticsApi.dashboard(),
      ]);
      setTrainers(t.items || []);
      setDashData(dash);

      // Load trainer histories in parallel
      const histMap: Record<string, any> = {};
      await Promise.all(
        (t.items || []).map(async (tr: any) => {
          try {
            histMap[tr.id] = await analyticsApi.trainer(tr.id);
          } catch { histMap[tr.id] = null; }
        })
      );
      setHistories(histMap);
    } catch {
      toast.error("Failed to load reports");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  function downloadCSV() {
    const rows = [
      ["Trainer", "Employee ID", "Email", "Batches", "Avg Rating", "Responses", "Health Score"],
      ...trainers.map((t) => {
        const h = histories[t.id];
        return [
          t.full_name,
          t.employee_id,
          t.email,
          h?.total_batches ?? 0,
          h?.overall_avg?.toFixed(2) ?? "—",
          h?.total_responses ?? 0,
          h?.health_score?.toFixed(2) ?? "—",
        ];
      }),
    ];
    const csv = rows.map((r) => r.join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "trainer_report.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <Loader2 className="w-6 h-6 text-blue-600 animate-spin" />
    </div>
  );

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="page-title flex items-center gap-2">
            <BarChart3 className="w-6 h-6 text-blue-600" /> Analytics Reports
          </h1>
          <p className="text-sm text-slate-500 mt-1">Performance summary across all trainers and programs</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={load} className="inline-flex items-center gap-2 px-3 py-2 bg-white border border-slate-200 text-slate-600 text-sm rounded-lg hover:bg-slate-50 transition-colors">
            <RefreshCw className="w-3.5 h-3.5" /> Refresh
          </button>
          <button onClick={downloadCSV} className="inline-flex items-center gap-2 px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors">
            <Download className="w-3.5 h-3.5" /> Export CSV
          </button>
        </div>
      </div>

      {/* Org overview */}
      {dashData && (
        <div className="grid grid-cols-4 gap-4">
          {[
            { label: "Total Responses", value: dashData.total_feedback_count ?? 0, icon: Users },
            { label: "Avg Rating", value: (dashData.avg_rating ?? 0).toFixed(2), icon: Star },
            { label: "Avg Health Score", value: (dashData.avg_health_score ?? 0).toFixed(2), icon: Award },
            { label: "Completion Rate", value: `${(dashData.completion_rate ?? 0).toFixed(1)}%`, icon: TrendingUp },
          ].map((kpi) => (
            <div key={kpi.label} className="stat-card text-center">
              <kpi.icon className="w-5 h-5 text-blue-500 mx-auto mb-2" />
              <p className="text-2xl font-bold text-slate-900 tabular-nums">{kpi.value}</p>
              <p className="text-xs text-slate-500 mt-1">{kpi.label}</p>
            </div>
          ))}
        </div>
      )}

      {/* Trainer table */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-card">
        <div className="px-5 py-4 border-b border-slate-100 flex items-center gap-2">
          <BarChart3 className="w-4 h-4 text-slate-400" />
          <h3 className="text-sm font-semibold text-slate-800">Trainer Performance Report</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full data-table">
            <thead>
              <tr>
                <th>Trainer</th>
                <th>Employee ID</th>
                <th>Batches</th>
                <th>Responses</th>
                <th>Avg Rating</th>
                <th>Health Score</th>
                <th>Sentiment</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {trainers.map((t) => {
                const h = histories[t.id];
                return (
                  <tr key={t.id}>
                    <td>
                      <div>
                        <p className="font-medium text-slate-900">{t.full_name}</p>
                        <p className="text-xs text-slate-400">{t.email}</p>
                      </div>
                    </td>
                    <td className="font-mono text-xs text-slate-500">{t.employee_id}</td>
                    <td className="text-center">{h?.total_batches ?? 0}</td>
                    <td className="text-center">{h?.total_responses ?? 0}</td>
                    <td>
                      {h?.overall_avg ? <ScoreBadge value={h.overall_avg} /> : <span className="text-slate-300 text-xs">—</span>}
                    </td>
                    <td>
                      {h?.health_score ? (
                        <div className="flex items-center gap-1.5">
                          <div className="w-16 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                            <div className="h-full bg-blue-500 rounded-full" style={{ width: `${Math.min(h.health_score * 20, 100)}%` }} />
                          </div>
                          <span className="text-xs font-medium text-slate-600">{h.health_score.toFixed(1)}</span>
                        </div>
                      ) : <span className="text-slate-300 text-xs">—</span>}
                    </td>
                    <td>
                      {h?.sentiment_positive != null ? (
                        <div className="flex items-center gap-1">
                          {h.sentiment_positive >= 60 ? (
                            <TrendingUp className="w-3.5 h-3.5 text-emerald-500" />
                          ) : (
                            <TrendingDown className="w-3.5 h-3.5 text-red-400" />
                          )}
                          <span className="text-xs text-slate-600">{h.sentiment_positive.toFixed(0)}% +ve</span>
                        </div>
                      ) : <span className="text-slate-300 text-xs">—</span>}
                    </td>
                    <td>
                      <Link
                        href={`/admin/trainers/${t.id}`}
                        className="text-xs text-blue-600 hover:underline"
                      >
                        View →
                      </Link>
                    </td>
                  </tr>
                );
              })}
              {trainers.length === 0 && (
                <tr>
                  <td colSpan={8} className="text-center text-slate-400 py-8">No trainers found</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
