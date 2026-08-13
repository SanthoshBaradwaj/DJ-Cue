import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CUE — What does the floor want?",
  description:
    "AI song request aggregator for live events. Turns crowd noise into Crowd Waves.",
};

export const viewport: Viewport = {
  themeColor: "#05050a",
  width: "device-width",
  initialScale: 1,
  // Guests are one-handed in a dark room; a stray pinch-zoom mid-request is
  // pure friction.
  maximumScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
