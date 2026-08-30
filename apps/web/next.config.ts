import type { NextConfig } from "next";

const API_URL = process.env.API_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  transpilePackages: ["@step-by-step/api-client", "@novnc/novnc"],
  experimental: {
    useTypeScriptCli: true,
  },
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${API_URL}/api/:path*` },
      { source: "/extension", destination: `${API_URL}/extension` },
      { source: "/extension.zip", destination: `${API_URL}/extension.zip` },
    ];
  },
};

export default nextConfig;
