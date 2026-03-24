"use client";

import { useState, useEffect } from "react";
import { 
  Plus, 
  Link as LinkIcon, 
  FileText, 
  Trash2, 
  Loader2,
  ExternalLink,
  Hash
} from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

interface Watchlist {
  id: number;
  name: string;
  description: string | null;
  source: string;
  symbol_count: number;
  symbols: { symbol: string; exchange: string; full_symbol: string; category: string }[];
}

export default function WatchlistsPage() {
  const [watchlists, setWatchlists] = useState<Watchlist[]>([]);
  const [loading, setLoading] = useState(true);
  const [showImport, setShowImport] = useState(false);
  const [importUrl, setImportUrl] = useState("");
  const [importName, setImportName] = useState("");
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState("");
  const [expandedId, setExpandedId] = useState<number | null>(null);

  useEffect(() => {
    loadWatchlists();
  }, []);

  const loadWatchlists = async () => {
    try {
      const data = await api.getWatchlists();
      setWatchlists(data);
    } finally {
      setLoading(false);
    }
  };

  const handleImport = async () => {
    if (!importUrl.trim()) return;
    
    setImporting(true);
    setError("");
    
    try {
      await api.importWatchlistFromUrl(importUrl.trim(), importName.trim() || undefined);
      setImportUrl("");
      setImportName("");
      setShowImport(false);
      loadWatchlists();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import failed");
    } finally {
      setImporting(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Delete this watchlist?")) return;
    
    try {
      await api.deleteWatchlist(id);
      loadWatchlists();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to delete");
    }
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
          <h1 className="text-3xl font-bold">Watchlists</h1>
          <p className="text-muted-foreground mt-1">
            Import symbols from TradingView or create manually
          </p>
        </div>
        <button
          onClick={() => setShowImport(!showImport)}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition"
        >
          <Plus className="h-4 w-4" />
          Import Watchlist
        </button>
      </div>

      {/* Import Form */}
      {showImport && (
        <div className="glass rounded-xl p-6 space-y-4">
          <div className="flex items-center gap-2 text-lg font-semibold">
            <LinkIcon className="h-5 w-5 text-primary" />
            Import from TradingView URL
          </div>
          
          <div className="space-y-3">
            <input
              type="url"
              value={importUrl}
              onChange={(e) => setImportUrl(e.target.value)}
              placeholder="https://www.tradingview.com/watchlists/123456/"
              className="w-full px-4 py-2 bg-secondary border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
            />
            <input
              type="text"
              value={importName}
              onChange={(e) => setImportName(e.target.value)}
              placeholder="Watchlist name (optional)"
              className="w-full px-4 py-2 bg-secondary border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
            />
            
            {error && (
              <p className="text-sm text-red-500">{error}</p>
            )}
            
            <div className="flex gap-2">
              <button
                onClick={handleImport}
                disabled={importing || !importUrl.trim()}
                className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 disabled:opacity-50 transition"
              >
                {importing && <Loader2 className="h-4 w-4 animate-spin" />}
                Import
              </button>
              <button
                onClick={() => setShowImport(false)}
                className="px-4 py-2 text-muted-foreground hover:text-foreground transition"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Watchlist Grid */}
      {watchlists.length === 0 ? (
        <div className="glass rounded-xl p-12 text-center">
          <FileText className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
          <h3 className="text-lg font-medium mb-2">No watchlists yet</h3>
          <p className="text-muted-foreground mb-4">
            Import a TradingView watchlist to get started
          </p>
          <button
            onClick={() => setShowImport(true)}
            className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition"
          >
            <Plus className="h-4 w-4" />
            Import Watchlist
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          {watchlists.map((watchlist) => (
            <div
              key={watchlist.id}
              className="glass rounded-xl overflow-hidden"
            >
              <div
                className="p-4 flex items-center gap-4 cursor-pointer hover:bg-secondary/50 transition"
                onClick={() => setExpandedId(expandedId === watchlist.id ? null : watchlist.id)}
              >
                <div className="h-10 w-10 rounded-lg bg-primary/20 flex items-center justify-center">
                  <Hash className="h-5 w-5 text-primary" />
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold truncate">{watchlist.name}</h3>
                  <p className="text-sm text-muted-foreground">
                    {watchlist.symbol_count} symbols • {watchlist.source}
                  </p>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDelete(watchlist.id);
                  }}
                  className="p-2 text-muted-foreground hover:text-red-500 transition"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
              
              {expandedId === watchlist.id && (
                <div className="px-4 pb-4 border-t border-border pt-4">
                  <div className="flex flex-wrap gap-2">
                    {watchlist.symbols.map((sym, i) => (
                      <span
                        key={i}
                        className={cn(
                          "px-2 py-1 text-xs rounded-full",
                          sym.category === "crypto" && "bg-purple-500/20 text-purple-400",
                          sym.category === "stock" && "bg-blue-500/20 text-blue-400",
                          sym.category === "index" && "bg-green-500/20 text-green-400",
                          sym.category === "commodity" && "bg-yellow-500/20 text-yellow-400",
                          sym.category === "forex" && "bg-cyan-500/20 text-cyan-400",
                          !["crypto", "stock", "index", "commodity", "forex"].includes(sym.category) &&
                            "bg-secondary text-muted-foreground"
                        )}
                      >
                        {sym.full_symbol}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
