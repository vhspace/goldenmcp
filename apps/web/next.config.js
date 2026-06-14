const { getWebEnvConfig } = require("./load-web-env.cjs");

/** @type {import('next').NextConfig} */
const nextConfig = {
  // standalone is for self-hosted Docker; Vercel uses its own serverless output.
  ...(process.env.VERCEL ? {} : { output: "standalone" }),
  env: getWebEnvConfig(),
};

module.exports = nextConfig;
