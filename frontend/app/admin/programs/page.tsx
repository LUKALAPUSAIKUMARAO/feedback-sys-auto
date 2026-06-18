"use client";
import { useEffect, useState } from "react";
import { programsApi } from "@/lib/api";
import { Plus, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

const schema = z.object({
  title: z.string().min(3),
  description: z.string().optional(),
  skills_covered: z.string().optional(),
  competency_tags: z.string().optional(),
  duration_hours: z.coerce.number().optional(),
  level: z.enum(["beginner", "intermediate", "advanced", "expert"]).optional(),
});
type FormData = z.infer<typeof schema>;

export default function ProgramsPage() {
  const [programs, setPrograms] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);

  const { register, handleSubmit, reset, formState: { errors } } = useForm<FormData>({ resolver: zodResolver(schema) });

  async function load() {
    setLoading(true);
    try {
      const res = await programsApi.list({ page: 1, page_size: 50 });
      setPrograms(res.items);
    } catch { toast.error("Failed to load programs"); }
    finally { setLoading(false); }
  }

  useEffect(() => { load(); }, []);

  async function onSubmit(data: FormData) {
    setCreating(true);
    try {
      await programsApi.create({
        ...data,
        skills_covered: data.skills_covered ? data.skills_covered.split(",").map(s => s.trim()) : [],
        competency_tags: data.competency_tags ? data.competency_tags.split(",").map(s => s.trim()) : [],
      });
      toast.success("Program created");
      reset();
      setShowCreate(false);
      load();
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Failed");
    } finally { setCreating(false); }
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="page-header">
        <div>
          <h1 className="page-title">Training Programs</h1>
          <p className="page-subtitle">{programs.length} programs defined</p>
        </div>
        <button onClick={() => setShowCreate(true)} className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors">
          <Plus className="w-4 h-4" /> New Program
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {loading ? (
          <div className="col-span-3 flex justify-center py-12"><Loader2 className="w-6 h-6 animate-spin text-blue-600" /></div>
        ) : programs.map((p: any) => (
          <div key={p.id} className="stat-card">
            <div className="flex items-start justify-between mb-2">
              <h3 className="text-sm font-semibold text-slate-900">{p.title}</h3>
              {p.level && <span className="text-xs text-slate-500 bg-slate-100 px-2 py-0.5 rounded-full capitalize">{p.level}</span>}
            </div>
            {p.description && <p className="text-xs text-slate-500 mb-3 line-clamp-2">{p.description}</p>}
            <div className="flex flex-wrap gap-1.5">
              {p.skills_covered?.slice(0, 4).map((s: string) => (
                <span key={s} className="px-2 py-0.5 bg-blue-50 text-blue-700 text-2xs font-medium rounded-full ring-1 ring-blue-200">{s}</span>
              ))}
            </div>
            {p.duration_hours && <p className="text-xs text-slate-400 mt-3">{p.duration_hours} hours</p>}
          </div>
        ))}
      </div>

      {showCreate && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between px-6 py-5 border-b border-slate-200">
              <h2 className="text-base font-semibold text-slate-900">Create Training Program</h2>
              <button onClick={() => setShowCreate(false)} className="p-1.5 hover:bg-slate-100 rounded-lg text-slate-400 text-xl">×</button>
            </div>
            <form onSubmit={handleSubmit(onSubmit)} className="p-6 space-y-4">
              {[
                { name: "title", label: "Title *", placeholder: "e.g., Advanced Python for Data Engineering" },
                { name: "description", label: "Description", placeholder: "Course overview…", type: "textarea" },
                { name: "skills_covered", label: "Skills (comma-separated)", placeholder: "Python, Pandas, Spark" },
                { name: "competency_tags", label: "Competency Tags (comma-separated)", placeholder: "Data Engineering, Cloud, ETL" },
              ].map(({ name, label, placeholder, type }) => (
                <div key={name}>
                  <label className="block text-sm font-medium text-slate-700 mb-1">{label}</label>
                  {type === "textarea" ? (
                    <textarea {...register(name as any)} placeholder={placeholder} rows={2} className="w-full border border-slate-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/30 resize-none" />
                  ) : (
                    <input {...register(name as any)} placeholder={placeholder} className="w-full border border-slate-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/30" />
                  )}
                  {errors[name as keyof FormData] && <p className="text-red-500 text-xs mt-1">{errors[name as keyof FormData]?.message}</p>}
                </div>
              ))}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Duration (hours)</label>
                  <input type="number" step="0.5" {...register("duration_hours")} placeholder="40" className="w-full border border-slate-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/30" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Level</label>
                  <select {...register("level")} className="w-full border border-slate-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/30">
                    <option value="">Select…</option>
                    {["beginner", "intermediate", "advanced", "expert"].map(l => <option key={l} value={l} className="capitalize">{l}</option>)}
                  </select>
                </div>
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button type="button" onClick={() => setShowCreate(false)} className="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-lg">Cancel</button>
                <button type="submit" disabled={creating} className="px-6 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg flex items-center gap-2">
                  {creating && <Loader2 className="w-4 h-4 animate-spin" />} Create
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
