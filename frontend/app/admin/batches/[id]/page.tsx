"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { batchesApi, analyticsApi } from "@/lib/api";
import { formatDateTime, statusColor, cn } from "@/lib/utils";
import { ArrowLeft, Upload, Send, Zap, Loader2, Users } from "lucide-react";
import { toast } from "sonner";
import ParticipantUploadModal from "@/components/dashboard/ParticipantUploadModal";

export default function BatchDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [batch, setBatch] = useState<any>(null);
  const [participants, setParticipants] = useState<any[]>([]);
  const [pipelineRuns, setPipelineRuns] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showUpload, setShowUpload] = useState(false);
  const [sendingLinks, setSendingLinks] = useState(false);
  const [triggeringPipeline, setTriggeringPipeline] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const [b, p, runs] = await Promise.all([
        batchesApi.get(id),
        batchesApi.getParticipants(id, { page: 1, page_size: 100 }),
        analyticsApi.pipelineRuns(id),
      ]);
      setBatch(b);
      setParticipants(p.items);
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
      setTimeout(load, 2000);
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Failed to trigger pipeline");
    } finally { setTriggeringPipeline(false); }
  }

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <Loader2 className="w-6 h-6 text-blue-600 animate-spin" />
    </div>
  );

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
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowUpload(true)}
            className="inline-flex items-center gap-2 px-4 py-2 bg-white border border-slate-200 text-slate-700 text-sm font-medium rounded-lg hover:bg-slate-50 transition-colors"
          >
            <Upload className="w-4 h-4" /> Upload Participants
          </button>
          {["completed", "survey_open", "survey_closed"].includes(batch?.status) && (
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

      {/* Participants */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-card">
        <div className="px-5 py-4 border-b border-slate-100 flex items-center gap-2">
          <Users className="w-4 h-4 text-slate-400" />
          <h3 className="text-sm font-semibold text-slate-800">Participants ({participants.length})</h3>
        </div>
        <table className="w-full data-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Employee ID</th>
              <th>Email</th>
              <th>Department</th>
            </tr>
          </thead>
          <tbody>
            {participants.map((p: any) => (
              <tr key={p.id}>
                <td className="font-medium text-slate-900">{p.full_name}</td>
                <td className="font-mono text-xs text-slate-500">{p.employee_id}</td>
                <td className="text-slate-500 text-sm">{p.email}</td>
                <td className="text-slate-500">{p.department || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pipeline runs */}
      {pipelineRuns.length > 0 && (
        <div className="stat-card">
          <h3 className="text-sm font-semibold text-slate-800 mb-3">Pipeline Run History</h3>
          <div className="space-y-2">
            {pipelineRuns.map((run: any) => (
              <div key={run.id} className="flex items-center justify-between py-2 border-b border-slate-100 last:border-0">
                <div>
                  <span className={cn("risk-badge text-xs",
                    run.run_status === "completed" ? "bg-emerald-50 text-emerald-700 ring-emerald-600/20" :
                    run.run_status === "failed" ? "bg-red-50 text-red-700 ring-red-600/20" :
                    "bg-amber-50 text-amber-700 ring-amber-600/20"
                  )}>{run.run_status}</span>
                  <span className="text-xs text-slate-500 ml-3">{run.submission_count} submissions · {run.agents_run?.length} agents</span>
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
