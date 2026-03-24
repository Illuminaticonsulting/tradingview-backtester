/**
 * API Client for the TradingView Backtester API
 */

// Empty string means use relative URL (same domain via nginx proxy)
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? '';

interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

class ApiClient {
  private accessToken: string | null = null;
  private refreshToken: string | null = null;

  constructor() {
    if (typeof window !== 'undefined') {
      this.accessToken = localStorage.getItem('access_token');
      this.refreshToken = localStorage.getItem('refresh_token');
    }
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string>),
    };

    if (this.accessToken) {
      headers['Authorization'] = `Bearer ${this.accessToken}`;
    }

    const response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers,
    });

    if (response.status === 401 && this.refreshToken) {
      // Try to refresh token
      const refreshed = await this.refreshAccessToken();
      if (refreshed) {
        headers['Authorization'] = `Bearer ${this.accessToken}`;
        const retryResponse = await fetch(`${API_BASE}${endpoint}`, {
          ...options,
          headers,
        });
        if (!retryResponse.ok) {
          throw new Error(`API Error: ${retryResponse.status}`);
        }
        return retryResponse.json();
      }
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `API Error: ${response.status}`);
    }

    return response.json();
  }

  private async refreshAccessToken(): Promise<boolean> {
    try {
      const response = await fetch(`${API_BASE}/api/auth/refresh`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.refreshToken}`,
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const data: TokenResponse = await response.json();
        this.setTokens(data.access_token, data.refresh_token);
        return true;
      }
    } catch (e) {
      // Refresh failed
    }
    this.clearTokens();
    return false;
  }

  setTokens(accessToken: string, refreshToken: string) {
    this.accessToken = accessToken;
    this.refreshToken = refreshToken;
    if (typeof window !== 'undefined') {
      localStorage.setItem('access_token', accessToken);
      localStorage.setItem('refresh_token', refreshToken);
    }
  }

  clearTokens() {
    this.accessToken = null;
    this.refreshToken = null;
    if (typeof window !== 'undefined') {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
    }
  }

  isAuthenticated(): boolean {
    return !!this.accessToken;
  }

  // Auth
  async register(email: string, password: string, name?: string) {
    return this.request<{ id: number; email: string }>('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, name }),
    });
  }

  async login(email: string, password: string) {
    const data = await this.request<TokenResponse>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    this.setTokens(data.access_token, data.refresh_token);
    return data;
  }

  async logout() {
    this.clearTokens();
  }

  async getMe() {
    return this.request<{ id: number; email: string; name: string | null }>('/api/auth/me');
  }

  // Credentials
  async getCredentialsStatus() {
    return this.request<{
      tv_cookies: { configured: boolean; valid: boolean };
      deepseek_key: { configured: boolean; valid: boolean };
      claude_key: { configured: boolean; valid: boolean };
    }>('/api/credentials/status');
  }

  async saveCredential(type: string, value: string, label?: string) {
    return this.request('/api/credentials/', {
      method: 'POST',
      body: JSON.stringify({ credential_type: type, value, label }),
    });
  }

  async validateCredential(type: string) {
    return this.request<{ valid: boolean; error?: string }>(
      `/api/credentials/${type}/validate`,
      { method: 'POST' }
    );
  }

  async deleteCredential(type: string) {
    return this.request(`/api/credentials/${type}`, { method: 'DELETE' });
  }

  // Watchlists
  async getWatchlists() {
    return this.request<{
      id: number;
      name: string;
      description: string | null;
      source: string;
      symbol_count: number;
      symbols: { symbol: string; exchange: string; full_symbol: string; category: string }[];
    }[]>('/api/watchlists/');
  }

  async importWatchlistFromUrl(url: string, name?: string) {
    return this.request('/api/watchlists/import/url', {
      method: 'POST',
      body: JSON.stringify({ url, name }),
    });
  }

  async createWatchlist(name: string, symbols: { symbol: string; exchange?: string }[], description?: string) {
    return this.request('/api/watchlists/', {
      method: 'POST',
      body: JSON.stringify({ name, description, symbols }),
    });
  }

  async deleteWatchlist(id: number) {
    return this.request(`/api/watchlists/${id}`, { method: 'DELETE' });
  }

  // Jobs
  async getJobs(status?: string) {
    const query = status ? `?status=${status}` : '';
    return this.request<{
      jobs: {
        id: number;
        name: string;
        status: string;
        strategy_type: string;
        current_iteration: number;
        max_iterations: number;
        progress_data: Record<string, any>;
        created_at: string;
      }[];
      total: number;
    }>(`/api/jobs/${query}`);
  }

  async createJob(data: {
    name: string;
    description?: string;
    strategy_type: string;
    ai_provider: string;
    watchlist_id: number;
    target_win_rate?: number;
    target_profit_factor?: number;
    target_max_drawdown?: number;
    max_iterations?: number;
  }) {
    return this.request('/api/jobs/', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getJob(id: number) {
    return this.request(`/api/jobs/${id}`);
  }

  async cancelJob(id: number) {
    return this.request(`/api/jobs/${id}/cancel`, { method: 'POST' });
  }

  // Strategies
  async getStrategies(sortBy = 'score') {
    return this.request<{
      strategies: {
        id: number;
        job_id: number;
        version: number;
        name: string;
        pine_script: string;
        win_rate: number | null;
        profit_factor: number | null;
        max_drawdown: number | null;
        score: number | null;
        created_at: string;
      }[];
      total: number;
    }>(`/api/strategies/?sort_by=${sortBy}`);
  }

  async getStrategy(id: number) {
    return this.request(`/api/strategies/${id}`);
  }

  async downloadStrategy(id: number): Promise<string> {
    const response = await fetch(`${API_BASE}/api/strategies/${id}/download`, {
      headers: {
        'Authorization': `Bearer ${this.accessToken}`,
      },
    });
    return response.text();
  }
}

export const api = new ApiClient();
