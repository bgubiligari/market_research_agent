import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests/browser",
  workers: 1,
  use: {
    baseURL: process.env.WEB_URL || "http://127.0.0.1:3002",
    headless: true,
    channel: "chrome",
  },
  reporter: "list",
  timeout: 45000,
});
