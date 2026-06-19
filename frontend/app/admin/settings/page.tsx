"use client";
import { useState } from "react";
import { Settings, Mail, Lock, Sliders, Save, Send, CheckCircle, Loader2, Info, Eye, EyeOff } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";

export default function SettingsPage() {
  const [smtp, setSmtp] = useState({
    host: "smtp.gmail.com",
    port: "587",
    user: "",
    password: "",
    from_email: "",
    from_name: "Bilvantis TIP",
  });
  const [testEmail, setTestEmail] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [testing, setTesting] = useState(false);
  const [saving, setSaving] = useState(false);

  async function handleTestEmail() {
    if (!testEmail) { toast.error("Enter a test email address"); return; }
    setTesting(true);
    try {
      await api.post("/settings/test-email", { to_email: testEmail, ...smtp });
      toast.success(`Test email sent to ${testEmail}`);
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Email test failed — check SMTP credentials in .env");
    } finally {
      setTesting(false);
    }
  }

  async function handleSave() {
    setSaving(true);
    setTimeout(() => {
      setSaving(false);
      toast.success("Settings noted — update your backend .env file to persist changes");
    }, 800);
  }

  return (
    <div className="space-y-6 animate-fade-in max-w-3xl">
      <div>
        <h1 className="page-title flex items-center gap-2">
          <Settings className="w-6 h-6 text-blue-600" /> Settings
        </h1>
        <p className="text-sm text-slate-500 mt-1">Configure email delivery and platform behavior</p>
      </div>

      {/* SMTP Email Config */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-card">
        <div className="px-6 py-4 border-b border-slate-100 flex items-center gap-2">
          <Mail className="w-4 h-4 text-slate-400" />
          <h3 className="font-semibold text-slate-800 text-sm">Email Configuration (SMTP)</h3>
        </div>
        <div className="p-6 space-y-4">
          <div className="bg-blue-50 border border-blue-100 rounded-lg p-4 flex gap-3">
            <Info className="w-4 h-4 text-blue-500 shrink-0 mt-0.5" />
            <div className="text-sm text-blue-700">
              <p className="font-medium mb-1">Gmail Setup</p>
              <p>Use <strong>smtp.gmail.com</strong> port 587 with a Gmail App Password (not your regular password). Enable 2FA then create an App Password at <em>myaccount.google.com → Security → App passwords</em>. Update these values in your <code className="font-mono bg-blue-100 px-1 rounded">.env</code> file on the server.</p>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1.5">SMTP Host</label>
              <input
                value={smtp.host}
                onChange={(e) => setSmtp({ ...smtp, host: e.target.value })}
                className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="smtp.gmail.com"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1.5">Port</label>
              <input
                value={smtp.port}
                onChange={(e) => setSmtp({ ...smtp, port: e.target.value })}
                className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="587"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1.5">Gmail Address (SMTP_USER)</label>
              <input
                type="email"
                value={smtp.user}
                onChange={(e) => setSmtp({ ...smtp, user: e.target.value })}
                className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="yourname@gmail.com"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1.5">App Password (SMTP_PASSWORD)</label>
              <div className="relative">
                <input
                  type={showPassword ? "text" : "password"}
                  value={smtp.password}
                  onChange={(e) => setSmtp({ ...smtp, password: e.target.value })}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 pr-9 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="xxxx xxxx xxxx xxxx"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                >
                  {showPassword ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                </button>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1.5">From Email</label>
              <input
                type="email"
                value={smtp.from_email}
                onChange={(e) => setSmtp({ ...smtp, from_email: e.target.value })}
                className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="noreply@bilvantis.io"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1.5">From Name</label>
              <input
                value={smtp.from_name}
                onChange={(e) => setSmtp({ ...smtp, from_name: e.target.value })}
                className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Bilvantis TIP"
              />
            </div>
          </div>

          <div className="pt-2 border-t border-slate-100">
            <label className="block text-xs font-medium text-slate-700 mb-1.5">Send Test Email</label>
            <div className="flex gap-2">
              <input
                type="email"
                value={testEmail}
                onChange={(e) => setTestEmail(e.target.value)}
                className="flex-1 border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="lukalapusaikumar1@gmail.com"
              />
              <button
                onClick={handleTestEmail}
                disabled={testing}
                className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
              >
                {testing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                Test
              </button>
            </div>
            <p className="text-xs text-slate-400 mt-1.5">Note: SMTP credentials must first be set in the server <code className="font-mono">.env</code> file to actually send emails.</p>
          </div>
        </div>
      </div>

      {/* Platform config reference */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-card">
        <div className="px-6 py-4 border-b border-slate-100 flex items-center gap-2">
          <Sliders className="w-4 h-4 text-slate-400" />
          <h3 className="font-semibold text-slate-800 text-sm">Platform Configuration</h3>
        </div>
        <div className="p-6 space-y-4">
          <div className="bg-slate-50 rounded-lg p-4 text-xs font-mono text-slate-600 space-y-1">
            <p className="text-slate-400 mb-2"># backend/.env — edit these values to configure the platform</p>
            <p>FEEDBACK_TOKEN_EXPIRE_HOURS=<span className="text-blue-600">72</span></p>
            <p>FEEDBACK_THRESHOLD=<span className="text-blue-600">5</span>  <span className="text-slate-400"># min responses to trigger AI pipeline</span></p>
            <p>SMTP_HOST=<span className="text-blue-600">smtp.gmail.com</span></p>
            <p>SMTP_PORT=<span className="text-blue-600">587</span></p>
            <p>SMTP_USER=<span className="text-amber-600">your-gmail@gmail.com</span></p>
            <p>SMTP_PASSWORD=<span className="text-amber-600">your-app-password</span></p>
            <p>SMTP_FROM_EMAIL=<span className="text-amber-600">your-gmail@gmail.com</span></p>
            <p>GROQ_API_KEY=<span className="text-emerald-600">gsk_u1KUobF7...</span>  <span className="text-slate-400"># already configured</span></p>
            <p>FRONTEND_URL=<span className="text-blue-600">http://localhost:3003</span></p>
          </div>
          <p className="text-xs text-slate-500">
            After updating the <code className="font-mono bg-slate-100 px-1 rounded">.env</code> file, restart the backend server for changes to take effect.
          </p>
        </div>
      </div>

      {/* Quick setup for test emails */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-card">
        <div className="px-6 py-4 border-b border-slate-100 flex items-center gap-2">
          <CheckCircle className="w-4 h-4 text-emerald-500" />
          <h3 className="font-semibold text-slate-800 text-sm">Test Email Addresses</h3>
        </div>
        <div className="p-6">
          <p className="text-sm text-slate-600 mb-3">These addresses are configured for testing the feedback email flow:</p>
          <div className="space-y-2">
            {[
              "lukalapusaikumar1@gmail.com",
              "lukalapusaikumargov@gmail.com",
              "pranavimaktha992@gmail.com",
              "lukalapusaikumaraws@gmail.com",
            ].map((email) => (
              <div key={email} className="flex items-center gap-3 py-2 border-b border-slate-50 last:border-0">
                <CheckCircle className="w-4 h-4 text-emerald-400 shrink-0" />
                <span className="font-mono text-sm text-slate-700">{email}</span>
                <button
                  onClick={() => setTestEmail(email)}
                  className="ml-auto text-xs text-blue-600 hover:underline"
                >
                  Use for test
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
