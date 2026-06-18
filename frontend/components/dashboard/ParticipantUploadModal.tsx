"use client";
import { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { batchesApi } from "@/lib/api";
import { X, Upload, Loader2, CheckCircle, AlertCircle, FileText } from "lucide-react";
import { toast } from "sonner";

interface UploadResult {
  created: number;
  updated: number;
  enrolled: number;
  errors: any[];
}

export default function ParticipantUploadModal({
  batchId, onClose, onUploaded
}: { batchId: string; onClose: () => void; onUploaded: () => void }) {
  const [mode, setMode] = useState<"csv" | "manual">("csv");
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<UploadResult | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [manualRows, setManualRows] = useState([
    { full_name: "", email: "", employee_id: "", department: "", designation: "" }
  ]);

  const onDrop = useCallback((accepted: File[]) => {
    if (accepted[0]) setFile(accepted[0]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "text/csv": [".csv"] },
    maxFiles: 1,
  });

  async function handleCSVUpload() {
    if (!file) return;
    setUploading(true);
    try {
      const res = await batchesApi.uploadCSV(batchId, file);
      setResult(res);
      toast.success(`${res.enrolled} participants enrolled`);
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  async function handleManualUpload() {
    const valid = manualRows.filter(r => r.full_name && r.email && r.employee_id);
    if (!valid.length) { toast.error("Add at least one valid participant"); return; }
    setUploading(true);
    try {
      const res = await batchesApi.uploadParticipants(batchId, { participants: valid });
      setResult(res);
      toast.success(`${res.enrolled} participants enrolled`);
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  function addRow() {
    setManualRows(r => [...r, { full_name: "", email: "", employee_id: "", department: "", designation: "" }]);
  }

  function updateRow(i: number, field: string, value: string) {
    setManualRows(r => r.map((row, idx) => idx === i ? { ...row, [field]: value } : row));
  }

  if (result) {
    return (
      <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-8 text-center">
          <CheckCircle className="w-12 h-12 text-emerald-500 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-slate-900 mb-1">Upload Complete</h3>
          <div className="grid grid-cols-3 gap-3 mt-4 mb-6">
            {[["Created", result.created], ["Updated", result.updated], ["Enrolled", result.enrolled]].map(([l, v]) => (
              <div key={l} className="bg-slate-50 rounded-xl p-3">
                <p className="text-2xl font-bold text-slate-900">{v}</p>
                <p className="text-xs text-slate-500">{l}</p>
              </div>
            ))}
          </div>
          {result.errors.length > 0 && (
            <div className="bg-red-50 rounded-xl p-3 mb-4 text-left">
              <p className="text-xs font-medium text-red-700 mb-1 flex items-center gap-1">
                <AlertCircle className="w-3.5 h-3.5" /> {result.errors.length} errors
              </p>
              {result.errors.slice(0, 3).map((e, i) => (
                <p key={i} className="text-xs text-red-600">{e.employee_id}: {e.error}</p>
              ))}
            </div>
          )}
          <button onClick={onUploaded} className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-2.5 rounded-xl text-sm transition-colors">
            Done
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between px-6 py-5 border-b border-slate-200">
          <h2 className="text-base font-semibold text-slate-900">Upload Participants</h2>
          <button onClick={onClose} className="p-1.5 hover:bg-slate-100 rounded-lg text-slate-400"><X className="w-4 h-4" /></button>
        </div>

        <div className="p-6">
          {/* Mode Toggle */}
          <div className="flex gap-2 mb-6">
            {(["csv", "manual"] as const).map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
                  mode === m ? "bg-blue-600 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                }`}
              >
                {m === "csv" ? "Upload CSV" : "Manual Entry"}
              </button>
            ))}
          </div>

          {mode === "csv" ? (
            <div className="space-y-4">
              <div
                {...getRootProps()}
                className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${
                  isDragActive ? "border-blue-400 bg-blue-50" : "border-slate-200 hover:border-slate-300 hover:bg-slate-50"
                }`}
              >
                <input {...getInputProps()} />
                {file ? (
                  <div className="flex items-center justify-center gap-2">
                    <FileText className="w-5 h-5 text-blue-600" />
                    <p className="text-sm font-medium text-slate-700">{file.name}</p>
                  </div>
                ) : (
                  <>
                    <Upload className="w-8 h-8 text-slate-400 mx-auto mb-2" />
                    <p className="text-sm font-medium text-slate-700">Drop CSV file here or click to browse</p>
                    <p className="text-xs text-slate-400 mt-1">Required columns: full_name, email, employee_id</p>
                    <p className="text-xs text-slate-400">Optional: department, designation</p>
                  </>
                )}
              </div>
              <button
                onClick={handleCSVUpload}
                disabled={!file || uploading}
                className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white font-medium text-sm rounded-xl transition-colors flex items-center justify-center gap-2"
              >
                {uploading && <Loader2 className="w-4 h-4 animate-spin" />}
                Upload & Enroll
              </button>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr>
                      {["Full Name *", "Email *", "Employee ID *", "Department", "Designation"].map(h => (
                        <th key={h} className="text-left px-2 py-2 text-xs font-semibold text-slate-500 uppercase">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {manualRows.map((row, i) => (
                      <tr key={i}>
                        {(["full_name", "email", "employee_id", "department", "designation"] as const).map(field => (
                          <td key={field} className="px-1 py-1">
                            <input
                              value={row[field]}
                              onChange={(e) => updateRow(i, field, e.target.value)}
                              className="w-full border border-slate-200 rounded-md px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500/30"
                              placeholder={field.replace("_", " ")}
                            />
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <button onClick={addRow} className="text-sm text-blue-600 hover:text-blue-700 font-medium">+ Add row</button>
              <button
                onClick={handleManualUpload}
                disabled={uploading}
                className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white font-medium text-sm rounded-xl transition-colors flex items-center justify-center gap-2"
              >
                {uploading && <Loader2 className="w-4 h-4 animate-spin" />}
                Enroll Participants
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
