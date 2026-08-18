import type { NextConfig } from "next";

const API_URL = process.env.API_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  transpilePackages: ["@step-by-step/api-client"],
  // `next dev` otherwise writes its own AGENTS.md and CLAUDE.md into apps/web
  // on every start. This repository already tells agents what they need, from
  // the root, and a generated pair beside it is two more files saying
  // something else.
  agentRules: false,
  experimental: {
    // TypeScript 7 (tsgo) has no in-process compiler API; use its CLI.
    useTypeScriptCli: true,
  },
  async rewrites() {
    // The browser talks to one origin; Next proxies /api/* to FastAPI.
    return [{ source: "/api/:path*", destination: `${API_URL}/api/:path*` }];
  },
};

export default nextConfig;
