import { defineConfig, loadEnv } from "vite";
import { tanstackRouter } from "@tanstack/router-plugin/vite";
import viteReact from "@vitejs/plugin-react";
import tsconfigPaths from "vite-tsconfig-paths";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const backendUrl = env.BACKEND_URL || "http://localhost:8000";

  return {
    server: {
      port: 3000,
      proxy: {
        "/api": {
          target: backendUrl,
          changeOrigin: true,
        },
      },
    },
    plugins: [
      tanstackRouter({
        routesDirectory: "src/app",
        generatedRouteTree: "src/routeTree.gen.ts",
        target: "react",
      }),
      viteReact({
        babel: {
          plugins: ["babel-plugin-react-compiler"],
        },
      }),
      tailwindcss(),
      tsconfigPaths(),
    ],
  };
});
