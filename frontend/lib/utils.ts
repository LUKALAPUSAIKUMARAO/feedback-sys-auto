import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatScore(score: number | null | undefined, decimals = 1): string {
  if (score == null) return "—";
  return score.toFixed(decimals);
}

export function scoreTierColor(score: number): string {
  if (score >= 4.5) return "text-emerald-600";
  if (score >= 4.0) return "text-blue-600";
  if (score >= 3.5) return "text-amber-600";
  if (score >= 3.0) return "text-orange-600";
  return "text-red-600";
}

export function scoreBadgeVariant(score: number): "default" | "secondary" | "destructive" | "outline" {
  if (score >= 4.0) return "default";
  if (score >= 3.0) return "secondary";
  return "destructive";
}

export function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return "—";
  return new Intl.DateTimeFormat("en-US", {
    month: "short", day: "numeric", year: "numeric",
  }).format(new Date(dateStr));
}

export function formatDateTime(dateStr: string | null | undefined): string {
  if (!dateStr) return "—";
  return new Intl.DateTimeFormat("en-US", {
    month: "short", day: "numeric", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  }).format(new Date(dateStr));
}

export function statusColor(status: string): string {
  const map: Record<string, string> = {
    scheduled: "bg-blue-50 text-blue-700 ring-blue-600/20",
    ongoing: "bg-green-50 text-green-700 ring-green-600/20",
    completed: "bg-slate-50 text-slate-700 ring-slate-600/20",
    survey_open: "bg-amber-50 text-amber-700 ring-amber-600/20",
    survey_closed: "bg-orange-50 text-orange-700 ring-orange-600/20",
    processed: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
    cancelled: "bg-red-50 text-red-700 ring-red-600/20",
  };
  return map[status] || "bg-slate-50 text-slate-700 ring-slate-600/20";
}

export function sentimentColor(label: string): string {
  const map: Record<string, string> = {
    positive: "text-emerald-600",
    negative: "text-red-600",
    neutral: "text-slate-500",
  };
  return map[label] || "text-slate-500";
}

export function tierBadge(tier: string): string {
  const map: Record<string, string> = {
    "Elite": "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
    "Strong": "bg-blue-50 text-blue-700 ring-blue-600/20",
    "Satisfactory": "bg-amber-50 text-amber-700 ring-amber-600/20",
    "Needs Improvement": "bg-orange-50 text-orange-700 ring-orange-600/20",
    "At Risk": "bg-red-50 text-red-700 ring-red-600/20",
  };
  return map[tier] || "bg-slate-50 text-slate-700 ring-slate-600/20";
}

export function truncate(str: string, n: number): string {
  return str.length > n ? str.substring(0, n - 3) + "..." : str;
}
