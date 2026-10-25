import { defineConfig, devices } from "@playwright/test";

const MOCK = 4010;
const SITE = 3100;

export default defineConfig({
  testDir: "e2e",
  timeout: 30_000,
  reporter: "list",
  use: { baseURL: `http://127.0.0.1:${SITE}`, ...devices["Desktop Chrome"] },
  webServer: [
    { command: `MOCK_PORT=${MOCK} node e2e/mock-api.mjs`, port: MOCK, reuseExistingServer: false },
    {
      command: `npx next start -p ${SITE} -H 127.0.0.1`,
      port: SITE,
      reuseExistingServer: false,
      env: { NETWORTH_API_URL: `http://127.0.0.1:${MOCK}` },
    },
  ],
});
