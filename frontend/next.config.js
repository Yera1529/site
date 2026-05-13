/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  async rewrites() {
    return [
      {
        // Proxy template downloads through Next.js to avoid CORS
        source: "/download-sd/:path*",
        destination: "http://backend:8000/api/templates-sd/download/:path*",
      },
    ];
  },
};

module.exports = nextConfig;
