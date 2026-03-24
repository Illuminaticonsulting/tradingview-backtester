import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "TradingView AI Backtester",
  description: "Autonomous AI-powered Pine Script strategy generation and backtesting",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-background antialiased">
        {children}
      </body>
    </html>
  );
}
