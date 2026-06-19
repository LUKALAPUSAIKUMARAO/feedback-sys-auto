"use client";
import { useEffect, useState } from "react";
import { analyticsApi, batchesApi } from "@/lib/api";
import { formatDateTime, statusColor, cn } from "@/lib/utils";
import {
  Send, ChevronRight, Loader2, CheckCircle, Users, Mail,
  Megaphone, Zap, RefreshCw
} from "lucide-react";
import { toast } from "sonner";
import Link from "next/link";

export default function CampaignsPage() {
  const [campaigns, setCampaigns] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [sendingId, setSendingId] = useState<string | null>(null);
  const [triggeringId, setTriggeringId] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try {
      const data = await analyticsApi.campaigns();
      setCampaigns(data);
    } catch {
      toast.error("Failed to load campaigns");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function handleSendLinks(batchId: string) {
    setSendingId(batchId);
    try {
      const res = await batchesApi.sendFeedbackLinks(batchId);
      toast.success(`${res.sent} feedback link${res.sent !== 1 ? "s" : ""} sent`);
      load();
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Failed to send links");
    } finally {
      setSendingId(null);
    }
  }

  async function handleRunAI(batchId: string) {
    setTriggeringId(batchId);
    try {
      await analyticsApi.triggerPipeline({ batch_id: batchId, force: false });
      toast.success("AI analysis started in background");
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Failed to trigger analysis");
    } finally {
      setTriggeringId(null);
    }
  }

  const totalEnrolled = campaigns.reduce((s, c) => s + c.enrolled, 0);
  const totalLinksSent = campaigns.reduce((s, c) => s + c.links_sent, 0);
  const totalSubmitted = campaigns.reduce((s, c) => s + c.submitted, 0);
  const active = campaigns.filter((c) => ["ongoing", "survey_open", "scheduled"].includes(c.status)).length;

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="page-title flex items-center gap-2">
            <Megaphone className="w-6 h-6 text-blue-600" /> Feedback Campaigns
          </h1>
          <p className="text-sm text-slate-500 mt-1">Manage and track feedback collection across all training batches</p>
        </div>
        <button
          onClick={load}
          className="inline-flex items-center gap-2 px-3 py-2 bg-white border border-slate-200 text-slate-600 text-sm rounded-lg hover:bg-slate-50 transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" /> Refresh
        </button>
      </div>

      {/* Summary KPIs */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: "Total Campaigns", value: campaigns.length, color: "text-slate-900" },
          { label: "Active", value: active, color: "text-blue-600" },
          { label: "Links Sent", value: totalLinksSent, color: "text-indigo-600" },
          { label: "Responses", value: totalSubmitted, color: "text-emerald-600" },
        ].map((kpi) => (
          <div key={kpi.label} className="stat-card text-center">
            <p className={cn("text-2xl font-bold tabular-nums", kpi.color)}>{kpi.value}</p>
            <p className="text-xs text-slate-500 mt-1">{kpi.label}</p>
          </div>
        ))}
      </div>

      {/* Campaign list */}
      {loading ? (
        <div className="flex items-center justify-center h-48">
          <Loader2 className="w-6 h-6 text-blue-600 animate-spin" />
        </div>
      ) : (
        <div className="space-y-3">
          {campaigns.map((c) => (
            <div key={c.batch_id} className="bg-white rounded-xl border border-slate-200 p-5 shadow-card hover:border-slate-300 transition-colors">
              <div className="flex items-start gap-4">
                {/* Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={cn("risk-badge", statusColor(c.status))}>{c.status?.replace(/_/g, " ")}</span>
                    <span className="text-xs text-slate-400 font-mono">{c.batch_code}</span>
                  </div>
                  <h3 className="font-semibold text-slate-900 truncate">{c.title}</h3>
                  <p className="text-sm text-slate-500 mt-0.5">{c.trainer_name} · {c.program_title}</p>
                  {c.start_datetime && (
                    <p className="text-xs text-slate-400 mt-1">
                      {formatDateTime(c.start_datetime)} → {formatDateTime(c.end_datetime)}
                    </p>
                  )}
                </div>

                {/* Stats */}
                <div className="flex items-center gap-6 text-center shrink-0">
                  <div>
                    <div className="flex items-center gap-1 justify-center">
                      <Users className="w-3.5 h-3.5 text-slate-400" />
                      <span className="font-bold text-slate-900">{c.enrolled}</span>
                    </div>
                    <p className="text-2xs text-slate-400 mt-0.5">Enrolled</p>
                  </div>
                  <div>
                    <div className="flex items-center gap-1 justify-center text-blue-600">
                      <Mail className="w-3.5 h-3.5" />
                      <span className="font-bold">{c.links_sent}</span>
                      <span className="text-xs text-slate-400">({c.links_sent_pct}%)</span>
                    </div>
                    <p className="text-2xs text-slate-400 mt-0.5">Links Sent</p>
                  </div>
                  <div>
                    <div className="flex items-center gap-1 justify-center text-emerald-600">
                      <CheckCircle className="w-3.5 h-3.5" />
                      <span className="font-bold">{c.submitted}</span>
                      <span className="text-xs text-slate-400">({c.submitted_pct}%)</span>
                    </div>
                    <p className="text-2xs text-slate-400 mt-0.5">Submitted</p>
                  </div>
                </div>

                {/* Actions */}
                <div className="flex flex-col gap-2 shrink-0">
                  <button
                    onClick={() => handleSendLinks(c.batch_id)}
                    disabled={sendingId === c.batch_id}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-blue-50 hover:bg-blue-100 text-blue-700 text-xs font-medium rounded-lg transition-colors disabled:opacity-50"
                  >
                    {sendingId === c.batch_id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
                    Send Links
                  </button>
                  {c.submitted >= 1 && (
                    <button
                      onClick={() => handleRunAI(c.batch_id)}
                      disabled={triggeringId === c.batch_id}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-emerald-50 hover:bg-emerald-100 text-emerald-700 text-xs font-medium rounded-lg transition-colors disabled:opacity-50"
                    >
                      {triggeringId === c.batch_id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Zap className="w-3.5 h-3.5" />}
                      Run AI
                    </button>
                  )}
                  <Link
                    href={`/admin/batches/${c.batch_id}`}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-50 hover:bg-slate-100 text-slate-700 text-xs font-medium rounded-lg transition-colors"
                  >
                    <ChevronRight className="w-3.5 h-3.5" />
                    Details
                  </Link>
                </div>
              </div>

              {/* Progress bar */}
              {c.enrolled > 0 && (
                <div className="mt-4 pt-3 border-t border-slate-50">
                  <div className="flex items-center justify-between text-2xs text-slate-400 mb-1.5">
                    <span>Response Progress</span>
                    <span className="font-medium text-slate-600">{c.submitted_pct}% complete</span>
                  </div>
                  <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-emerald-500 rounded-full transition-all duration-500"
                      style={{ width: `${Math.min(c.submitted_pct, 100)}%` }}
                    />
                  </div>
                </div>
              )}
            </div>
          ))}

          {campaigns.length === 0 && (
            <div className="text-center py-16 bg-white rounded-xl border border-slate-200">
              <Megaphone className="w-10 h-10 text-slate-200 mx-auto mb-3" />
              <p className="text-slate-400 font-medium">No campaigns yet</p>
              <p className="text-slate-300 text-sm mt-1">Create a training batch to start collecting feedback</p>
              <Link href="/admin/batches" className="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors">
                Go to Batches
              </Link>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
