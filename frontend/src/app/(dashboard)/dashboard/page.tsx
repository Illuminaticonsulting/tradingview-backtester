"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { 
  Play, 
  FileCode, 
  Activity, 
  TrendingUp,
  Clock,
  CheckCircle,
  XCircle,
  Loader2
} from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

interface Job {
  id: number;
  name: string;
  status: string;
  strategy_type: string;
  current_iteration: number;
  max_iterations: number;
  created_at: string;
}

interface Strategy {
  id: number;
  name: string;
  win_rate: number | null;
  profit_factor: number | null;
  score: number | null;
}

export default function DashboardPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [credStatus, setCredStatus] = useState<{
    tv_cookies: { configured: boolean };
    deepseek_key: { configured: boolean };
    claude_key: { configured: boolean };
  } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.getJobs().then(r => setJobs(r.jobs.slice(0, 5))),
      api.getStrategies().then(r => setStrategies(r.strategies.slice(0, 5))),
      api.getCredentialsStatus().then(setCredStatus),
    ]).finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  const allCredsConfigured = credStatus && 
    credStatus.tv_cookies.configured && 
    (credStatus.deepseek_key.configured || credStatus.claude_key.configured);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold">Dashboard</h1>
        <p className="text-muted-foreground mt-1">
          Generate and manage your AI trading strategies
        </p>
      </div>

      {/* Setup Alert */}
      {!allCredsConfigured && (
        <div className="p-4 bg-yellow-500/10 border border-yellow-500/20 rounded-lg">
          <h3 className="font-medium text-yellow-500 mb-1">Setup Required</h3>
          <p className="text-sm text-muted-foreground mb-3">
            Configure your credentials before generating strategies.
          </p>
          <Link
            href="/settings"
            className="inline-flex items-center text-sm text-yellow-500 hover:underline"
          >
            Go to Settings →
          </Link>
        </div>
      )}

      {/* Quick Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          icon={<Activity className="h-5 w-5 text-blue-500" />}
          label="Total Jobs"
          value={jobs.length.toString()}
        />
        <StatCard
          icon={<FileCode className="h-5 w-5 text-green-500" />}
          label="Strategies"
          value={strategies.length.toString()}
        />
        <StatCard
          icon={<TrendingUp className="h-5 w-5 text-purple-500" />}
          label="Best Win Rate"
          value={strategies[0]?.win_rate ? `${strategies[0].win_rate.toFixed(1)}%` : "—"}
        />
        <StatCard
          icon={<CheckCircle className="h-5 w-5 text-emerald-500" />}
          label="Completed Jobs"
          value={jobs.filter(j => j.status === "completed").length.toString()}
        />
      </div>

      {/* Quick Actions */}
      <div className="grid md:grid-cols-2 gap-4">
        <Link
          href="/generate"
          className={cn(
            "glass p-6 rounded-xl flex items-center gap-4 hover:border-primary/50 transition",
            !allCredsConfigured && "opacity-50 pointer-events-none"
          )}
        >
          <div className="p-3 rounded-lg bg-primary/20">
            <Play className="h-6 w-6 text-primary" />
          </div>
          <div>
            <h3 className="font-semibold">Generate Strategy</h3>
            <p className="text-sm text-muted-foreground">
              Let AI create and optimize a new strategy
            </p>
          </div>
        </Link>
        <Link
          href="/watchlists"
          className="glass p-6 rounded-xl flex items-center gap-4 hover:border-primary/50 transition"
        >
          <div className="p-3 rounded-lg bg-green-500/20">
            <FileCode className="h-6 w-6 text-green-500" />
          </div>
          <div>
            <h3 className="font-semibold">Manage Watchlists</h3>
            <p className="text-sm text-muted-foreground">
              Import symbols from TradingView
            </p>
          </div>
        </Link>
      </div>

      {/* Recent Jobs */}
      <div className="glass rounded-xl p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold">Recent Jobs</h2>
          {jobs.length > 0 && (
            <Link href="/generate" className="text-sm text-primary hover:underline">
              View all
            </Link>
          )}
        </div>
        
        {jobs.length === 0 ? (
          <p className="text-center text-muted-foreground py-8">
            No jobs yet. Generate your first strategy!
          </p>
        ) : (
          <div className="space-y-3">
            {jobs.map((job) => (
              <div
                key={job.id}
                className="flex items-center gap-4 p-3 rounded-lg bg-secondary/50"
              >
                <StatusIcon status={job.status} />
                <div className="flex-1 min-w-0">
                  <p className="font-medium truncate">{job.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {job.strategy_type} • Iteration {job.current_iteration}/{job.max_iterations}
                  </p>
                </div>
                <div className="text-xs text-muted-foreground">
                  <Clock className="h-3 w-3 inline mr-1" />
                  {new Date(job.created_at).toLocaleDateString()}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Top Strategies */}
      <div className="glass rounded-xl p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold">Top Strategies</h2>
          {strategies.length > 0 && (
            <Link href="/strategies" className="text-sm text-primary hover:underline">
              View all
            </Link>
          )}
        </div>
        
        {strategies.length === 0 ? (
          <p className="text-center text-muted-foreground py-8">
            No strategies generated yet.
          </p>
        ) : (
          <div className="space-y-3">
            {strategies.map((strategy, i) => (
              <Link
                key={strategy.id}
                href={`/strategies/${strategy.id}`}
                className="flex items-center gap-4 p-3 rounded-lg bg-secondary/50 hover:bg-secondary transition"
              >
                <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center text-primary font-bold">
                  {i + 1}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-medium truncate">{strategy.name}</p>
                </div>
                <div className="flex items-center gap-4 text-sm">
                  {strategy.win_rate && (
                    <span className="text-green-500">{strategy.win_rate.toFixed(1)}% WR</span>
                  )}
                  {strategy.profit_factor && (
                    <span className="text-blue-500">{strategy.profit_factor.toFixed(2)} PF</span>
                  )}
                  {strategy.score && (
                    <span className="font-mono text-muted-foreground">
                      Score: {strategy.score.toFixed(1)}
                    </span>
                  )}
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function StatCard({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="glass rounded-xl p-4">
      <div className="flex items-center gap-2 mb-2">
        {icon}
        <span className="text-sm text-muted-foreground">{label}</span>
      </div>
      <p className="text-2xl font-bold">{value}</p>
    </div>
  );
}

function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case "completed":
      return <CheckCircle className="h-5 w-5 text-green-500" />;
    case "failed":
      return <XCircle className="h-5 w-5 text-red-500" />;
    case "running":
      return <Loader2 className="h-5 w-5 text-blue-500 animate-spin" />;
    default:
      return <Clock className="h-5 w-5 text-muted-foreground" />;
  }
}
