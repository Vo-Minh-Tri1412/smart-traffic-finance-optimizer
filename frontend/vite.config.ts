import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Backend dashboard API (FastAPI): python -m ai_quantum_hvtc dashboard --port 8600
const API_TARGET = process.env.VITE_API_PROXY ?? "http://127.0.0.1:8600";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: API_TARGET,
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
  },
});
