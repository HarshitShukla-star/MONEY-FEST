import "./globals.css";
import { Providers } from "./providers";
import { AppShell } from "@/components/app-shell";
export const metadata = { title: "MONEY-FEST", description: "Content automation command center" };
export default function RootLayout({ children }: { children: React.ReactNode }) { return <html lang="en"><body><Providers><AppShell>{children}</AppShell></Providers></body></html>; }
