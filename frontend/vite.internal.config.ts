import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  root: "internal",
  envDir: ".",
  plugins: [react()],
  cacheDir: "../node_modules/.vite-internal",
  resolve: {
    alias: {
      "/src": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    host: "127.0.0.1",
    port: 5174,
    fs: {
      allow: [".."],
    },
  },
  preview: {
    host: "127.0.0.1",
    port: 4174,
  },
  build: {
    outDir: "../dist/internal",
    emptyOutDir: false,
  },
});
