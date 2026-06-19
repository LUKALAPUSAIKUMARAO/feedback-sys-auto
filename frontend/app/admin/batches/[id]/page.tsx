"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { batchesApi, analyticsApi } from "@/lib/api";
import { formatDateTime, statusColor, cn } from "@/lib/utils";
import { ArrowLeft, Upload, Send, Zap, Loader2, Users, CheckCircle, Clock, Copy, ExternalLink } from "lucide-react";
import { toast } from "sonner";
import ParticipantUploadModal from "@/components/dashboard/ParticipantUploadModal";

export default function BatchDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [batch, setBatch] = useState<any>(null);
  const [roster, setRoster] = useState<any[]>([]);
  const [pipelineRuns, setPipelineRuns] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showUpload, setShowUpload] = useState(false);
  const [sendingLinks, setSendingLinks] = useState(false);
  const [triggeringPipeline, setTriggeringPipeline] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const [b, r, runs] = await Promise.all([
        batchesApi.get(id),
        batchesApi.getRoster(id),
        analyticsApi.pipelineRuns(id),
      ]);
      setBatch(b);
      setRoster(r);
      setPipelineRuns(runs);
    } catch { toast.error("Failed to load batch"); }
    finally { setLoading(false); }
  }

  useEffect(() => { load(); }, [id]);

  async function handleSendLinks() {
    setSendingLinks(true);
    try {
      const res = await batchesApi.sendFeedbackLinks(id);
      toast.success(`Sent ${res.sent} feedback links`);
      load();
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Failed to send links");
    } finally { setSendingLinks(false); }
  }

  async function handleTriggerPipeline() {
    setTriggeringPipeline(true);
    try {
      await analyticsApi.triggerPipeline({ batch_id: id, force: false });
      toast.success("Pipeline triggered — analysis running in background");
      setTimeout(load, 3000);
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Failed to trigger pipeline");
    } finally { setTriggeringPipeline(false); }
  }

  function copyLink(url: string) {
    navigator.clipboard.writeText(url).then(() => toast.success("Link copied!"));
  }

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <Loader2 className="w-6 h-6 text-blue-600 animate-spin" />
    </div>
  );

  const submitted = roster.filter((r) => r.has_submitted).length;
  const linksSent = roster.filter((r) => r.feedback_link_sent).length;

  return (
    <div className="space-y-6 animate-fade-in">
      <button onClick={() => router.back()} className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-800 mb-2 transition-colors">
        <ArrowLeft className="w-4 h-4" /> Back to Batches
      </button>

      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="page-title">{batch?.title || batch?.batch_code}</h1>
          <div className="flex items-center gap-3 mt-1">
            <span className={cn("risk-badge", statusColor(batch?.status))}>{batch?.status?.replace(/_/g, " ")}</span>
            <span className="text-sm text-slate-500">{formatDateTime(batch?.start_datetime)} → {formatDateTime(batch?.end_datetime)}</span>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-wrap justify-end">
          <button
            onClick={() => setShowUpload(true)}
            className="inline-flex items-center gap-2 px-4 py-2 bg-white border border-slate-200 text-slate-700 text-sm font-medium rounded-lg hover:bg-slate-50 transition-colors"
          >
            <Upload className="w-4 h-4" /> Upload Participants
          </button>
          {["completed", "survey_open", "survey_closed", "scheduled", "ongoing"].includes(batch?.status) && (
            <button
              onClick={handleSendLinks}
              disabled={sendingLinks}
              className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
            >
              {sendingLinks ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              Send Feedback Links
            </button>
          )}
          {["survey_open", "survey_closed", "completed"].includes(batch?.status) && (
            <button
              onClick={handleTriggerPipeline}
              disabled={triggeringPipeline}
              className="inline-flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
            >
              {triggeringPipeline ? <Loader2 className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}
              Run AI Analysis
            </button>
          )}
        </div>
      </div>

      {/* Summary KPIs */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: "Enrolled", value: roster.length },
          { label: "Links Sent", value: linksSent },
          { label: "Submitted", value: submitted },
          { label: "Response Rate", value: roster.length ? `${Math.round(submitted / roster.length * 100)}%` : "—" },
        ].map((kpi) => (
          <div key={kpi.label} className="stat-card text-center">
            <p className="text-2xl font-bold text-slate-900 tabular-nums">{kpi.value}</p>
            <p className="text-xs text-slate-500 mt-1">{kpi.label}</p>
          </div>
        ))}
      </div>

      {/* Roster with status */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-card">
        <div className="px-5 py-4 border-b border-slate-100 flex items-center gap-2">
          <Users className="w-4 h-4 text-slate-400" />
          <h3 className="text-sm font-semibold text-slate-800">Participant Roster ({roster.length})</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Employee ID</th>
                <th>Email</th>
                <th>Department</th>
                <th>Link Sent</th>
                <th>Submitted</th>
                <th>Feedback Link</th>
              </tr>
            </thead>
            <tbody>
              {roster.map((p: any) => (
                <tr key={p.roster_id}>
                  <td className="font-medium text-slate-900">{p.full_name}</td>
                  <td className="font-mono text-xs text-slate-500">{p.employee_id}</td>
                  <td className="text-slate-500 text-sm">{p.email}</td>
                  <td className="text-slate-500">{p.department || "—"}</td>
                  <td>
                    {p.feedback_link_sent ? (
                      <div className="flex items-center gap-1 text-emerald-600">
                        <CheckCircle className="w-3.5 h-3.5" />
                        <span className="text-xs">{p.feedback_link_sent_at ? formatDateTime(p.feedback_link_sent_at) : "Sent"}</span>
                      </div>
                    ) : (
                      <span className="flex items-center gap-1 text-slate-400 text-xs"><Clock className="w-3.5 h-3.5" /> Pending</span>
                    )}
                  </td>
                  <td>
                    {p.has_submitted ? (
                      <span className="flex items-center gap-1 text-emerald-600 text-xs font-medium">
                        <CheckCircle className="w-3.5 h-3.5" /> Done
                      </span>
                    ) : (
                      <span className="text-slate-400 text-xs">Awaiting</span>
                    )}
                  </td>
                  <td>
                    {p.feedback_url ? (
                      <div className="flex items-center gap-1.5">
                        <button
                          onClick={() => copyLink(p.feedback_url)}
                          className="text-slate-400 hover:text-blue-600 transition-colors"
                          title="Copy link"
                        >
                          <Copy className="w-3.5 h-3.5" />
                        </button>
                        <a
                          href={p.feedback_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-slate-400 hover:text-blue-600 transition-colors"
                          title="Open link"
                        >
                          <ExternalLink className="w-3.5 h-3.5" />
                        </a>
                      </div>
                    ) : (
                      <span className="text-slate-300 text-xs">—</span>
                    )}
                  </td>
                </tr>
              ))}
              {roster.length === 0 && (
                <tr>
                  <td colSpan={7} className="text-center text-slate-400 py-8">No participants enrolled yet</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Pipeline runs */}
      {pipelineRuns.length > 0 && (
        <div className="stat-card">
          <h3 className="text-sm font-semibold text-slate-800 mb-3">AI Pipeline Run History</h3>
          <div className="space-y-2">
            {pipelineRuns.map((run: any) => (
              <div key={run.id} className="flex items-center justify-between py-2 border-b border-slate-100 last:border-0">
                <div>
                  <span className={cn("risk-badge text-xs",
                    run.run_status === "completed" ? "bg-emerald-50 text-emerald-700 ring-emerald-600/20" :
                    run.run_status === "failed" ? "bg-red-50 text-red-700 ring-red-600/20" :
                    "bg-amber-50 text-amber-700 ring-amber-600/20"
                  )}>{run.run_status}</span>
                  <span className="text-xs text-slate-500 ml-3">
                    {run.submission_count} submissions · {run.agents_run?.length || 0} agents
                    {run.duration_ms ? ` · ${(run.duration_ms / 1000).toFixed(1)}s` : ""}
                  </span>
                </div>
                <span className="text-xs text-slate-400">{formatDateTime(run.created_at)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {showUpload && (
        <ParticipantUploadModal
          batchId={id}
          onClose={() => setShowUpload(false)}
          onUploaded={() => { setShowUpload(false); load(); }}
        />
      )}
    </div>
  );
}
