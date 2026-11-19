import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// In development, `npm run dev` forwards /api calls to the Python backend.
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": "http://127.0.0.1:8000" } },
});
