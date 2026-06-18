"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { trainersApi } from "@/lib/api";
import { formatScore, scoreTierColor, tierBadge, cn } from "@/lib/utils";
import { Plus, Search, Loader2, ChevronRight } from "lucide-react";
import { toast } from "sonner";
import TrainerCreateModal from "@/components/dashboard/TrainerCreateModal";

export default function TrainersPage() {
  const router = useRouter();
  const [trainers, setTrainers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);

  async function load(p = 1, s = search) {
    setLoading(true);
    try {
      const res = await trainersApi.list({ page: p, page_size: 20, search: s || undefined });
      setTrainers(res.items);
      setTotal(res.total);
    } catch {
      toast.error("Failed to load trainers");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(1, ""); }, []);

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setPage(1);
    load(1, search);
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="page-header">
        <div>
          <h1 className="page-title">Trainers</h1>
          <p className="page-subtitle">{total} registered trainers</p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors"
        >
          <Plus className="w-4 h-4" />
          Add Trainer
        </button>
      </div>

      {/* Search */}
      <form onSubmit={handleSearch} className="flex gap-2 max-w-sm">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by name…"
            className="w-full pl-9 pr-4 py-2 text-sm bg-white border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-400"
          />
        </div>
        <button type="submit" className="px-4 py-2 bg-slate-900 text-white text-sm rounded-lg hover:bg-slate-800 transition-colors">
          Search
        </button>
      </form>

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-card">
        <table className="w-full data-table">
          <thead>
            <tr>
              <th>Trainer</th>
              <th>Employee ID</th>
              <th>Department</th>
              <th>Sessions</th>
              <th>Avg Rating</th>
              <th>Health Score</th>
              <th>Tier</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={8} className="text-center py-12">
                <Loader2 className="w-5 h-5 animate-spin text-blue-600 mx-auto" />
              </td></tr>
            ) : trainers.length === 0 ? (
              <tr><td colSpan={8} className="text-center py-12 text-slate-500 text-sm">No trainers found</td></tr>
            ) : trainers.map((t: any) => (
              <tr
                key={t.id}
                className="cursor-pointer"
                onClick={() => router.push(`/admin/trainers/${t.id}`)}
              >
                <td>
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center shrink-0">
                      <span className="text-blue-700 text-xs font-semibold">{t.full_name.charAt(0)}</span>
                    </div>
                    <div>
                      <p className="font-medium text-slate-900">{t.full_name}</p>
                      <p className="text-xs text-slate-400">{t.email}</p>
                    </div>
                  </div>
                </td>
                <td className="font-mono text-xs text-slate-500">{t.employee_id}</td>
                <td className="text-slate-600">{t.department || "—"}</td>
                <td className="text-slate-600">{t.total_sessions}</td>
                <td className={cn("font-semibold tabular-nums", scoreTierColor(t.avg_rating))}>
                  {formatScore(t.avg_rating)} / 5
                </td>
                <td className={cn("font-bold tabular-nums text-base", scoreTierColor(t.overall_health_score))}>
                  {formatScore(t.overall_health_score)}
                </td>
                <td>
                  {t.total_sessions > 0 && (
                    <span className={cn("risk-badge text-xs", tierBadge(
                      t.overall_health_score >= 4.5 ? "Elite" :
                      t.overall_health_score >= 4.0 ? "Strong" :
                      t.overall_health_score >= 3.5 ? "Satisfactory" :
                      t.overall_health_score >= 3.0 ? "Needs Improvement" : "At Risk"
                    ))}>
                      {t.overall_health_score >= 4.5 ? "Elite" :
                       t.overall_health_score >= 4.0 ? "Strong" :
                       t.overall_health_score >= 3.5 ? "Satisfactory" :
                       t.overall_health_score >= 3.0 ? "Needs Improvement" : "At Risk"}
                    </span>
                  )}
                </td>
                <td><ChevronRight className="w-4 h-4 text-slate-300" /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showCreate && (
        <TrainerCreateModal
          onClose={() => setShowCreate(false)}
          onCreated={() => { setShowCreate(false); load(1, ""); }}
        />
      )}
    </div>
  );
}
