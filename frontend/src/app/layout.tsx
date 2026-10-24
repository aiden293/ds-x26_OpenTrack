import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = { title: "Civic Pulse | Boston 311 estimates", description: "Understand the possible wait for your Boston 311 request with historical resolution estimates." };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
