import type { NextConfig } from "next";

const API_URL = process.env.API_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  transpilePackages: ["@step-by-step/api-client"],
  experimental: {
    // TypeScript 7 (tsgo) has no in-process compiler API; use its CLI.
    useTypeScriptCli: true,
  },
  async rewrites() {
    // The browser talks to one origin; Next proxies /api/* to FastAPI — and
    // the extension download with it, because the instance serves the build
    // that came with it, from the backend that came with it.
    return [
      { source: "/api/:path*", destination: `${API_URL}/api/:path*` },
      { source: "/extension", destination: `${API_URL}/extension` },
      { source: "/extension.zip", destination: `${API_URL}/extension.zip` },
    ];
  },
};

export default nextConfig;
