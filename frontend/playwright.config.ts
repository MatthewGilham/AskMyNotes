// End-to-end test setup. The tests start the real app on a spare port, with
// fake models (so nothing costs money), a fresh data folder inside the
// project (so your real chats are never touched), and a small made-up notes
// module with its own settings file (so your real notes are never read).
import { defineConfig } from "@playwright/test";
import { rmSync } from "node:fs";
import { resolve } from "node:path";

// Keep Playwright's browsers inside node_modules, not in the user folder.
process.env.PLAYWRIGHT_BROWSERS_PATH = "0";

// 8765 unless another program is using it (then set E2E_PORT to a free port).
const port = Number(process.env.E2E_PORT ?? 8765);
// The worker processes load this file again; the variable makes sure the data
// folder is only wiped once, by the first load, before the server starts.
if (!process.env.E2E_DATA_DIR) {
  process.env.E2E_DATA_DIR = resolve("..", "data", "e2e");
  rmSync(process.env.E2E_DATA_DIR, { recursive: true, force: true });
}
const dataDir = process.env.E2E_DATA_DIR;

export default defineConfig({
  testDir: "./e2e",
  workers: 1, // the tests share one server and one database
  use: { baseURL: `http://127.0.0.1:${port}` },
  webServer: {
    // e2e_setup writes the made-up notes and the settings file first.
    command:
      `uv run python -m askmynotes.e2e_setup "${dataDir}" && ` +
      `uv run askmynotes --no-browser --fake-model --port ${port} ` +
      `--settings "${dataDir}/settings.toml" --data-dir "${dataDir}"`,
    cwd: "..",
    url: `http://127.0.0.1:${port}/api/health`,
    reuseExistingServer: false,
    timeout: 120_000,
  },
});
