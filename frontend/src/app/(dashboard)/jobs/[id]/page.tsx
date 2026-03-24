"use client";

import { useState, useEffect, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { 
  ArrowLeft,
  Play,
  Pause,
  XCircle,
  CheckCircle,
  Loader2,
  Activity,
  TrendingUp,
  Code,
  Clock
} from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

interface JobDetail {
  id: number;
  name: string;
  description: string | null;
  status: string;
  strategy_type: string;
  ai_provider: string;
  current_iteration: number;
  max_iterations: number;
  target_win_rate: number;
  target_profit_factor: number;
  target_max_drawdown: number;
  progress_data: Record<string, any>;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

interface ProgressEvent {
  event: string;
  job_id: number;
  data: Record<string, any>;
}

export default function JobDetailPage() {
  const params = useParams();
  const router = useRouter();
  const jobId = Number(params.id);
  
  const [job, setJob] = useState<JobDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [events, setEvents] = useState<ProgressEvent[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const eventsEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadJob();
  }, [jobId]);

  useEffect(() => {
    // Connect WebSocket if job is running
    if (job?.status === "running" || job?.status === "pending") {
      connectWebSocket();
    }
    
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [job?.status]);

  useEffect(() => {
    // Auto-scroll events
    eventsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events]);

  const loadJob = async () => {
    try {
      const data = await api.getJob(jobId);
      setJob(data as JobDetail);
    } catch {
      router.push("/dashboard");
    } finally {
      setLoading(false);
    }
  };

  const connectWebSocket = () => {
    // Use current window location for WebSocket URL when API_URL is empty (production)
    const apiUrl = process.env.NEXT_PUBLIC_API_URL;
    const wsUrl = apiUrl 
      ? `${apiUrl.replace("http", "ws")}/api/jobs/${jobId}/ws`
      : `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/api/jobs/${jobId}/ws`;
    
    const ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
      console.log("WebSocket connected");
    };
    
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setEvents(prev => [...prev, data]);
        
        // Update job based on events
        if (data.event === "iteration.start") {
          setJob(prev => prev ? { ...prev, current_iteration: data.data.iteration } : prev);
        } else if (data.event === "job.complete") {
          setJob(prev => prev ? { ...prev, status: "completed" } : prev);
          loadJob(); // Reload full job data
        } else if (data.event === "error") {
          loadJob();
        }
      } catch (e) {
        console.error("Failed to parse WS message:", e);
      }
    };
    
    ws.onclose = () => {
      console.log("WebSocket disconnected");
    };
    
    wsRef.current = ws;
    
    // Ping to keep alive
    const pingInterval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send("ping");
      }
    }, 30000);
    
    return () => clearInterval(pingInterval);
  };

  const handleCancel = async () => {
    if (!confirm("Cancel this job?")) return;
    
    try {
      await api.cancelJob(jobId);
      loadJob();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to cancel");
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (!job) {
    return null;
  }

  const progress = (job.current_iteration / job.max_iterations) * 100;
  const isActive = job.status === "running" || job.status === "pending";

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link
          href="/dashboard"
          className="p-2 hover:bg-secondary rounded-lg transition"
        >
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <div className="flex-1">
          <h1 className="text-2xl font-bold">{job.name}</h1>
          <p className="text-muted-foreground">
            {job.strategy_type} • {job.ai_provider}
          </p>
        </div>
        {isActive && (
          <button
            onClick={handleCancel}
            className="flex items-center gap-2 px-4 py-2 text-red-500 hover:bg-red-500/10 rounded-lg transition"
          >
            <XCircle className="h-4 w-4" />
            Cancel
          </button>
        )}
      </div>

      {/* Status & Progress */}
      <div className="glass rounded-xl p-6">
        <div className="flex items-center gap-4 mb-4">
          <StatusIcon status={job.status} />
          <div className="flex-1">
            <p className="font-medium capitalize">{job.status}</p>
            <p className="text-sm text-muted-foreground">
              Iteration {job.current_iteration} of {job.max_iterations}
            </p>
          </div>
          {job.status === "completed" && (
            <Link
              href={`/strategies?job=${job.id}`}
              className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition"
            >
              <Code className="h-4 w-4" />
              View Strategies
            </Link>
          )}
        </div>
        
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">Progress</span>
            <span>{progress.toFixed(0)}%</span>
          </div>
          <div className="h-2 bg-secondary rounded-full overflow-hidden">
            <div 
              className={cn(
                "h-full rounded-full transition-all duration-500",
                job.status === "completed" && "bg-green-500",
                job.status === "failed" && "bg-red-500",
                job.status === "running" && "bg-primary",
                (job.status === "pending" || job.status === "cancelled") && "bg-muted"
              )}
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>

        {job.error_message && (
          <div className="mt-4 p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-red-500 text-sm">
            {job.error_message}
          </div>
        )}
      </div>

      {/* Targets */}
      <div className="grid grid-cols-3 gap-4">
        <div className="glass rounded-xl p-4">
          <div className="text-sm text-muted-foreground mb-1">Target Win Rate</div>
          <div className="text-2xl font-bold">{job.target_win_rate}%</div>
        </div>
        <div className="glass rounded-xl p-4">
          <div className="text-sm text-muted-foreground mb-1">Target Profit Factor</div>
          <div className="text-2xl font-bold">{(job.target_profit_factor / 100).toFixed(2)}</div>
        </div>
        <div className="glass rounded-xl p-4">
          <div className="text-sm text-muted-foreground mb-1">Max Drawdown</div>
          <div className="text-2xl font-bold">{job.target_max_drawdown}%</div>
        </div>
      </div>

      {/* Live Events */}
      <div className="glass rounded-xl p-6">
        <h2 className="font-semibold mb-4 flex items-center gap-2">
          <Activity className="h-5 w-5 text-primary" />
          Live Events
          {isActive && <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />}
        </h2>
        
        <div className="max-h-80 overflow-y-auto space-y-2 font-mono text-sm">
          {events.length === 0 ? (
            <p className="text-muted-foreground">
              {isActive ? "Waiting for events..." : "No events recorded"}
            </p>
          ) : (
            events.map((event, i) => (
              <div key={i} className="flex gap-2">
                <EventIcon event={event.event} />
                <span className="text-muted-foreground">
                  {formatEvent(event)}
                </span>
              </div>
            ))
          )}
          <div ref={eventsEndRef} />
        </div>
      </div>

      {/* Timestamps */}
      <div className="text-sm text-muted-foreground flex flex-wrap gap-4">
        <span className="flex items-center gap-1">
          <Clock className="h-4 w-4" />
          Created: {new Date(job.created_at).toLocaleString()}
        </span>
        {job.started_at && (
          <span>Started: {new Date(job.started_at).toLocaleString()}</span>
        )}
        {job.completed_at && (
          <span>Completed: {new Date(job.completed_at).toLocaleString()}</span>
        )}
      </div>
    </div>
  );
}

function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case "completed":
      return <CheckCircle className="h-8 w-8 text-green-500" />;
    case "failed":
      return <XCircle className="h-8 w-8 text-red-500" />;
    case "running":
      return <Loader2 className="h-8 w-8 text-primary animate-spin" />;
    case "cancelled":
      return <XCircle className="h-8 w-8 text-muted-foreground" />;
    default:
      return <Clock className="h-8 w-8 text-muted-foreground" />;
  }
}

function EventIcon({ event }: { event: string }) {
  if (event.includes("error")) {
    return <XCircle className="h-4 w-4 text-red-500 flex-shrink-0" />;
  }
  if (event.includes("improved") || event.includes("complete")) {
    return <CheckCircle className="h-4 w-4 text-green-500 flex-shrink-0" />;
  }
  if (event.includes("progress") || event.includes("start")) {
    return <Activity className="h-4 w-4 text-blue-500 flex-shrink-0" />;
  }
  return <TrendingUp className="h-4 w-4 text-muted-foreground flex-shrink-0" />;
}

function formatEvent(event: ProgressEvent): string {
  switch (event.event) {
    case "iteration.start":
      return `Starting iteration ${event.data.iteration}/${event.data.total}`;
    case "strategy.generated":
      return `Generated strategy v${event.data.version}`;
    case "backtest.progress":
      return `Backtesting ${event.data.symbol} (${event.data.current}/${event.data.total})`;
    case "metrics.collected":
      return `Metrics: WR ${event.data.win_rate?.toFixed(1) || "?"}%, PF ${event.data.profit_factor?.toFixed(2) || "?"}`;
    case "strategy.improved":
      return `New best! v${event.data.version} score: ${event.data.score?.toFixed(1)}`;
    case "job.complete":
      return `Completed! Best version: ${event.data.best_version}`;
    case "error":
      return `Error: ${event.data.message}`;
    default:
      return JSON.stringify(event.data);
  }
}
