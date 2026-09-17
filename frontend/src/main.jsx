import React from "react";
import ReactDOM from "react-dom/client";
import { marked } from "marked";
import "./styles.css";

const prompts = [
  {
    label: "Japan Trip",
    text: "Plan a complete 7 days Japan trip from India including flights, hotels and sightseeing under 2 lakhs.",
    icon: "⛩️",
  },
  {
    label: "Dubai Trip",
    text: "Plan a 5 days Dubai trip from India with flights, hotels and sightseeing.",
    icon: "🏙️",
  },
  {
    label: "Thailand Trip",
    text: "Plan a 7 days Thailand trip from India with budget hotels and sightseeing.",
    icon: "🏝️",
  },
  {
    label: "Global Flights",
    text: "Give me all country flight info.",
    icon: "✈️",
  },
];

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

function App() {
  const [message, setMessage] = React.useState("");
  const [threadId, setThreadId] = React.useState(
    localStorage.getItem("travel_thread_id") || "",
  );
  const [answer, setAnswer] = React.useState("");
  const [missingSlots, setMissingSlots] = React.useState([]);
  const [formAnswers, setFormAnswers] = React.useState({});
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState("");

  const requestPlan = async (payload) => {
    const response = await fetch(`${apiBaseUrl}/api/travel`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const body = await response.text();
    let data;

    try {
      data = body ? JSON.parse(body) : null;
    } catch {
      throw new Error(response.ok ? "The server returned an invalid response." : `Request failed (${response.status}).`);
    }

    if (!response.ok || !data?.success) throw new Error(data?.error || "Something went wrong.");

    setThreadId(data.thread_id);
    localStorage.setItem("travel_thread_id", data.thread_id);
    setMissingSlots(data.missing_slots || []);
    setFormAnswers({});
    setAnswer(data.status === "ready" ? data.answer : "");
  };

  const sendMessage = async () => {
    const trimmed = message.trim();
    if (!trimmed) {
      setError("Please enter your travel request first.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      await requestPlan({ message: trimmed, thread_id: threadId || null });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const submitClarifications = async () => {
    const unanswered = missingSlots.find((slot) => !formAnswers[slot.key] || (Array.isArray(formAnswers[slot.key]) && !formAnswers[slot.key].length));
    if (unanswered) {
      setError(`Please answer: ${unanswered.label}`);
      return;
    }
    setLoading(true);
    setError("");
    try {
      await requestPlan({ thread_id: threadId, answers: formAnswers });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const selectOption = (slot, option) => {
    if (!slot.multiple) {
      setFormAnswers((current) => ({ ...current, [slot.key]: option }));
      return;
    }
    setFormAnswers((current) => {
      const selected = current[slot.key] || [];
      return { ...current, [slot.key]: selected.includes(option) ? selected.filter((item) => item !== option) : [...selected, option] };
    });
  };

  const copyResult = async () => {
    const text = document.getElementById("resultBox")?.innerText || "";
    if (text) await navigator.clipboard.writeText(text);
  };

  const downloadPDF = () => window.print();

  return (
    <div className="min-h-screen overflow-x-hidden bg-[#050b18] text-slate-100 font-body antialiased selection:bg-blue-500/30 selection:text-blue-200">
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,600;1,9..144,400&family=Inter:wght@300;400;500;600;700&display=swap');
        .font-display { font-family: 'Fraunces', serif; }
        .font-body { font-family: 'Inter', sans-serif; }
        
        .ticket-edge {
          background-image: repeating-linear-gradient(90deg, transparent, transparent 6px, rgba(203, 213, 225, 0.6) 6px, rgba(203, 213, 225, 0.6) 12px);
          height: 1px;
        }

        .glow-button {
          box-shadow: 0 0 25px -3px rgba(37, 99, 235, 0.5), 0 0 10px -2px rgba(29, 78, 216, 0.3);
        }
        .glow-button:hover:not(:disabled) {
          box-shadow: 0 0 35px 2px rgba(37, 99, 235, 0.7), 0 0 15px 0px rgba(29, 78, 216, 0.4);
        }

        @keyframes pulse-slow {
          0%, 100% { opacity: 0.4; transform: scale(1); }
          50% { opacity: 0.7; transform: scale(1.05); }
        }
        .animate-pulse-glow {
          animation: pulse-slow 8s infinite ease-in-out;
        }

        /* Custom Structured Markdown Styling inside the light container */
        .travel-markdown h1, 
        .travel-markdown h2, 
        .travel-markdown h3 {
          color: #0f172a;
          font-weight: 700;
          margin-top: 1.5em;
          margin-bottom: 0.5em;
        }
        .travel-markdown h2 {
          border-bottom: 2px solid #e2e8f0;
          padding-bottom: 0.3em;
        }
        .travel-markdown table {
          width: 100%;
          border-collapse: collapse;
          margin: 1.25em 0;
          font-size: 0.95rem;
        }
        .travel-markdown th {
          background-color: #f1f5f9;
          color: #0f172a;
          font-weight: 600;
          text-align: left;
          padding: 10px 14px;
          border: 1px solid #cbd5e1;
        }
        .travel-markdown td {
          padding: 10px 14px;
          border: 1px solid #e2e8f0;
          color: #334155;
        }
        .travel-markdown tr:nth-child(even) {
          background-color: #f8fafc;
        }
        .travel-markdown ul, .travel-markdown ol {
          padding-left: 1.5rem;
          margin: 1rem 0;
          color: #334155;
        }
        .travel-markdown li {
          margin-bottom: 0.4rem;
        }
        .travel-markdown blockquote {
          border-left: 4px solid #2563eb;
          background-color: #eff6ff;
          padding: 0.75rem 1rem;
          color: #1e3a8a;
          border-radius: 0 0.5rem 0.5rem 0;
          margin: 1.25rem 0;
        }
      `}</style>

      {/* Ambient background glows */}
      <div className="fixed inset-0 -z-10 overflow-hidden pointer-events-none">
        <div className="animate-pulse-glow absolute -top-40 left-1/2 -translate-x-1/2 w-[800px] h-[500px] bg-blue-600/15 blur-[140px] rounded-full" />
        <div className="absolute top-1/3 -right-40 w-[600px] h-[600px] bg-indigo-600/15 blur-[160px] rounded-full" />
        <div className="absolute bottom-10 -left-40 w-[600px] h-[600px] bg-cyan-600/10 blur-[160px] rounded-full" />
      </div>

      <div className="mx-auto w-[min(1080px,calc(100%-32px))] py-12 md:py-20">
        {/* Header Section */}
        <header className="mb-12 text-center relative">
          <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-blue-500/30 bg-blue-950/40 px-4 py-1.5 text-xs font-semibold uppercase tracking-widest text-blue-300 backdrop-blur-md">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500"></span>
            </span>
            TripPilot AI Engine
          </div>
          <h1 className="font-display mb-4 text-5xl font-medium tracking-tight text-white sm:text-7xl">
            Your next trip,{" "}
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-300 via-blue-400 to-indigo-300">
              planned
            </span>
            .
          </h1>
          <p className="mx-auto max-w-xl text-base sm:text-lg leading-relaxed text-slate-400">
            Smart, custom itineraries tailored to your budget, flight details,
            and local highlights.
          </p>
        </header>

        {/* Input Card */}
        <section className="rounded-3xl border border-blue-500/20 bg-slate-900/60 p-6 sm:p-8 shadow-2xl backdrop-blur-xl relative overflow-hidden group">
          <div className="absolute top-0 left-0 right-0 h-[1px] bg-gradient-to-r from-transparent via-blue-500/40 to-transparent" />

          <div className="mb-6 flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
            <div>
              <h2 className="font-display text-2xl font-medium text-white flex items-center gap-2">
                Where do you want to go?
              </h2>
              <p className="text-sm text-slate-400">
                Describe your destination, origin, duration, and target budget.
              </p>
            </div>
            <div className="self-start sm:self-auto inline-flex items-center gap-2 rounded-full border border-blue-500/30 bg-blue-500/10 px-3 py-1 text-xs font-medium text-blue-300 backdrop-blur-sm">
              <span className="h-2 w-2 rounded-full bg-blue-400 shadow-[0_0_8px_#3b82f6]" />
              AI Assistant Ready
            </div>
          </div>

          <div className="flex flex-col gap-4">
            <div className="relative">
              <textarea
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="e.g. Plan a complete 7 days Japan trip from India including flights, hotels and sightseeing under 2 lakhs..."
                className="min-h-36 w-full resize-y rounded-2xl border border-blue-500/20 bg-[#070e20]/80 p-5 text-base leading-relaxed text-slate-100 placeholder:text-slate-500 outline-none transition focus:border-blue-500/60 focus:ring-4 focus:ring-blue-500/15"
              />
            </div>

            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              {/* Quick Prompts */}
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-medium text-slate-500 uppercase tracking-wider mr-1">
                  Suggestions:
                </span>
                {prompts.map((p) => (
                  <button
                    key={p.label}
                    onClick={() => setMessage(p.text)}
                    className="inline-flex items-center gap-1.5 rounded-xl border border-blue-500/20 bg-blue-950/20 px-3 py-1.5 text-xs font-medium text-slate-300 transition hover:border-blue-400/50 hover:bg-blue-600/10 hover:text-blue-200 active:scale-95"
                  >
                    <span>{p.icon}</span>
                    <span>{p.label}</span>
                  </button>
                ))}
              </div>

              {/* Dark Blue Generate Button */}
              <button
                onClick={sendMessage}
                disabled={loading}
                className="glow-button group relative min-w-[180px] overflow-hidden rounded-xl bg-gradient-to-r from-blue-700 via-blue-600 to-indigo-700 px-6 py-3.5 font-bold text-white transition-all duration-200 hover:scale-[1.02] active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:scale-100"
              >
                <div className="relative z-10 flex items-center justify-center gap-2">
                  {loading ? (
                    <>
                      <svg
                        className="h-5 w-5 animate-spin text-white"
                        fill="none"
                        viewBox="0 0 24 24"
                      >
                        <circle
                          className="opacity-25"
                          cx="12"
                          cy="12"
                          r="10"
                          stroke="currentColor"
                          strokeWidth="4"
                        />
                        <path
                          className="opacity-75"
                          fill="currentColor"
                          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                        />
                      </svg>
                      <span>Generating...</span>
                    </>
                  ) : (
                    <>
                      <span>Generate Plan</span>
                      <svg
                        className="h-4 w-4 transition-transform duration-200 group-hover:translate-x-1"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                        strokeWidth="2.5"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3"
                        />
                      </svg>
                    </>
                  )}
                </div>
              </button>
            </div>
          </div>
        </section>

        {/* Error Alert */}
        {error && (
          <div className="mt-6 flex items-center gap-3 rounded-2xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200 backdrop-blur-md">
            <svg
              className="h-5 w-5 shrink-0 text-red-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
            <span>{error}</span>
          </div>
        )}

        {missingSlots.length > 0 && (
          <section className="mt-6 rounded-3xl border border-amber-400/30 bg-slate-900/80 p-6 shadow-2xl backdrop-blur-xl sm:p-8">
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-amber-300">One quick check</p>
            <h2 className="mt-2 font-display text-2xl text-white">Complete your trip details</h2>
            <p className="mt-2 text-sm text-slate-400">Your plan is paused. It will continue automatically after these answers.</p>
            <div className="mt-6 grid gap-5 sm:grid-cols-2">
              {missingSlots.map((slot) => (
                <div key={slot.key} className={slot.options ? "sm:col-span-2" : ""}>
                  <label className="mb-2 block text-sm font-semibold text-slate-200">{slot.label}</label>
                  {slot.options ? (
                    <div className="flex flex-wrap gap-2">
                      {slot.options.map((option) => {
                        const selected = slot.multiple ? (formAnswers[slot.key] || []).includes(option) : formAnswers[slot.key] === option;
                        return (
                          <button key={option} type="button" onClick={() => selectOption(slot, option)} className={`rounded-xl border px-4 py-2 text-sm font-medium transition ${selected ? "border-blue-400 bg-blue-600 text-white" : "border-slate-600 bg-slate-800 text-slate-300 hover:border-blue-400"}`}>
                            {option}
                          </button>
                        );
                      })}
                    </div>
                  ) : (
                    <input
                      value={formAnswers[slot.key] || ""}
                      onChange={(event) => setFormAnswers((current) => ({ ...current, [slot.key]: event.target.value }))}
                      placeholder={slot.key === "duration_days" ? "e.g. 5" : slot.key === "travel_dates" ? "e.g. 12-16 October 2026" : "Enter your answer"}
                      type={slot.key === "duration_days" ? "number" : "text"}
                      min={slot.key === "duration_days" ? "1" : undefined}
                      className="w-full rounded-xl border border-slate-600 bg-slate-950 px-4 py-3 text-slate-100 outline-none focus:border-blue-400 focus:ring-4 focus:ring-blue-500/15"
                    />
                  )}
                </div>
              ))}
            </div>
            <button onClick={submitClarifications} disabled={loading} className="mt-7 rounded-xl bg-gradient-to-r from-blue-700 to-indigo-700 px-6 py-3 font-bold text-white disabled:opacity-60">
              {loading ? "Continuing..." : "Continue planning"}
            </button>
          </section>
        )}

        {/* Structured White Result Container */}
        {answer && (
          <section className="mt-10 overflow-hidden rounded-3xl bg-white text-slate-900 shadow-2xl ring-1 ring-slate-900/10">
            {/* Header Toolbar */}
            <div className="flex flex-col gap-4 bg-slate-50 p-6 sm:p-8 pb-5 sm:flex-row sm:items-center sm:justify-between border-b border-slate-200">
              <div>
                <h2 className="font-display text-2xl font-bold text-slate-900 flex items-center gap-2">
                  🗺️ Your Custom Itinerary
                </h2>
                <p className="text-xs font-mono text-slate-500 mt-1">
                  Thread ID: {threadId || "N/A"}
                </p>
              </div>
              <div className="flex items-center gap-3">
                <button
                  onClick={copyResult}
                  className="inline-flex items-center gap-2 rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50 hover:text-slate-900 active:scale-95"
                >
                  <svg
                    className="h-4 w-4"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth="2"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
                    />
                  </svg>
                  Copy
                </button>
                <button
                  onClick={downloadPDF}
                  className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-4 py-2 text-sm font-bold text-white transition hover:bg-blue-700 active:scale-95 shadow-md"
                >
                  <svg
                    className="h-4 w-4"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth="2.5"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z"
                    />
                  </svg>
                  Print / Save PDF
                </button>
              </div>
            </div>

            <div className="ticket-edge mx-6 sm:mx-8" />

            {/* Markdown Itinerary Body */}
            <div className="p-6 sm:p-10" id="resultBox">
              <div
                className="travel-markdown prose max-w-none prose-slate prose-p:text-slate-700 prose-strong:text-slate-900 prose-a:text-blue-600"
                dangerouslySetInnerHTML={{ __html: marked.parse(answer) }}
              />
            </div>
          </section>
        )}

        <footer className="mt-16 text-center text-xs text-slate-600">
          TripPilot AI • Crafted for smart travel and precise budgets.
        </footer>
      </div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
