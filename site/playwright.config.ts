import { defineConfig, devices } from "@playwright/test";

import { E2E_AUTH_SECRET, E2E_WEB_SECRET } from "./e2e/session";

const MOCK = 4010;
const SITE = 3100;


export default defineConfig({
  testDir: "e2e",
  timeout: 30_000,
  reporter: "list",
  use: { baseURL: `http://127.0.0.1:${SITE}`, ...devices["Desktop Chrome"] },
  webServer: [
    {
      command: `MOCK_PORT=${MOCK} node e2e/mock-api.mjs`,
      port: MOCK,
      reuseExistingServer: false,
      env: { NETWORTH_WEB_SECRET: E2E_WEB_SECRET },
    },
    {
      command: `npx next start -p ${SITE} -H 127.0.0.1`,
      port: SITE,
      reuseExistingServer: false,
      env: {
        NETWORTH_API_URL: `http://127.0.0.1:${MOCK}`,
        NETWORTH_WEB_SECRET: E2E_WEB_SECRET,
        AUTH_SECRET: E2E_AUTH_SECRET,
        AUTH_TRUST_HOST: "true",
        AUTH_GOOGLE_ID: "e2e-client-id",
        AUTH_GOOGLE_SECRET: "e2e-client-secret",
        NETWORTH_LAB: "1",
      },
    },
  ],
});
