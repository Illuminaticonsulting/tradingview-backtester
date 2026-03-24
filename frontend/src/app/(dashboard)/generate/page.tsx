"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { 
  Play, 
  Sparkles, 
  Target,
  Loader2,
  ChevronRight,
  AlertCircle
} from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

interface Watchlist {
  id: number;
  name: string;
  symbol_count: number;
}

const strategyTypes = [
  { id: "sma_bounce", name: "SMA Bounce", description: "Mean reversion on SMA touches" },
  { id: "rsi_reversal", name: "RSI Reversal", description: "Oversold/overbought reversals" },
  { id: "breakout", name: "Breakout", description: "Support/resistance breakouts" },
  { id: "trend_follow", name: "Trend Following", description: "Momentum-based entries" },
  { id: "custom", name: "Custom", description: "AI generates from scratch" },
];

const aiProviders = [
  { id: "deepseek", name: "DeepSeek R1", description: "Best value, deep reasoning" },
  { id: "claude", name: "Claude Sonnet", description: "High quality, more expensive" },
];

export default function GeneratePage() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [watchlists, setWatchlists] = useState<Watchlist[]>([]);
  const [credStatus, setCredStatus] = useState<{
    tv_cookies: { configured: boolean };
    deepseek_key: { configured: boolean };
    claude_key: { configured: boolean };
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  // Form state
  const [selectedWatchlist, setSelectedWatchlist] = useState<number | null>(null);
  const [selectedStrategy, setSelectedStrategy] = useState("sma_bounce");
  const [selectedProvider, setSelectedProvider] = useState("deepseek");
  const [jobName, setJobName] = useState("");
  const [targetWinRate, setTargetWinRate] = useState(60);
  const [targetProfitFactor, setTargetProfitFactor] = useState(150);
  const [targetMaxDrawdown, setTargetMaxDrawdown] = useState(20);
  const [maxIterations, setMaxIterations] = useState(10);

  useEffect(() => {
    Promise.all([
      api.getWatchlists().then(setWatchlists),
      api.getCredentialsStatus().then(setCredStatus),
    ]).finally(() => setLoading(false));
  }, []);

  const handleSubmit = async () => {
    if (!selectedWatchlist) return;
    
    setSubmitting(true);
    
    try {
      const job = await api.createJob({
        name: jobName || `${selectedStrategy}_${Date.now()}`,
        strategy_type: selectedStrategy,
        ai_provider: selectedProvider,
        watchlist_id: selectedWatchlist,
        target_win_rate: targetWinRate,
        target_profit_factor: targetProfitFactor,
        target_max_drawdown: targetMaxDrawdown,
        max_iterations: maxIterations,
      }) as { id: number };
      
      // Navigate to job page
      router.push(`/jobs/${job.id}`);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to create job");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  const missingCreds = !credStatus?.tv_cookies.configured || 
    (!credStatus?.deepseek_key.configured && !credStatus?.claude_key.configured);

  const availableProviders = aiProviders.filter(p => 
    p.id === "deepseek" ? credStatus?.deepseek_key.configured : credStatus?.claude_key.configured
  );

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Generate Strategy</h1>
        <p className="text-muted-foreground mt-1">
          Let AI create and optimize a trading strategy
        </p>
      </div>

      {/* Missing credentials warning */}
      {missingCreds && (
        <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-lg flex gap-3">
          <AlertCircle className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" />
          <div>
            <p className="font-medium text-red-500">Missing Credentials</p>
            <p className="text-sm text-muted-foreground">
              Configure TradingView cookies and at least one AI provider in Settings.
            </p>
          </div>
        </div>
      )}

      {/* Progress Steps */}
      <div className="flex items-center gap-2">
        {[1, 2, 3].map((s) => (
          <div
            key={s}
            className={cn(
              "flex-1 h-1 rounded-full transition",
              s <= step ? "bg-primary" : "bg-secondary"
            )}
          />
        ))}
      </div>

      {/* Step 1: Select Watchlist */}
      {step === 1 && (
        <div className="glass rounded-xl p-6 space-y-4">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <span className="w-7 h-7 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-sm">1</span>
            Select Watchlist
          </h2>
          
          {watchlists.length === 0 ? (
            <div className="p-4 bg-yellow-500/10 border border-yellow-500/20 rounded-lg">
              <p className="text-yellow-500">No watchlists found. Import one first.</p>
              <a href="/watchlists" className="text-sm text-primary hover:underline">
                Go to Watchlists →
              </a>
            </div>
          ) : (
            <div className="space-y-2">
              {watchlists.map((wl) => (
                <button
                  key={wl.id}
                  onClick={() => setSelectedWatchlist(wl.id)}
                  className={cn(
                    "w-full p-4 rounded-lg border text-left transition",
                    selectedWatchlist === wl.id
                      ? "border-primary bg-primary/10"
                      : "border-border hover:border-primary/50"
                  )}
                >
                  <div className="font-medium">{wl.name}</div>
                  <div className="text-sm text-muted-foreground">{wl.symbol_count} symbols</div>
                </button>
              ))}
            </div>
          )}
          
          <button
            onClick={() => setStep(2)}
            disabled={!selectedWatchlist}
            className="w-full flex items-center justify-center gap-2 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 disabled:opacity-50 transition"
          >
            Continue <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Step 2: Strategy & Provider */}
      {step === 2 && (
        <div className="glass rounded-xl p-6 space-y-6">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <span className="w-7 h-7 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-sm">2</span>
            Strategy Type
          </h2>
          
          <div className="grid grid-cols-2 gap-3">
            {strategyTypes.map((st) => (
              <button
                key={st.id}
                onClick={() => setSelectedStrategy(st.id)}
                className={cn(
                  "p-4 rounded-lg border text-left transition",
                  selectedStrategy === st.id
                    ? "border-primary bg-primary/10"
                    : "border-border hover:border-primary/50"
                )}
              >
                <div className="font-medium">{st.name}</div>
                <div className="text-sm text-muted-foreground">{st.description}</div>
              </button>
            ))}
          </div>

          <h3 className="text-lg font-semibold flex items-center gap-2 pt-4">
            <Sparkles className="h-5 w-5 text-primary" />
            AI Provider
          </h3>
          
          <div className="space-y-2">
            {availableProviders.map((p) => (
              <button
                key={p.id}
                onClick={() => setSelectedProvider(p.id)}
                className={cn(
                  "w-full p-4 rounded-lg border text-left transition",
                  selectedProvider === p.id
                    ? "border-primary bg-primary/10"
                    : "border-border hover:border-primary/50"
                )}
              >
                <div className="font-medium">{p.name}</div>
                <div className="text-sm text-muted-foreground">{p.description}</div>
              </button>
            ))}
          </div>
          
          <div className="flex gap-2">
            <button
              onClick={() => setStep(1)}
              className="px-4 py-2 text-muted-foreground hover:text-foreground transition"
            >
              Back
            </button>
            <button
              onClick={() => setStep(3)}
              className="flex-1 flex items-center justify-center gap-2 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition"
            >
              Continue <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}

      {/* Step 3: Targets & Launch */}
      {step === 3 && (
        <div className="glass rounded-xl p-6 space-y-6">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <span className="w-7 h-7 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-sm">3</span>
            Configure Targets
          </h2>
          
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">Job Name</label>
              <input
                type="text"
                value={jobName}
                onChange={(e) => setJobName(e.target.value)}
                placeholder={`${selectedStrategy}_strategy`}
                className="w-full px-4 py-2 bg-secondary border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium mb-1">
                  Target Win Rate: {targetWinRate}%
                </label>
                <input
                  type="range"
                  min="40"
                  max="80"
                  value={targetWinRate}
                  onChange={(e) => setTargetWinRate(Number(e.target.value))}
                  className="w-full"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium mb-1">
                  Target Profit Factor: {(targetProfitFactor / 100).toFixed(2)}
                </label>
                <input
                  type="range"
                  min="100"
                  max="300"
                  step="10"
                  value={targetProfitFactor}
                  onChange={(e) => setTargetProfitFactor(Number(e.target.value))}
                  className="w-full"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium mb-1">
                  Max Drawdown: {targetMaxDrawdown}%
                </label>
                <input
                  type="range"
                  min="5"
                  max="40"
                  value={targetMaxDrawdown}
                  onChange={(e) => setTargetMaxDrawdown(Number(e.target.value))}
                  className="w-full"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium mb-1">
                  Max Iterations: {maxIterations}
                </label>
                <input
                  type="range"
                  min="1"
                  max="20"
                  value={maxIterations}
                  onChange={(e) => setMaxIterations(Number(e.target.value))}
                  className="w-full"
                />
              </div>
            </div>
          </div>
          
          <div className="flex gap-2">
            <button
              onClick={() => setStep(2)}
              className="px-4 py-2 text-muted-foreground hover:text-foreground transition"
            >
              Back
            </button>
            <button
              onClick={handleSubmit}
              disabled={submitting || missingCreds}
              className="flex-1 flex items-center justify-center gap-2 py-3 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 disabled:opacity-50 transition font-medium"
            >
              {submitting ? (
                <Loader2 className="h-5 w-5 animate-spin" />
              ) : (
                <Play className="h-5 w-5" />
              )}
              Launch Strategy Generation
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
