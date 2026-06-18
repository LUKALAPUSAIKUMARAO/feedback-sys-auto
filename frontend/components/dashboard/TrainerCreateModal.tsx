"use client";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { trainersApi } from "@/lib/api";
import { X, Loader2 } from "lucide-react";
import { toast } from "sonner";

const schema = z.object({
  full_name: z.string().min(2),
  employee_id: z.string().min(1),
  email: z.string().email(),
  designation: z.string().optional(),
  department: z.string().optional(),
  skills: z.string().optional(),
  bio: z.string().optional(),
});
type FormData = z.infer<typeof schema>;

export default function TrainerCreateModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [loading, setLoading] = useState(false);
  const { register, handleSubmit, formState: { errors } } = useForm<FormData>({ resolver: zodResolver(schema) });

  async function onSubmit(data: FormData) {
    setLoading(true);
    try {
      await trainersApi.create({
        ...data,
        skills: data.skills ? data.skills.split(",").map(s => s.trim()).filter(Boolean) : [],
      });
      toast.success("Trainer created successfully");
      onCreated();
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Failed to create trainer");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between px-6 py-5 border-b border-slate-200">
          <h2 className="text-base font-semibold text-slate-900">Add New Trainer</h2>
          <button onClick={onClose} className="p-1.5 hover:bg-slate-100 rounded-lg text-slate-400"><X className="w-4 h-4" /></button>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="p-6 space-y-4">
          {[
            { name: "full_name", label: "Full Name *", placeholder: "e.g., Rajesh Kumar" },
            { name: "employee_id", label: "Employee ID *", placeholder: "e.g., EMP001" },
            { name: "email", label: "Email *", placeholder: "rajesh@company.com", type: "email" },
            { name: "designation", label: "Designation", placeholder: "e.g., Senior Software Engineer" },
            { name: "department", label: "Department", placeholder: "e.g., Engineering" },
            { name: "skills", label: "Skills (comma-separated)", placeholder: "Python, Machine Learning, AWS" },
          ].map(({ name, label, placeholder, type }) => (
            <div key={name}>
              <label className="block text-sm font-medium text-slate-700 mb-1">{label}</label>
              <input
                {...register(name as keyof FormData)}
                type={type || "text"}
                placeholder={placeholder}
                className="w-full border border-slate-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-400"
              />
              {errors[name as keyof FormData] && (
                <p className="text-red-500 text-xs mt-1">{errors[name as keyof FormData]?.message}</p>
              )}
            </div>
          ))}

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Bio (Optional)</label>
            <textarea
              {...register("bio")}
              rows={3}
              placeholder="Brief professional background…"
              className="w-full border border-slate-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-400 resize-none"
            />
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-lg transition-colors">Cancel</button>
            <button type="submit" disabled={loading} className="px-6 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors flex items-center gap-2">
              {loading && <Loader2 className="w-4 h-4 animate-spin" />}
              Create Trainer
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
