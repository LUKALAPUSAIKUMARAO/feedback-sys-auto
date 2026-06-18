"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Search, Loader2 } from "lucide-react";
import { toast } from "sonner";

export default function ParticipantsPage() {
  const [participants, setParticipants] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [total, setTotal] = useState(0);

  async function load(s = "") {
    setLoading(true);
    try {
      const res = await api.get("/admin/participants", { params: { page: 1, page_size: 50, search: s || undefined } }).then(r => r.data);
      setParticipants(res.items || []);
      setTotal(res.total || 0);
    } catch { toast.error("Failed to load participants"); }
    finally { setLoading(false); }
  }

  useEffect(() => { load(); }, []);

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="page-header">
        <div>
          <h1 className="page-title">Participants</h1>
          <p className="page-subtitle">{total} participants registered</p>
        </div>
      </div>

      <form onSubmit={(e) => { e.preventDefault(); load(search); }} className="flex gap-2 max-w-sm">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search participants…"
            className="w-full pl-9 pr-4 py-2 text-sm bg-white border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/30"
          />
        </div>
        <button type="submit" className="px-4 py-2 bg-slate-900 text-white text-sm rounded-lg hover:bg-slate-800 transition-colors">Search</button>
      </form>

      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-card">
        <table className="w-full data-table">
          <thead>
            <tr><th>Name</th><th>Employee ID</th><th>Email</th><th>Department</th><th>Designation</th></tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={5} className="text-center py-12"><Loader2 className="w-5 h-5 animate-spin text-blue-600 mx-auto" /></td></tr>
            ) : participants.length === 0 ? (
              <tr><td colSpan={5} className="text-center py-12 text-slate-500 text-sm">No participants found</td></tr>
            ) : participants.map((p: any) => (
              <tr key={p.id}>
                <td className="font-medium text-slate-900">{p.full_name}</td>
                <td className="font-mono text-xs text-slate-500">{p.employee_id}</td>
                <td className="text-slate-500 text-sm">{p.email}</td>
                <td className="text-slate-500">{p.department || "—"}</td>
                <td className="text-slate-500">{p.designation || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
