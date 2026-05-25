/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  // Keep trailing slashes intact so `/api/v1/projects/` proxies straight to
  // the FastAPI list routes (defined as `@router.get("/")`) instead of being
  // 308-redirected to the slashless path.
  skipTrailingSlashRedirect: true,
  async rewrites() {
    // Server-side proxy target. The browser always calls relative `/api/*`
    // and `/health/*` (so API_BASE stays ""); Next rewrites them to the
    // backend service inside the cluster. Overridable via BACKEND_URL.
    const backend = process.env.BACKEND_URL || "http://dclaw-project-backend:8100";
    return [
      {
        source: "/api/:path*",
        destination: `${backend}/api/:path*`,
      },
      {
        source: "/health/:path*",
        destination: `${backend}/health/:path*`,
      },
    ];
  },
};

export default nextConfig;
