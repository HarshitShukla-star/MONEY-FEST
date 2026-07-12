import type { Config } from "tailwindcss";
const config: Config = { content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"], theme: { extend: { colors: { ink: "#09090b", panel: "#111116", line: "#27272f", glow: "#7c5cff" }, boxShadow: { glow: "0 0 40px rgba(100,83,255,.22)" } } }, plugins: [] };
export default config;
