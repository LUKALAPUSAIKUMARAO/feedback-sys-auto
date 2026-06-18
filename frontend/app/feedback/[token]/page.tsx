"use client";
import { useEffect, useState, useRef } from "react";
import { useParams } from "next/navigation";
import { feedbackApi } from "@/lib/api";
import { Star, Mic, MicOff, CheckCircle, XCircle, Loader2, Send } from "lucide-react";
import { toast } from "sonner";

interface TokenInfo {
  valid: boolean;
  participant_name?: string;
  batch_title?: string;
  trainer_name?: string;
  program_title?: string;
  already_submitted?: boolean;
  expired?: boolean;
}

const RATING_DIMENSIONS = [
  { key: "rating_technical_knowledge", label: "Technical Knowledge", desc: "Depth and accuracy of technical content" },
  { key: "rating_communication", label: "Communication", desc: "Clarity and effectiveness of delivery" },
  { key: "rating_session_engagement", label: "Session Engagement", desc: "Interactivity and participation quality" },
  { key: "rating_time_management", label: "Time Management", desc: "Punctuality, pacing, and schedule adherence" },
  { key: "rating_practical_learning", label: "Practical Learning", desc: "Hands-on examples and real-world application" },
  { key: "rating_content_quality", label: "Content Quality", desc: "Relevance, structure, and material quality" },
];

function StarRating({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  const [hovered, setHovered] = useState(0);
  const labels = ["", "Poor", "Fair", "Good", "Very Good", "Excellent"];
  return (
    <div className="flex items-center gap-1">
      {[1, 2, 3, 4, 5].map((star) => (
        <button
          key={star}
          type="button"
          onClick={() => onChange(star)}
          onMouseEnter={() => setHovered(star)}
          onMouseLeave={() => setHovered(0)}
          className="transition-transform hover:scale-110 focus:outline-none"
          aria-label={`Rate ${star} stars`}
        >
          <Star
            className={`w-7 h-7 transition-colors ${
              star <= (hovered || value)
                ? "fill-amber-400 text-amber-400"
                : "fill-transparent text-slate-200"
            }`}
          />
        </button>
      ))}
      {(hovered || value) > 0 && (
        <span className="ml-2 text-sm text-slate-500 font-medium">
          {labels[hovered || value]}
        </span>
      )}
    </div>
  );
}

export default function FeedbackPage() {
  const { token } = useParams<{ token: string }>();
  const [tokenInfo, setTokenInfo] = useState<TokenInfo | null>(null);
  const [validating, setValidating] = useState(true);
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [isAnonymous, setIsAnonymous] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const [ratings, setRatings] = useState<Record<string, number>>({
    rating_technical_knowledge: 0,
    rating_communication: 0,
    rating_session_engagement: 0,
    rating_time_management: 0,
    rating_practical_learning: 0,
    rating_content_quality: 0,
  });
  const [textPositive, setTextPositive] = useState("");
  const [textImprove, setTextImprove] = useState("");
  const [textOverall, setTextOverall] = useState("");

  useEffect(() => {
    feedbackApi.validate(token)
      .then(setTokenInfo)
      .catch(() => setTokenInfo({ valid: false }))
      .finally(() => setValidating(false));
  }, [token]);

  function allRated() {
    return Object.values(ratings).every((v) => v > 0);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!allRated()) {
      toast.error("Please rate all 6 dimensions before submitting");
      return;
    }
    setSubmitting(true);
    try {
      await feedbackApi.submit({
        token,
        ...ratings,
        free_text_positive: textPositive || null,
        free_text_improve: textImprove || null,
        free_text_overall: textOverall || null,
        is_anonymous: isAnonymous,
      });
      setSubmitted(true);
    } catch (e: any) {
      const detail = e.response?.data?.detail || "Submission failed";
      if (detail.includes("already") || e.response?.status === 409) {
        setTokenInfo({ valid: false, already_submitted: true });
      } else {
        toast.error(detail);
      }
    } finally {
      setSubmitting(false);
    }
  }

  async function toggleRecording() {
    if (isRecording) {
      mediaRecorderRef.current?.stop();
      setIsRecording(false);
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream);
      chunksRef.current = [];
      mr.ondataavailable = (e) => chunksRef.current.push(e.data);
      mr.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        setAudioBlob(blob);
        stream.getTracks().forEach((t) => t.stop());
      };
      mr.start();
      mediaRecorderRef.current = mr;
      setIsRecording(true);
    } catch {
      toast.error("Microphone access denied");
    }
  }

  // ── States ────────────────────────────────────────────────────────────────

  if (validating) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <Loader2 className="w-8 h-8 text-blue-600 animate-spin" />
      </div>
    );
  }

  if (!tokenInfo?.valid) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 p-4">
        <div className="max-w-md w-full bg-white rounded-2xl border border-slate-200 shadow-card p-10 text-center">
          <div className="w-14 h-14 rounded-full bg-red-50 flex items-center justify-center mx-auto mb-4">
            <XCircle className="w-8 h-8 text-red-500" />
          </div>
          <h2 className="text-lg font-semibold text-slate-900 mb-2">
            {tokenInfo?.already_submitted
              ? "Feedback Already Submitted"
              : tokenInfo?.expired
              ? "Link Expired"
              : "Invalid Link"}
          </h2>
          <p className="text-sm text-slate-500">
            {tokenInfo?.already_submitted
              ? "You have already submitted feedback for this training session. Each participant may only submit once."
              : tokenInfo?.expired
              ? "This feedback link has expired. Please contact your HR department if you need a new link."
              : "This feedback link is not valid. Please check your email for the correct link."}
          </p>
        </div>
      </div>
    );
  }

  if (submitted) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 p-4">
        <div className="max-w-md w-full bg-white rounded-2xl border border-slate-200 shadow-card p-10 text-center">
          <div className="w-14 h-14 rounded-full bg-emerald-50 flex items-center justify-center mx-auto mb-4">
            <CheckCircle className="w-8 h-8 text-emerald-500" />
          </div>
          <h2 className="text-lg font-semibold text-slate-900 mb-2">Thank You!</h2>
          <p className="text-sm text-slate-500">
            Your feedback has been recorded successfully. Your insights directly improve training quality for your organization.
          </p>
          <p className="text-xs text-slate-400 mt-4">You may now close this window.</p>
        </div>
      </div>
    );
  }

  // ── Form ──────────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-slate-50 py-10 px-4">
      <div className="max-w-2xl mx-auto">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-10 h-10 rounded-xl bg-blue-600 mb-3">
            <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          </div>
          <h1 className="text-xl font-bold text-slate-900">Training Feedback</h1>
          <p className="text-sm text-slate-500 mt-1">
            {tokenInfo.batch_title} · {tokenInfo.trainer_name}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Ratings */}
          <div className="bg-white rounded-2xl border border-slate-200 shadow-card divide-y divide-slate-100">
            <div className="px-6 py-4">
              <h2 className="text-sm font-semibold text-slate-800">Performance Ratings</h2>
              <p className="text-xs text-slate-500 mt-0.5">Rate each dimension from 1 (Poor) to 5 (Excellent)</p>
            </div>
            {RATING_DIMENSIONS.map((dim) => (
              <div key={dim.key} className="px-6 py-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-slate-800">{dim.label}</p>
                    <p className="text-xs text-slate-400 mt-0.5">{dim.desc}</p>
                  </div>
                  <StarRating
                    value={ratings[dim.key]}
                    onChange={(v) => setRatings((r) => ({ ...r, [dim.key]: v }))}
                  />
                </div>
              </div>
            ))}
          </div>

          {/* Text Feedback */}
          <div className="bg-white rounded-2xl border border-slate-200 shadow-card divide-y divide-slate-100">
            <div className="px-6 py-4">
              <h2 className="text-sm font-semibold text-slate-800">Written Feedback</h2>
              <p className="text-xs text-slate-500 mt-0.5">Optional — all fields are optional below</p>
            </div>

            <div className="px-6 py-4 space-y-1">
              <label className="text-xs font-medium text-slate-700">What did you find most valuable?</label>
              <textarea
                value={textPositive}
                onChange={(e) => setTextPositive(e.target.value)}
                maxLength={2000}
                rows={2}
                placeholder="e.g., The hands-on labs were excellent and directly applicable…"
                className="w-full text-sm bg-slate-50 border border-slate-200 rounded-lg px-4 py-2.5 text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-400 resize-none"
              />
            </div>

            <div className="px-6 py-4 space-y-1">
              <label className="text-xs font-medium text-slate-700">What could be improved?</label>
              <textarea
                value={textImprove}
                onChange={(e) => setTextImprove(e.target.value)}
                maxLength={2000}
                rows={2}
                placeholder="e.g., More time for Q&A would have been helpful…"
                className="w-full text-sm bg-slate-50 border border-slate-200 rounded-lg px-4 py-2.5 text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-400 resize-none"
              />
            </div>

            <div className="px-6 py-4 space-y-1">
              <label className="text-xs font-medium text-slate-700">Overall impressions</label>
              <textarea
                value={textOverall}
                onChange={(e) => setTextOverall(e.target.value)}
                maxLength={2000}
                rows={3}
                placeholder="Share any additional thoughts about the training session…"
                className="w-full text-sm bg-slate-50 border border-slate-200 rounded-lg px-4 py-2.5 text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-400 resize-none"
              />
            </div>
          </div>

          {/* Audio + Anonymity */}
          <div className="bg-white rounded-2xl border border-slate-200 shadow-card px-6 py-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-slate-800">Voice Note (Optional)</p>
                <p className="text-xs text-slate-500">Record additional verbal feedback</p>
              </div>
              <div className="flex items-center gap-3">
                {audioBlob && <span className="text-xs text-emerald-600 font-medium">Recorded ✓</span>}
                <button
                  type="button"
                  onClick={toggleRecording}
                  className={`p-2.5 rounded-lg transition-colors ${
                    isRecording
                      ? "bg-red-100 text-red-600 hover:bg-red-200"
                      : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                  }`}
                >
                  {isRecording ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <div className="mt-4 flex items-center gap-3">
              <button
                type="button"
                role="switch"
                aria-checked={isAnonymous}
                onClick={() => setIsAnonymous(!isAnonymous)}
                className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
                  isAnonymous ? "bg-blue-600" : "bg-slate-200"
                }`}
              >
                <span className={`inline-block h-3.5 w-3.5 rounded-full bg-white shadow transition-transform ${
                  isAnonymous ? "translate-x-4" : "translate-x-0.5"
                }`} />
              </button>
              <div>
                <p className="text-sm font-medium text-slate-800">Submit Anonymously</p>
                <p className="text-xs text-slate-500">Your name will not be attached to this submission</p>
              </div>
            </div>
          </div>

          {/* Submit */}
          <button
            type="submit"
            disabled={submitting || !allRated()}
            className="w-full py-3.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed text-white font-semibold rounded-xl text-sm transition-colors flex items-center justify-center gap-2"
          >
            {submitting ? (
              <><Loader2 className="w-4 h-4 animate-spin" /> Submitting…</>
            ) : (
              <><Send className="w-4 h-4" /> Submit Feedback</>
            )}
          </button>

          {!allRated() && (
            <p className="text-xs text-center text-slate-400">Please rate all 6 dimensions to enable submission</p>
          )}

          <p className="text-xs text-center text-slate-400 pb-4">
            This link is single-use and unique to you. Bilvantis Training Intelligence Platform.
          </p>
        </form>
      </div>
    </div>
  );
}
