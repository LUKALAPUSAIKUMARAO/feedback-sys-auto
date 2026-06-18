"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { batchesApi } from "@/lib/api";
import { formatDateTime, statusColor, cn } from "@/lib/utils";
import { Plus, Loader2, ChevronRight, Send } from "lucide-react";
import { toast } from "sonner";
import BatchCreateModal from "@/components/dashboard/BatchCreateModal";

export default function BatchesPage() {
  const router = useRouter();
  const [batches, setBatches] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [sendingLinks, setSendingLinks] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try {
      const res = await batchesApi.list({ page: 1, page_size: 50 });
      setBatches(res.items);
    } catch { toast.error("Failed to load batches"); }
    finally { setLoading(false); }
  }

  useEffect(() => { load(); }, []);

  async function handleSendLinks(batchId: string, e: React.MouseEvent) {
    e.stopPropagation();
    setSendingLinks(batchId);
    try {
      const res = await batchesApi.sendFeedbackLinks(batchId);
      toast.success(`Sent ${res.sent} feedback links`);
      load();
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Failed to send links");
    } finally {
      setSendingLinks(null);
    }
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="page-header">
        <div>
          <h1 className="page-title">Training Batches</h1>
          <p className="page-subtitle">{batches.length} batches across all programs</p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors"
        >
          <Plus className="w-4 h-4" /> Create Batch
        </button>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-card">
        <table className="w-full data-table">
          <thead>
            <tr>
              <th>Batch</th>
              <th>Trainer</th>
              <th>Start</th>
              <th>End</th>
              <th>Enrolled</th>
              <th>Status</th>
              <th>Actions</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={8} className="text-center py-12">
                <Loader2 className="w-5 h-5 animate-spin text-blue-600 mx-auto" />
              </td></tr>
            ) : batches.map((b: any) => (
              <tr key={b.id} className="cursor-pointer" onClick={() => router.push(`/admin/batches/${b.id}`)}>
                <td>
                  <p className="font-medium text-slate-900">{b.title || b.batch_code}</p>
                  <p className="text-xs text-slate-400 font-mono">{b.batch_code}</p>
                </td>
                <td className="text-slate-600 text-sm">{b.trainer_id?.slice(0, 8) || "—"}</td>
                <td className="text-xs text-slate-500">{formatDateTime(b.start_datetime)}</td>
                <td className="text-xs text-slate-500">{formatDateTime(b.end_datetime)}</td>
                <td className="text-slate-600">{b.actual_enrolled} / {b.max_capacity}</td>
                <td>
                  <span className={cn("risk-badge", statusColor(b.status))}>
                    {b.status.replace(/_/g, " ")}
                  </span>
                </td>
                <td>
                  {b.status === "completed" && (
                    <button
                      onClick={(e) => handleSendLinks(b.id, e)}
                      disabled={sendingLinks === b.id}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-blue-50 hover:bg-blue-100 text-blue-700 text-xs font-medium rounded-lg transition-colors"
                    >
                      {sendingLinks === b.id
                        ? <Loader2 className="w-3 h-3 animate-spin" />
                        : <Send className="w-3 h-3" />}
                      Send Links
                    </button>
                  )}
                </td>
                <td><ChevronRight className="w-4 h-4 text-slate-300" /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showCreate && (
        <BatchCreateModal
          onClose={() => setShowCreate(false)}
          onCreated={() => { setShowCreate(false); load(); }}
        />
      )}
    </div>
  );
}
