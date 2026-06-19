"use client";
import { useState, useRef, useEffect } from "react";
import { analyticsApi, trainersApi, batchesApi } from "@/lib/api";
import { MessageSquareCode, Send, Loader2, Bot, User, Trash2, Info } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: string[];
  confidence?: number;
  ts: number;
}

const SUGGESTED = [
  "Which trainer has the highest overall rating this quarter?",
  "What are the most common themes in negative feedback?",
  "Which training program needs improvement and why?",
  "Summarize feedback trends for the last 3 months",
  "What are participants saying about communication skills?",
  "Compare trainer performance across all batches",
];

export default function AiChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [trainers, setTrainers] = useState<any[]>([]);
  const [selectedTrainer, setSelectedTrainer] = useState<string>("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    trainersApi.list({ page_size: 50 }).then((d) => setTrainers(d.items || [])).catch(() => {});
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function send(question: string) {
    if (!question.trim() || loading) return;
    const userMsg: Message = { role: "user", content: question, ts: Date.now() };
    setMessages((m) => [...m, userMsg]);
    setInput("");
    setLoading(true);
    try {
      const res = await analyticsApi.chat({
        question,
        trainer_id: selectedTrainer || undefined,
        time_range_days: 90,
      });
      const aiMsg: Message = {
        role: "assistant",
        content: res.answer,
        sources: res.sources,
        confidence: res.confidence,
        ts: Date.now(),
      };
      setMessages((m) => [...m, aiMsg]);
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "AI response failed");
      setMessages((m) => [...m, {
        role: "assistant",
        content: "Sorry, I encountered an error. Please try again.",
        ts: Date.now(),
      }]);
    } finally {
      setLoading(false);
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    send(input);
  }

  return (
    <div className="flex flex-col h-[calc(100vh-3.5rem-3rem)] animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between mb-4 shrink-0">
        <div>
          <h1 className="page-title flex items-center gap-2">
            <MessageSquareCode className="w-6 h-6 text-blue-600" /> AI Analytics Chat
          </h1>
          <p className="text-sm text-slate-500 mt-1">Ask anything about training feedback powered by GROQ AI</p>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={selectedTrainer}
            onChange={(e) => setSelectedTrainer(e.target.value)}
            className="text-sm border border-slate-200 rounded-lg px-3 py-2 text-slate-700 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All Trainers</option>
            {trainers.map((t) => (
              <option key={t.id} value={t.id}>{t.full_name}</option>
            ))}
          </select>
          {messages.length > 0 && (
            <button
              onClick={() => setMessages([])}
              className="inline-flex items-center gap-1.5 px-3 py-2 bg-white border border-slate-200 text-slate-500 text-sm rounded-lg hover:bg-slate-50 transition-colors"
            >
              <Trash2 className="w-3.5 h-3.5" /> Clear
            </button>
          )}
        </div>
      </div>

      {/* Chat area */}
      <div className="flex-1 overflow-y-auto bg-white rounded-xl border border-slate-200 shadow-card p-4 space-y-4 mb-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center py-8">
            <div className="w-14 h-14 rounded-2xl bg-blue-600/10 flex items-center justify-center mb-4">
              <Bot className="w-7 h-7 text-blue-600" />
            </div>
            <p className="text-slate-700 font-semibold text-lg mb-1">Bilvantis AI Analytics</p>
            <p className="text-slate-400 text-sm max-w-sm mb-6">
              Ask me anything about trainer performance, feedback themes, or program insights. Powered by GROQ Llama 3.3.
            </p>
            <div className="grid grid-cols-2 gap-2 max-w-lg">
              {SUGGESTED.map((q) => (
                <button
                  key={q}
                  onClick={() => send(q)}
                  className="text-left text-xs bg-slate-50 hover:bg-blue-50 hover:border-blue-200 border border-slate-200 text-slate-600 hover:text-blue-700 rounded-lg px-3 py-2.5 transition-colors"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={cn("flex gap-3", msg.role === "user" ? "justify-end" : "justify-start")}>
            {msg.role === "assistant" && (
              <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center shrink-0 mt-0.5">
                <Bot className="w-4 h-4 text-white" />
              </div>
            )}
            <div className={cn(
              "max-w-[75%] rounded-2xl px-4 py-3",
              msg.role === "user"
                ? "bg-blue-600 text-white rounded-tr-sm"
                : "bg-slate-50 text-slate-800 rounded-tl-sm border border-slate-100"
            )}>
              <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.content}</p>
              {msg.confidence != null && (
                <div className="mt-2 flex items-center gap-1.5 text-xs text-slate-400">
                  <Info className="w-3 h-3" />
                  <span>Confidence: {Math.round(msg.confidence * 100)}%</span>
                </div>
              )}
              {msg.sources && msg.sources.length > 0 && (
                <div className="mt-2 text-xs text-slate-400">
                  Sources: {msg.sources.join(", ")}
                </div>
              )}
            </div>
            {msg.role === "user" && (
              <div className="w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center shrink-0 mt-0.5">
                <User className="w-4 h-4 text-slate-600" />
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="flex gap-3 justify-start">
            <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center shrink-0">
              <Bot className="w-4 h-4 text-white" />
            </div>
            <div className="bg-slate-50 border border-slate-100 rounded-2xl rounded-tl-sm px-4 py-3 flex items-center gap-2">
              <Loader2 className="w-4 h-4 text-blue-600 animate-spin" />
              <span className="text-sm text-slate-500">Analyzing with GROQ AI...</span>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="flex gap-3 shrink-0">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about feedback insights, trainer performance, themes..."
          className="flex-1 border border-slate-200 rounded-xl px-4 py-3 text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white shadow-sm"
          disabled={loading}
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="inline-flex items-center gap-2 px-5 py-3 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-xl transition-colors disabled:opacity-50 shadow-sm"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          Send
        </button>
      </form>
    </div>
  );
}
