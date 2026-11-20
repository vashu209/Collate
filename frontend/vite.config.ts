import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/status": "http://127.0.0.1:8000",
      "/proposals": "http://127.0.0.1:8000",
      "/operations": "http://127.0.0.1:8000",
      "/rollback": "http://127.0.0.1:8000",
      "/scan": "http://127.0.0.1:8000",
      "/propose": "http://127.0.0.1:8000",
      "/tasks": "http://127.0.0.1:8000",
      '/browse-folder': 'http://127.0.0.1:8000',
    },
  },
});
