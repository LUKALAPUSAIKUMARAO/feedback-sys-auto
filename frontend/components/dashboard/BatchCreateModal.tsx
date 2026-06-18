"use client";
import { useState, useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { batchesApi, trainersApi, programsApi } from "@/lib/api";
import { X, Loader2 } from "lucide-react";
import { toast } from "sonner";

const schema = z.object({
  program_id: z.string().uuid(),
  trainer_id: z.string().uuid(),
  batch_code: z.string().min(2),
  title: z.string().optional(),
  start_datetime: z.string().min(1),
  end_datetime: z.string().min(1),
  max_capacity: z.coerce.number().min(1).max(1000).default(30),
  venue: z.string().optional(),
  mode: z.enum(["online", "offline", "hybrid"]).default("online"),
});
type FormData = z.infer<typeof schema>;

export default function BatchCreateModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [loading, setLoading] = useState(false);
  const [trainers, setTrainers] = useState<any[]>([]);
  const [programs, setPrograms] = useState<any[]>([]);

  const { register, handleSubmit, formState: { errors } } = useForm<FormData>({ resolver: zodResolver(schema) });

  useEffect(() => {
    Promise.all([
      trainersApi.list({ page: 1, page_size: 100 }),
      programsApi.list({ page: 1, page_size: 100 }),
    ]).then(([t, p]) => {
      setTrainers(t.items);
      setPrograms(p.items);
    }).catch(() => toast.error("Failed to load trainers/programs"));
  }, []);

  async function onSubmit(data: FormData) {
    setLoading(true);
    try {
      await batchesApi.create({
        ...data,
        start_datetime: new Date(data.start_datetime).toISOString(),
        end_datetime: new Date(data.end_datetime).toISOString(),
      });
      toast.success("Batch created successfully");
      onCreated();
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Failed to create batch");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between px-6 py-5 border-b border-slate-200">
          <h2 className="text-base font-semibold text-slate-900">Create Training Batch</h2>
          <button onClick={onClose} className="p-1.5 hover:bg-slate-100 rounded-lg text-slate-400"><X className="w-4 h-4" /></button>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Training Program *</label>
            <select {...register("program_id")} className="w-full border border-slate-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/30">
              <option value="">Select program…</option>
              {programs.map((p: any) => <option key={p.id} value={p.id}>{p.title}</option>)}
            </select>
            {errors.program_id && <p className="text-red-500 text-xs mt-1">Select a program</p>}
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Trainer *</label>
            <select {...register("trainer_id")} className="w-full border border-slate-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/30">
              <option value="">Select trainer…</option>
              {trainers.map((t: any) => <option key={t.id} value={t.id}>{t.full_name} ({t.employee_id})</option>)}
            </select>
            {errors.trainer_id && <p className="text-red-500 text-xs mt-1">Select a trainer</p>}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Batch Code *</label>
              <input {...register("batch_code")} placeholder="e.g., BATCH-2025-01" className="w-full border border-slate-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/30" />
              {errors.batch_code && <p className="text-red-500 text-xs mt-1">{errors.batch_code.message}</p>}
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Mode</label>
              <select {...register("mode")} className="w-full border border-slate-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/30">
                <option value="online">Online</option>
                <option value="offline">Offline</option>
                <option value="hybrid">Hybrid</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Title (Optional)</label>
            <input {...register("title")} placeholder="e.g., Python Advanced — Batch 3" className="w-full border border-slate-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/30" />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Start Date & Time *</label>
              <input type="datetime-local" {...register("start_datetime")} className="w-full border border-slate-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/30" />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">End Date & Time *</label>
              <input type="datetime-local" {...register("end_datetime")} className="w-full border border-slate-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/30" />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Max Capacity</label>
              <input type="number" {...register("max_capacity")} defaultValue={30} min={1} className="w-full border border-slate-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/30" />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Venue</label>
              <input {...register("venue")} placeholder="e.g., Room 4B / Zoom" className="w-full border border-slate-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/30" />
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-lg transition-colors">Cancel</button>
            <button type="submit" disabled={loading} className="px-6 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors flex items-center gap-2">
              {loading && <Loader2 className="w-4 h-4 animate-spin" />}
              Create Batch
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
