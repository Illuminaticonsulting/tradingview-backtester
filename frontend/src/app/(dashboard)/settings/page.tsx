"use client";

import { useState, useEffect } from "react";
import { 
  Key, 
  Cookie, 
  Save, 
  Trash2, 
  CheckCircle, 
  XCircle, 
  Loader2,
  Eye,
  EyeOff,
  AlertCircle
} from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

interface CredentialStatus {
  tv_cookies: { configured: boolean; valid: boolean };
  deepseek_key: { configured: boolean; valid: boolean };
  claude_key: { configured: boolean; valid: boolean };
}

export default function SettingsPage() {
  const [status, setStatus] = useState<CredentialStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadStatus();
  }, []);

  const loadStatus = async () => {
    try {
      const data = await api.getCredentialsStatus();
      setStatus(data);
    } finally {
      setLoading(false);
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
    <div className="max-w-2xl space-y-8">
      <div>
        <h1 className="text-3xl font-bold">Settings</h1>
        <p className="text-muted-foreground mt-1">
          Configure your API keys and TradingView credentials
        </p>
      </div>

      <div className="glass rounded-xl p-6 space-y-6">
        <div className="flex items-center gap-3 pb-4 border-b border-border">
          <Cookie className="h-6 w-6 text-orange-500" />
          <div>
            <h2 className="font-semibold">TradingView Cookies</h2>
            <p className="text-sm text-muted-foreground">
              Required for browser automation
            </p>
          </div>
          <StatusBadge configured={status?.tv_cookies.configured} valid={status?.tv_cookies.valid} />
        </div>
        
        <CredentialInput
          type="tv_cookies"
          placeholder='[{"name": "sessionid", "value": "..."}, ...]'
          isTextarea
          onSave={loadStatus}
          configured={status?.tv_cookies.configured}
        />
        
        <div className="p-3 bg-yellow-500/10 border border-yellow-500/20 rounded-lg flex gap-3">
          <AlertCircle className="h-5 w-5 text-yellow-500 flex-shrink-0 mt-0.5" />
          <div className="text-sm">
            <p className="font-medium text-yellow-500">How to get cookies:</p>
            <ol className="mt-1 text-muted-foreground space-y-1 list-decimal list-inside">
              <li>Log into TradingView in Chrome</li>
              <li>Press F12 → Application → Cookies</li>
              <li>Copy cookies as JSON array format</li>
            </ol>
          </div>
        </div>
      </div>

      <div className="glass rounded-xl p-6 space-y-6">
        <div className="flex items-center gap-3 pb-4 border-b border-border">
          <Key className="h-6 w-6 text-blue-500" />
          <div>
            <h2 className="font-semibold">DeepSeek API Key</h2>
            <p className="text-sm text-muted-foreground">
              For DeepSeek R1 strategy generation (recommended)
            </p>
          </div>
          <StatusBadge configured={status?.deepseek_key.configured} valid={status?.deepseek_key.valid} />
        </div>
        
        <CredentialInput
          type="deepseek_key"
          placeholder="sk-..."
          onSave={loadStatus}
          configured={status?.deepseek_key.configured}
        />
      </div>

      <div className="glass rounded-xl p-6 space-y-6">
        <div className="flex items-center gap-3 pb-4 border-b border-border">
          <Key className="h-6 w-6 text-purple-500" />
          <div>
            <h2 className="font-semibold">Claude API Key</h2>
            <p className="text-sm text-muted-foreground">
              For Claude Sonnet strategy generation (optional)
            </p>
          </div>
          <StatusBadge configured={status?.claude_key.configured} valid={status?.claude_key.valid} />
        </div>
        
        <CredentialInput
          type="claude_key"
          placeholder="sk-ant-..."
          onSave={loadStatus}
          configured={status?.claude_key.configured}
        />
      </div>
    </div>
  );
}

function StatusBadge({ configured, valid }: { configured?: boolean; valid?: boolean }) {
  if (!configured) {
    return (
      <span className="ml-auto px-2 py-1 text-xs rounded-full bg-muted text-muted-foreground">
        Not configured
      </span>
    );
  }
  
  if (valid === true) {
    return (
      <span className="ml-auto flex items-center gap-1 px-2 py-1 text-xs rounded-full bg-green-500/20 text-green-500">
        <CheckCircle className="h-3 w-3" />
        Valid
      </span>
    );
  }
  
  if (valid === false) {
    return (
      <span className="ml-auto flex items-center gap-1 px-2 py-1 text-xs rounded-full bg-red-500/20 text-red-500">
        <XCircle className="h-3 w-3" />
        Invalid
      </span>
    );
  }
  
  return (
    <span className="ml-auto px-2 py-1 text-xs rounded-full bg-yellow-500/20 text-yellow-500">
      Not validated
    </span>
  );
}

function CredentialInput({
  type,
  placeholder,
  isTextarea,
  onSave,
  configured,
}: {
  type: string;
  placeholder: string;
  isTextarea?: boolean;
  onSave: () => void;
  configured?: boolean;
}) {
  const [value, setValue] = useState("");
  const [showValue, setShowValue] = useState(false);
  const [saving, setSaving] = useState(false);
  const [validating, setValidating] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const handleSave = async () => {
    if (!value.trim()) return;
    
    setSaving(true);
    setMessage(null);
    
    try {
      await api.saveCredential(type, value.trim());
      setValue("");
      setMessage({ type: "success", text: "Saved successfully" });
      onSave();
    } catch (err) {
      setMessage({ type: "error", text: err instanceof Error ? err.message : "Failed to save" });
    } finally {
      setSaving(false);
    }
  };

  const handleValidate = async () => {
    setValidating(true);
    setMessage(null);
    
    try {
      const result = await api.validateCredential(type);
      if (result.valid) {
        setMessage({ type: "success", text: "Credential is valid!" });
      } else {
        setMessage({ type: "error", text: result.error || "Credential is invalid" });
      }
      onSave();
    } catch (err) {
      setMessage({ type: "error", text: err instanceof Error ? err.message : "Validation failed" });
    } finally {
      setValidating(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm("Delete this credential?")) return;
    
    setDeleting(true);
    setMessage(null);
    
    try {
      await api.deleteCredential(type);
      setMessage({ type: "success", text: "Deleted" });
      onSave();
    } catch (err) {
      setMessage({ type: "error", text: err instanceof Error ? err.message : "Failed to delete" });
    } finally {
      setDeleting(false);
    }
  };

  const InputComponent = isTextarea ? "textarea" : "input";

  return (
    <div className="space-y-3">
      <div className="relative">
        <InputComponent
          type={showValue || isTextarea ? "text" : "password"}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder={configured ? "••••••••••••••••" : placeholder}
          className={cn(
            "w-full px-4 py-2 bg-secondary border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary pr-10",
            isTextarea && "min-h-[100px] resize-y font-mono text-sm"
          )}
        />
        {!isTextarea && (
          <button
            type="button"
            onClick={() => setShowValue(!showValue)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
          >
            {showValue ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </button>
        )}
      </div>

      {message && (
        <p className={cn(
          "text-sm",
          message.type === "success" ? "text-green-500" : "text-red-500"
        )}>
          {message.text}
        </p>
      )}

      <div className="flex gap-2">
        <button
          onClick={handleSave}
          disabled={saving || !value.trim()}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 disabled:opacity-50 transition"
        >
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
          Save
        </button>
        
        {configured && (
          <>
            <button
              onClick={handleValidate}
              disabled={validating}
              className="flex items-center gap-2 px-4 py-2 bg-secondary text-foreground rounded-lg hover:bg-secondary/80 disabled:opacity-50 transition"
            >
              {validating ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle className="h-4 w-4" />}
              Validate
            </button>
            
            <button
              onClick={handleDelete}
              disabled={deleting}
              className="flex items-center gap-2 px-4 py-2 text-red-500 hover:bg-red-500/10 rounded-lg disabled:opacity-50 transition"
            >
              {deleting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
              Delete
            </button>
          </>
        )}
      </div>
    </div>
  );
}
