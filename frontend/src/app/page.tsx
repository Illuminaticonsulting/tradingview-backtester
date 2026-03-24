import Link from "next/link";
import { ArrowRight, Bot, LineChart, Zap, Shield, Clock, Target } from "lucide-react";

export default function LandingPage() {
  return (
    <div className="relative min-h-screen">
      {/* Hero Section */}
      <header className="relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-blue-600/20 via-purple-600/10 to-transparent" />
        
        <nav className="relative z-10 flex items-center justify-between px-6 py-4 max-w-7xl mx-auto">
          <div className="flex items-center gap-2">
            <Bot className="h-8 w-8 text-primary" />
            <span className="text-xl font-bold">TV Backtester</span>
          </div>
          <div className="flex items-center gap-4">
            <Link href="/login" className="text-muted-foreground hover:text-foreground transition">
              Login
            </Link>
            <Link 
              href="/register" 
              className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition"
            >
              Get Started
            </Link>
          </div>
        </nav>

        <div className="relative z-10 max-w-7xl mx-auto px-6 py-24 text-center">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/10 text-primary text-sm mb-8">
            <Zap className="h-4 w-4" />
            <span>Powered by DeepSeek R1 & Claude</span>
          </div>
          
          <h1 className="text-5xl md:text-7xl font-bold tracking-tight mb-6">
            AI-Powered<br />
            <span className="bg-gradient-to-r from-blue-500 to-purple-500 bg-clip-text text-transparent">
              Strategy Generation
            </span>
          </h1>
          
          <p className="text-xl text-muted-foreground max-w-2xl mx-auto mb-10">
            Let AI create, test, and optimize TradingView Pine Script strategies automatically.
            Import your watchlist, set your targets, and watch the magic happen.
          </p>

          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link 
              href="/register" 
              className="inline-flex items-center justify-center gap-2 px-6 py-3 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition text-lg font-medium"
            >
              Start Free <ArrowRight className="h-5 w-5" />
            </Link>
            <Link 
              href="#features" 
              className="inline-flex items-center justify-center gap-2 px-6 py-3 border border-border rounded-lg hover:bg-card transition text-lg"
            >
              Learn More
            </Link>
          </div>
        </div>
      </header>

      {/* Features Section */}
      <section id="features" className="py-24 px-6">
        <div className="max-w-7xl mx-auto">
          <h2 className="text-3xl md:text-4xl font-bold text-center mb-4">
            How It Works
          </h2>
          <p className="text-muted-foreground text-center mb-16 max-w-2xl mx-auto">
            A fully autonomous agent that generates, backtests, and iteratively improves trading strategies
          </p>

          <div className="grid md:grid-cols-3 gap-8">
            <FeatureCard
              icon={<Target className="h-8 w-8 text-blue-500" />}
              title="Set Your Targets"
              description="Define your desired win rate, profit factor, and max drawdown. The AI will optimize toward your goals."
            />
            <FeatureCard
              icon={<LineChart className="h-8 w-8 text-green-500" />}
              title="Import Watchlist"
              description="Paste a TradingView watchlist URL or upload a CSV. We'll parse your symbols automatically."
            />
            <FeatureCard
              icon={<Bot className="h-8 w-8 text-purple-500" />}
              title="AI Generation"
              description="DeepSeek R1 or Claude generates Pine Script strategies, backtests them, and iterates based on results."
            />
          </div>
        </div>
      </section>

      {/* Benefits Section */}
      <section className="py-24 px-6 bg-card/50">
        <div className="max-w-7xl mx-auto">
          <div className="grid md:grid-cols-2 gap-16 items-center">
            <div>
              <h2 className="text-3xl md:text-4xl font-bold mb-6">
                Why Use AI Backtesting?
              </h2>
              <div className="space-y-6">
                <Benefit
                  icon={<Clock className="h-6 w-6 text-blue-500" />}
                  title="Save Hundreds of Hours"
                  description="What takes traders weeks of manual testing happens in minutes."
                />
                <Benefit
                  icon={<Zap className="h-6 w-6 text-yellow-500" />}
                  title="Continuous Improvement"
                  description="The AI learns from each backtest and iteratively improves the strategy."
                />
                <Benefit
                  icon={<Shield className="h-6 w-6 text-green-500" />}
                  title="Your Keys, Your Control"
                  description="You provide your own API keys and TradingView cookies. We never store them unencrypted."
                />
              </div>
            </div>
            <div className="glass rounded-2xl p-8 space-y-4">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Win Rate</span>
                <span className="text-green-500 font-mono">68.4%</span>
              </div>
              <div className="h-2 bg-secondary rounded-full overflow-hidden">
                <div className="h-full bg-green-500 rounded-full" style={{ width: '68.4%' }} />
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Profit Factor</span>
                <span className="text-blue-500 font-mono">2.34</span>
              </div>
              <div className="h-2 bg-secondary rounded-full overflow-hidden">
                <div className="h-full bg-blue-500 rounded-full" style={{ width: '78%' }} />
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Max Drawdown</span>
                <span className="text-yellow-500 font-mono">12.1%</span>
              </div>
              <div className="h-2 bg-secondary rounded-full overflow-hidden">
                <div className="h-full bg-yellow-500 rounded-full" style={{ width: '12.1%' }} />
              </div>
              <p className="text-center text-sm text-muted-foreground pt-4 border-t border-border">
                Example strategy metrics after 5 iterations
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-24 px-6">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-3xl md:text-4xl font-bold mb-6">
            Ready to Automate Your Strategy Research?
          </h2>
          <p className="text-muted-foreground mb-10 text-lg">
            Create an account, add your API keys, import a watchlist, and let AI do the rest.
          </p>
          <Link 
            href="/register" 
            className="inline-flex items-center justify-center gap-2 px-8 py-4 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition text-lg font-medium"
          >
            Get Started Free <ArrowRight className="h-5 w-5" />
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border py-8 px-6">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <Bot className="h-6 w-6 text-primary" />
            <span className="font-bold">TV Backtester</span>
          </div>
          <p className="text-sm text-muted-foreground">
            © 2024 TradingView AI Backtester. Not affiliated with TradingView.
          </p>
        </div>
      </footer>
    </div>
  );
}

function FeatureCard({ icon, title, description }: { icon: React.ReactNode; title: string; description: string }) {
  return (
    <div className="glass rounded-xl p-6 hover:border-primary/50 transition">
      <div className="mb-4">{icon}</div>
      <h3 className="text-xl font-semibold mb-2">{title}</h3>
      <p className="text-muted-foreground">{description}</p>
    </div>
  );
}

function Benefit({ icon, title, description }: { icon: React.ReactNode; title: string; description: string }) {
  return (
    <div className="flex gap-4">
      <div className="flex-shrink-0 mt-1">{icon}</div>
      <div>
        <h3 className="font-semibold mb-1">{title}</h3>
        <p className="text-muted-foreground">{description}</p>
      </div>
    </div>
  );
}
