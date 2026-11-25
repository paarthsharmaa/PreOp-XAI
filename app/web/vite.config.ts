import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const api = process.env.API_URL ?? "http://127.0.0.1:8000";
const proxy = {
  "/api": { target: api, changeOrigin: true, rewrite: (path: string) => path.replace(/^\/api/, "") },
};

export default defineConfig({
  base: "./",
  plugins: [react(), tailwindcss()],
  server: { proxy },
  preview: { proxy },
  build: { chunkSizeWarningLimit: 900 },
});
