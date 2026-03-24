"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { 
  FileCode, 
  Download, 
  TrendingUp,
  TrendingDown,
  Loader2,
  ArrowUpDown,
  ExternalLink
} from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

interface Strategy {
  id: number;
  job_id: number;
  version: number;
  name: string;
  pine_script: string;
  win_rate: number | null;
  profit_factor: number | null;
  max_drawdown: number | null;
  net_profit?: number | null;
  total_trades?: number | null;
  score: number | null;
  created_at: string;
}

export default function StrategiesPage() {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [loading, setLoading] = useState(true);
  const [sortBy, setSortBy] = useState("score");

  useEffect(() => {
    loadStrategies();
  }, [sortBy]);

  const loadStrategies = async () => {
    setLoading(true);
    try {
      const data = await api.getStrategies(sortBy);
      setStrategies(data.strategies);
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = async (strategy: Strategy) => {
    const content = await api.downloadStrategy(strategy.id);
    const blob = new Blob([content], { type: "text/plain" });
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
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Strategies</h1>
          <p className="text-muted-foreground mt-1">
            View and download generated Pine Scripts
          </p>
        </div>
        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value)}
          className="px-3 py-2 bg-secondary border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
        >
          <option value="score">Sort by Score</option>
          <option value="win_rate">Sort by Win Rate</option>
          <option value="profit_factor">Sort by Profit Factor</option>
          <option value="created_at">Sort by Date</option>
        </select>
      </div>

      {strategies.length === 0 ? (
        <div className="glass rounded-xl p-12 text-center">
          <FileCode className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
          <h3 className="text-lg font-medium mb-2">No strategies yet</h3>
          <p className="text-muted-foreground mb-4">
            Generate your first strategy to see it here
          </p>
          <Link
            href="/generate"
            className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition"
          >
            Generate Strategy
          </Link>
        </div>
      ) : (
        <div className="space-y-4">
          {strategies.map((strategy, i) => (
            <div
              key={strategy.id}
              className="glass rounded-xl p-4 hover:border-primary/30 transition"
            >
              <div className="flex items-start gap-4">
                <div className={cn(
                  "w-10 h-10 rounded-lg flex items-center justify-center font-bold",
                  i === 0 && "bg-yellow-500/20 text-yellow-500",
                  i === 1 && "bg-gray-400/20 text-gray-400",
                  i === 2 && "bg-amber-600/20 text-amber-600",
                  i > 2 && "bg-secondary text-muted-foreground"
                )}>
                  #{i + 1}
                </div>
                
                <div className="flex-1 min-w-0">
                  <Link
                    href={`/strategies/${strategy.id}`}
                    className="font-semibold hover:text-primary transition"
                  >
                    {strategy.name}
                  </Link>
                  <p className="text-sm text-muted-foreground">
                    Version {strategy.version} • {new Date(strategy.created_at).toLocaleDateString()}
                  </p>
                </div>

                <div className="flex items-center gap-6 text-sm">
                  {strategy.win_rate !== null && (
                    <div className="text-center">
                      <div className={cn(
                        "font-mono font-bold",
                        strategy.win_rate >= 60 ? "text-green-500" : 
                        strategy.win_rate >= 50 ? "text-yellow-500" : "text-red-500"
                      )}>
                        {strategy.win_rate.toFixed(1)}%
                      </div>
                      <div className="text-xs text-muted-foreground">Win Rate</div>
                    </div>
                  )}
                  
                  {strategy.profit_factor !== null && (
                    <div className="text-center">
                      <div className={cn(
                        "font-mono font-bold",
                        strategy.profit_factor >= 1.5 ? "text-green-500" : 
                        strategy.profit_factor >= 1 ? "text-yellow-500" : "text-red-500"
                      )}>
                        {strategy.profit_factor.toFixed(2)}
                      </div>
                      <div className="text-xs text-muted-foreground">Profit Factor</div>
                    </div>
                  )}
                  
                  {strategy.max_drawdown !== null && (
                    <div className="text-center">
                      <div className={cn(
                        "font-mono font-bold",
                        strategy.max_drawdown <= 15 ? "text-green-500" : 
                        strategy.max_drawdown <= 25 ? "text-yellow-500" : "text-red-500"
                      )}>
                        {strategy.max_drawdown.toFixed(1)}%
                      </div>
                      <div className="text-xs text-muted-foreground">Max DD</div>
                    </div>
                  )}
                  
                  {strategy.score !== null && (
                    <div className="text-center">
                      <div className="font-mono font-bold text-primary">
                        {strategy.score.toFixed(1)}
                      </div>
                      <div className="text-xs text-muted-foreground">Score</div>
                    </div>
                  )}
                </div>

                <button
                  onClick={() => handleDownload(strategy)}
                  className="p-2 text-muted-foreground hover:text-primary transition"
                  title="Download Pine Script"
                >
                  <Download className="h-5 w-5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
