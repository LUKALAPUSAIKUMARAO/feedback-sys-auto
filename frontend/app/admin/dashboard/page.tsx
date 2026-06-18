"use client";
import { useEffect, useState } from "react";
import { analyticsApi } from "@/lib/api";
import { formatScore, scoreTierColor, statusColor, tierBadge, cn } from "@/lib/utils";
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, RadarChart, Radar, PolarGrid,
  PolarAngleAxis, PolarRadiusAxis, Cell
} from "recharts";
import {
  TrendingUp, TrendingDown, Users, BookOpen, BarChart2,
  AlertTriangle, Star, MessageSquare, Zap, SendHorizontal, Loader2
} from "lucide-react";
import { toast } from "sonner";

interface DashboardData {
  total_trainers: number;
  total_batches: number;
  total_participants: number;
  total_feedback_responses: number;
  avg_org_health_score: number;
  top_trainers: any[];
  at_risk_trainers: any[];
  recent_batches: any[];
  monthly_trend: any[];
}

function StatCard({ label, value, sub, icon: Icon, trend, color = "blue" }: any) {
  return (
    <div className="stat-card">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">{label}</p>
          <p className="text-2xl font-bold text-slate-900 mt-1.5 tabular-nums">{value}</p>
          {sub && <p className="text-xs text-slate-500 mt-1">{sub}</p>}
        </div>
        <div className={cn(
          "w-9 h-9 rounded-lg flex items-center justify-center",
          color === "blue" && "bg-blue-50",
          color === "green" && "bg-emerald-50",
          color === "amber" && "bg-amber-50",
          color === "purple" && "bg-purple-50",
        )}>
          <Icon className={cn(
            "w-5 h-5",
            color === "blue" && "text-blue-600",
            color === "green" && "text-emerald-600",
            color === "amber" && "text-amber-600",
            color === "purple" && "text-purple-600",
          )} />
        </div>
      </div>
      {trend !== undefined && (
        <div className={cn("flex items-center gap-1 mt-3 text-xs font-medium", trend >= 0 ? "text-emerald-600" : "text-red-500")}>
          {trend >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
          {trend >= 0 ? "+" : ""}{trend.toFixed(1)} vs last month
        </div>
      )}
    </div>
  );
}

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [chatQ, setChatQ] = useState("");
  const [chatAnswer, setChatAnswer] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [chatHistory, setChatHistory] = useState<{ q: string; a: string }[]>([]);

  useEffect(() => {
    analyticsApi.dashboard()
      .then(setData)
      .catch(() => toast.error("Failed to load dashboard"))
      .finally(() => setLoading(false));
  }, []);

  async function handleChat(e: React.FormEvent) {
    e.preventDefault();
    if (!chatQ.trim()) return;
    setChatLoading(true);
    const q = chatQ;
    setChatQ("");
    try {
      const res = await analyticsApi.chat({ question: q, time_range_days: 90 });
      setChatHistory(h => [...h, { q, a: res.answer }]);
      setChatAnswer(res.answer);
    } catch {
      toast.error("Chat query failed");
    } finally {
      setChatLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-6 h-6 text-blue-600 animate-spin" />
      </div>
    );
  }

  const trend = data?.monthly_trend || [];

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Page Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Organization Dashboard</h1>
          <p className="page-subtitle">Live training intelligence overview</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-emerald-50 text-emerald-700 text-xs font-medium rounded-full ring-1 ring-emerald-600/20">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
            Live
          </span>
        </div>
      </div>

      {/* KPI Row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Total Trainers" value={data?.total_trainers ?? 0} icon={Users} color="blue" />
        <StatCard label="Training Batches" value={data?.total_batches ?? 0} icon={BookOpen} color="purple" />
        <StatCard label="Participants" value={data?.total_participants ?? 0} icon={Users} color="green" />
        <StatCard
          label="Org Health Score"
          value={`${formatScore(data?.avg_org_health_score ?? 0)} / 5`}
          sub={`${data?.total_feedback_responses ?? 0} total responses`}
          icon={Star}
          color="amber"
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Monthly Trend */}
        <div className="lg:col-span-2 stat-card">
          <h3 className="text-sm font-semibold text-slate-800 mb-4">Health Score Trend — Last 6 Months</h3>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={trend} margin={{ top: 5, right: 5, bottom: 5, left: -20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="month" tick={{ fontSize: 11, fill: "#94a3b8" }} />
              <YAxis domain={[0, 5]} tick={{ fontSize: 11, fill: "#94a3b8" }} />
              <Tooltip
                contentStyle={{ border: "1px solid #e2e8f0", borderRadius: "8px", fontSize: "12px" }}
                formatter={(v: any) => [Number(v).toFixed(2), "Avg Health Score"]}
              />
              <Line
                type="monotone"
                dataKey="avg_health_score"
                stroke="#2563eb"
                strokeWidth={2}
                dot={{ fill: "#2563eb", r: 3 }}
                activeDot={{ r: 5 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* At-Risk Trainers */}
        <div className="stat-card">
          <div className="flex items-center gap-2 mb-4">
            <AlertTriangle className="w-4 h-4 text-red-500" />
            <h3 className="text-sm font-semibold text-slate-800">At-Risk Trainers</h3>
          </div>
          {!data?.at_risk_trainers?.length ? (
            <p className="text-sm text-slate-500 text-center py-8">No at-risk trainers</p>
          ) : (
            <div className="space-y-3">
              {data.at_risk_trainers.map((t: any) => (
                <div key={t.id} className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-slate-800">{t.name}</p>
                    <p className="text-xs text-slate-500">{t.sessions} sessions</p>
                  </div>
                  <span className={cn("risk-badge", "bg-red-50 text-red-700 ring-red-600/20")}>
                    {formatScore(t.health_score)} / 5
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Tables Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Top Trainers */}
        <div className="stat-card overflow-hidden p-0">
          <div className="px-5 py-4 border-b border-slate-100 flex items-center gap-2">
            <BarChart2 className="w-4 h-4 text-blue-600" />
            <h3 className="text-sm font-semibold text-slate-800">Top Performers</h3>
          </div>
          <table className="w-full data-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Trainer</th>
                <th>Sessions</th>
                <th>Score</th>
              </tr>
            </thead>
            <tbody>
              {data?.top_trainers?.map((t: any, i: number) => (
                <tr key={t.id} className="cursor-pointer" onClick={() => window.location.href = `/admin/trainers/${t.id}`}>
                  <td className="text-slate-400 font-mono text-xs w-8">{i + 1}</td>
                  <td className="font-medium text-slate-900">{t.name}</td>
                  <td className="text-slate-500">{t.sessions}</td>
                  <td>
                    <span className={cn("font-semibold tabular-nums", scoreTierColor(t.health_score))}>
                      {formatScore(t.health_score)}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Recent Batches */}
        <div className="stat-card overflow-hidden p-0">
          <div className="px-5 py-4 border-b border-slate-100">
            <h3 className="text-sm font-semibold text-slate-800">Recent Batches</h3>
          </div>
          <table className="w-full data-table">
            <thead>
              <tr>
                <th>Batch</th>
                <th>Trainer</th>
                <th>Enrolled</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {data?.recent_batches?.map((b: any) => (
                <tr key={b.id}>
                  <td className="font-medium text-slate-900 max-w-[120px] truncate">{b.title}</td>
                  <td className="text-slate-500 text-xs">{b.trainer}</td>
                  <td className="text-slate-500">{b.enrolled}</td>
                  <td>
                    <span className={cn("risk-badge", statusColor(b.status))}>
                      {b.status.replace("_", " ")}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Chat Analytics */}
      <div className="stat-card">
        <div className="flex items-center gap-2 mb-4">
          <Zap className="w-4 h-4 text-blue-600" />
          <h3 className="text-sm font-semibold text-slate-800">Analytics Intelligence Chat</h3>
          <span className="ml-auto text-xs text-slate-400 bg-slate-100 px-2 py-0.5 rounded-full">Powered by Llama 3.3 + RAG</span>
        </div>

        {/* Chat history */}
        {chatHistory.length > 0 && (
          <div className="mb-4 space-y-3 max-h-64 overflow-y-auto">
            {chatHistory.map((item, i) => (
              <div key={i} className="space-y-2">
                <div className="flex justify-end">
                  <div className="bg-blue-600 text-white text-sm rounded-xl rounded-br-sm px-4 py-2.5 max-w-[80%]">
                    {item.q}
                  </div>
                </div>
                <div className="flex justify-start">
                  <div className="bg-slate-100 text-slate-800 text-sm rounded-xl rounded-bl-sm px-4 py-2.5 max-w-[85%] leading-relaxed">
                    {item.a}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {chatHistory.length === 0 && (
          <div className="grid grid-cols-2 gap-2 mb-4">
            {[
              "Why is trainer performance declining this month?",
              "Which training program has the highest satisfaction?",
              "What are the most common participant complaints?",
              "Show me trainers with improving sentiment trends",
            ].map((q) => (
              <button
                key={q}
                onClick={() => setChatQ(q)}
                className="text-left text-xs text-slate-600 bg-slate-50 hover:bg-slate-100 rounded-lg px-3 py-2 border border-slate-200 transition-colors"
              >
                {q}
              </button>
            ))}
          </div>
        )}

        <form onSubmit={handleChat} className="flex gap-2">
          <input
            value={chatQ}
            onChange={(e) => setChatQ(e.target.value)}
            placeholder="Ask anything about training performance…"
            className="flex-1 bg-slate-50 border border-slate-200 rounded-lg px-4 py-2.5 text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-400"
            disabled={chatLoading}
          />
          <button
            type="submit"
            disabled={chatLoading || !chatQ.trim()}
            className="px-4 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white rounded-lg transition-colors"
          >
            {chatLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <SendHorizontal className="w-4 h-4" />}
          </button>
        </form>
      </div>
    </div>
  );
}
