import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    chunkSizeWarningLimit: 1600,
    rollupOptions: {
      output: {
        manualChunks: {
          three: ["three"],
          anime: ["animejs"],
          markdown: ["react-markdown", "remark-gfm", "react-syntax-highlighter"],
          vendor: ["react", "react-dom", "zustand", "uuid", "lucide-react"],
        },
      },
    },
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    allowedHosts: true,
    proxy: {
      "/api": {
        target: process.env.VITE_BACKEND_URL || "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  preview: {
    host: "0.0.0.0",
    allowedHosts: true,
  },
});
