"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { 
  ArrowLeft,
  Download,
  Copy,
  Check,
  TrendingUp,
  TrendingDown,
  BarChart3
} from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

interface Strategy {
  id: number;
  job_id: number;
  version: number;
  name: string;
  pine_script: string;
  ai_reasoning: string | null;
  win_rate: number | null;
  profit_factor: number | null;
  max_drawdown: number | null;
  net_profit: number | null;
  total_trades: number | null;
  sharpe_ratio: number | null;
  score: number | null;
  created_at: string;
}

export default function StrategyDetailPage() {
  const params = useParams();
  const router = useRouter();
  const strategyId = Number(params.id);
  
  const [strategy, setStrategy] = useState<Strategy | null>(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    loadStrategy();
  }, [strategyId]);

  const loadStrategy = async () => {
    try {
      const data = await api.getStrategy(strategyId);
      setStrategy(data as Strategy);
    } catch {
      router.push("/strategies");
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = () => {
    if (!strategy) return;
    navigator.clipboard.writeText(strategy.pine_script);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = async () => {
    if (!strategy) return;
    const blob = new Blob([strategy.pine_script], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${strategy.name.replace(/\s+/g, "_")}_v${strategy.version}.pine`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="animate-spin h-8 w-8 border-2 border-primary border-t-transparent rounded-full" />
      </div>
    );
  }

  if (!strategy) {
    return null;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link
          href="/strategies"
          className="p-2 hover:bg-secondary rounded-lg transition"
        >
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <div className="flex-1">
          <h1 className="text-2xl font-bold">{strategy.name}</h1>
          <p className="text-muted-foreground">
            Version {strategy.version} • {new Date(strategy.created_at).toLocaleDateString()}
          </p>
        </div>
        <button
          onClick={handleCopy}
          className="flex items-center gap-2 px-4 py-2 bg-secondary text-foreground rounded-lg hover:bg-secondary/80 transition"
        >
          {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
          {copied ? "Copied!" : "Copy"}
        </button>
        <button
          onClick={handleDownload}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition"
        >
          <Download className="h-4 w-4" />
          Download
        </button>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard
          label="Win Rate"
          value={strategy.win_rate !== null ? `${strategy.win_rate.toFixed(1)}%` : "—"}
          color={strategy.win_rate !== null && strategy.win_rate >= 60 ? "green" : 
                 strategy.win_rate !== null && strategy.win_rate >= 50 ? "yellow" : "red"}
          icon={<TrendingUp className="h-5 w-5" />}
        />
        <MetricCard
          label="Profit Factor"
          value={strategy.profit_factor !== null ? strategy.profit_factor.toFixed(2) : "—"}
          color={strategy.profit_factor !== null && strategy.profit_factor >= 1.5 ? "green" : 
                 strategy.profit_factor !== null && strategy.profit_factor >= 1 ? "yellow" : "red"}
          icon={<BarChart3 className="h-5 w-5" />}
        />
        <MetricCard
          label="Max Drawdown"
          value={strategy.max_drawdown !== null ? `${strategy.max_drawdown.toFixed(1)}%` : "—"}
          color={strategy.max_drawdown !== null && strategy.max_drawdown <= 15 ? "green" : 
                 strategy.max_drawdown !== null && strategy.max_drawdown <= 25 ? "yellow" : "red"}
          icon={<TrendingDown className="h-5 w-5" />}
        />
        <MetricCard
          label="Score"
          value={strategy.score !== null ? strategy.score.toFixed(1) : "—"}
          color="primary"
          icon={<TrendingUp className="h-5 w-5" />}
        />
      </div>

      {/* Additional Metrics */}
      {(strategy.net_profit !== null || strategy.total_trades !== null || strategy.sharpe_ratio !== null) && (
        <div className="grid grid-cols-3 gap-4">
          {strategy.net_profit !== null && (
            <div className="glass rounded-xl p-4">
              <div className="text-sm text-muted-foreground mb-1">Net Profit</div>
              <div className={cn(
                "text-xl font-bold",
                strategy.net_profit >= 0 ? "text-green-500" : "text-red-500"
              )}>
                ${strategy.net_profit.toFixed(2)}
              </div>
            </div>
          )}
          {strategy.total_trades !== null && (
            <div className="glass rounded-xl p-4">
              <div className="text-sm text-muted-foreground mb-1">Total Trades</div>
              <div className="text-xl font-bold">{strategy.total_trades}</div>
            </div>
          )}
          {strategy.sharpe_ratio !== null && (
            <div className="glass rounded-xl p-4">
              <div className="text-sm text-muted-foreground mb-1">Sharpe Ratio</div>
              <div className="text-xl font-bold">{strategy.sharpe_ratio.toFixed(2)}</div>
            </div>
          )}
        </div>
      )}

      {/* AI Reasoning */}
      {strategy.ai_reasoning && (
        <div className="glass rounded-xl p-6">
          <h2 className="font-semibold mb-3">AI Reasoning</h2>
          <p className="text-muted-foreground whitespace-pre-wrap">{strategy.ai_reasoning}</p>
        </div>
      )}

      {/* Pine Script Code */}
      <div className="glass rounded-xl p-6">
        <h2 className="font-semibold mb-3">Pine Script Code</h2>
        <pre className="bg-secondary/50 rounded-lg p-4 overflow-x-auto text-sm font-mono max-h-[500px] overflow-y-auto">
          <code>{strategy.pine_script}</code>
        </pre>
      </div>
    </div>
  );
}

function MetricCard({
  label,
  value,
  color,
  icon,
}: {
  label: string;
  value: string;
  color: "green" | "yellow" | "red" | "primary";
  icon: React.ReactNode;
}) {
  const colorClasses = {
    green: "text-green-500",
    yellow: "text-yellow-500",
    red: "text-red-500",
    primary: "text-primary",
  };

  return (
    <div className="glass rounded-xl p-4">
      <div className="flex items-center gap-2 text-muted-foreground mb-2">
        {icon}
        <span className="text-sm">{label}</span>
      </div>
      <div className={cn("text-2xl font-bold", colorClasses[color])}>
        {value}
      </div>
    </div>
  );
}
