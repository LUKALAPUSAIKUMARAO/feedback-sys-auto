"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { analyticsApi, trainersApi } from "@/lib/api";
import { formatScore, scoreTierColor, tierBadge, cn, sentimentColor } from "@/lib/utils";
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, BarChart, Bar
} from "recharts";
import { ArrowLeft, AlertTriangle, TrendingUp, TrendingDown, Star, Loader2 } from "lucide-react";
import { toast } from "sonner";

export default function TrainerDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [trainer, setTrainer] = useState<any>(null);
  const [analytics, setAnalytics] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([trainersApi.get(id), analyticsApi.trainer(id)])
      .then(([t, a]) => { setTrainer(t); setAnalytics(a); })
      .catch(() => toast.error("Failed to load trainer details"))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <Loader2 className="w-6 h-6 text-blue-600 animate-spin" />
    </div>
  );

  if (!trainer || !analytics) return <p className="text-slate-500">Trainer not found</p>;

  const radarData = [
    { dim: "Technical", value: analytics.ratings.technical_knowledge },
    { dim: "Communication", value: analytics.ratings.communication },
    { dim: "Engagement", value: analytics.ratings.session_engagement },
    { dim: "Time Mgmt", value: analytics.ratings.time_management },
    { dim: "Practical", value: analytics.ratings.practical_learning },
    { dim: "Content", value: analytics.ratings.content_quality },
  ];

  const sentimentData = [
    { label: "Positive", value: analytics.sentiment.positive, fill: "#10b981" },
    { label: "Neutral", value: analytics.sentiment.neutral, fill: "#94a3b8" },
    { label: "Negative", value: analytics.sentiment.negative, fill: "#ef4444" },
  ];

  const snapshotTrend = (analytics.recent_snapshots || []).map((s: any) => ({
    date: s.date?.slice(0, 10) || "",
    score: s.health_score,
    overall: s.overall_avg,
  })).reverse();

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Back + Header */}
      <div>
        <button onClick={() => router.back()} className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-800 mb-4 transition-colors">
          <ArrowLeft className="w-4 h-4" /> Back to Trainers
        </button>

        <div className="flex items-start justify-between">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-blue-600 to-blue-800 flex items-center justify-center shrink-0">
              <span className="text-white text-xl font-bold">{trainer.full_name.charAt(0)}</span>
            </div>
            <div>
              <h1 className="text-xl font-bold text-slate-900">{trainer.full_name}</h1>
              <p className="text-sm text-slate-500">{trainer.designation} · {trainer.department}</p>
              <div className="flex items-center gap-2 mt-1">
                <span className="text-xs text-slate-400 font-mono">{trainer.employee_id}</span>
                <span className="text-slate-300">·</span>
                <span className="text-xs text-slate-400">{trainer.email}</span>
              </div>
            </div>
          </div>
          <div className="text-right">
            <p className={cn("text-3xl font-bold tabular-nums", scoreTierColor(analytics.overall_health_score))}>
              {formatScore(analytics.overall_health_score)} / 5
            </p>
            <span className={cn("risk-badge mt-1", tierBadge(analytics.recent_snapshots?.[0]?.tier || ""))}>
              {analytics.recent_snapshots?.[0]?.tier || "—"}
            </span>
          </div>
        </div>
      </div>

      {/* Risk Banner */}
      {analytics.risk_flag && (
        <div className="flex items-start gap-3 bg-red-50 border border-red-200 rounded-xl p-4">
          <AlertTriangle className="w-5 h-5 text-red-600 shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-semibold text-red-800">Performance Risk Flag</p>
            <p className="text-sm text-red-700">{analytics.risk_reason}</p>
          </div>
        </div>
      )}

      {/* KPI Row */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: "Total Sessions", value: analytics.total_sessions },
          { label: "Total Responses", value: analytics.total_responses },
          { label: "Avg Rating", value: `${formatScore(analytics.avg_rating)} / 5` },
          { label: "Positive Sentiment", value: `${analytics.sentiment.positive.toFixed(1)}%` },
        ].map((kpi) => (
          <div key={kpi.label} className="stat-card text-center">
            <p className="text-2xl font-bold text-slate-900 tabular-nums">{kpi.value}</p>
            <p className="text-xs text-slate-500 mt-1">{kpi.label}</p>
          </div>
        ))}
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Radar */}
        <div className="stat-card">
          <h3 className="text-sm font-semibold text-slate-800 mb-2">Dimension Scores</h3>
          <ResponsiveContainer width="100%" height={220}>
            <RadarChart data={radarData}>
              <PolarGrid stroke="#e2e8f0" />
              <PolarAngleAxis dataKey="dim" tick={{ fontSize: 10, fill: "#64748b" }} />
              <PolarRadiusAxis domain={[0, 5]} tick={false} />
              <Radar dataKey="value" stroke="#2563eb" fill="#2563eb" fillOpacity={0.15} strokeWidth={2} />
            </RadarChart>
          </ResponsiveContainer>
        </div>

        {/* Trend */}
        <div className="stat-card">
          <h3 className="text-sm font-semibold text-slate-800 mb-2">Health Score Trend</h3>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={snapshotTrend} margin={{ left: -20, right: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#94a3b8" }} />
              <YAxis domain={[0, 5]} tick={{ fontSize: 10, fill: "#94a3b8" }} />
              <Tooltip contentStyle={{ fontSize: "12px", borderRadius: "8px" }} />
              <Line type="monotone" dataKey="score" stroke="#2563eb" strokeWidth={2} dot={{ r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Sentiment */}
        <div className="stat-card">
          <h3 className="text-sm font-semibold text-slate-800 mb-2">Sentiment Distribution</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={sentimentData} margin={{ left: -20, right: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="label" tick={{ fontSize: 11, fill: "#94a3b8" }} />
              <YAxis tick={{ fontSize: 11, fill: "#94a3b8" }} />
              <Tooltip contentStyle={{ fontSize: "12px", borderRadius: "8px" }} formatter={(v) => [`${v}%`]} />
              <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                {sentimentData.map((entry, i) => (
                  <Cell key={i} fill={entry.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Themes + Recommendations */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="stat-card">
          <h3 className="text-sm font-semibold text-slate-800 mb-3">Top Themes from Feedback</h3>
          <div className="flex flex-wrap gap-2">
            {analytics.top_themes?.length ? analytics.top_themes.map((t: string, i: number) => (
              <span key={i} className="px-3 py-1 bg-blue-50 text-blue-700 text-xs font-medium rounded-full ring-1 ring-blue-200">
                {t}
              </span>
            )) : <p className="text-sm text-slate-400">No themes extracted yet</p>}
          </div>
        </div>

        <div className="stat-card">
          <h3 className="text-sm font-semibold text-slate-800 mb-3">AI Recommendations</h3>
          <div className="space-y-3">
            {analytics.recommendations?.length ? analytics.recommendations.map((r: any, i: number) => (
              <div key={i} className="flex gap-3">
                <span className="w-5 h-5 rounded-full bg-blue-600 text-white text-xs flex items-center justify-center font-semibold shrink-0">
                  {i + 1}
                </span>
                <div>
                  <p className="text-sm font-medium text-slate-800">{r.headline || r}</p>
                  {r.detail && <p className="text-xs text-slate-500 mt-0.5">{r.detail}</p>}
                </div>
              </div>
            )) : <p className="text-sm text-slate-400">Recommendations pending pipeline run</p>}
          </div>
        </div>
      </div>
    </div>
  );
}
