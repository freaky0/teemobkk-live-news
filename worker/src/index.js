/**
 * TeemoBKK Live News - schedule trigger.
 *
 * Cloudflare Workers Free caps CPU at 10ms per invocation and 50 subrequests,
 * which is far too little to parse ~40 news feeds. So this Worker does not
 * collect anything: on a cron trigger it simply asks GitHub to run the
 * existing Python collector, which has real CPU and the tuned rules.
 *
 * Secrets / vars (see wrangler.toml and DEPLOY.md):
 *   GH_TOKEN  - fine-grained token, Actions: Read and write on this repo only
 *   REPO      - owner/repo
 *   WORKFLOW  - workflow file name
 *   TRIGGER_KEY - optional; enables the manual /trigger endpoint
 */

const API_VERSION = "2022-11-28";

async function dispatch(env, reason) {
  const repo = env.REPO;
  const workflow = env.WORKFLOW;
  if (!repo || !workflow) {
    return { ok: false, status: 0, detail: "REPO or WORKFLOW is not configured" };
  }
  if (!env.GH_TOKEN) {
    return { ok: false, status: 0, detail: "GH_TOKEN secret is not set" };
  }
  const target = "https://api.github.com/repos/" + repo + "/actions/workflows/" + workflow + "/dispatches";
  const response = await fetch(target, {
    method: "POST",
    headers: {
      "Authorization": "Bearer " + env.GH_TOKEN,
      "Accept": "application/vnd.github+json",
      "X-GitHub-Api-Version": API_VERSION,
      "User-Agent": "teemobkk-live-news-trigger"
    },
    body: JSON.stringify({ ref: "main" })
  });
  const detail = response.status === 204 ? "queued" : (await response.text()).slice(0, 300);
  console.log("dispatch reason=" + reason + " status=" + response.status + " detail=" + detail);
  return { ok: response.status === 204, status: response.status, detail: detail, at: new Date().toISOString() };
}

export default {
  async scheduled(controller, env, ctx) {
    ctx.waitUntil(dispatch(env, "cron:" + controller.cron));
  },

  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/trigger") {
      if (!env.TRIGGER_KEY || url.searchParams.get("key") !== env.TRIGGER_KEY) {
        return new Response("forbidden", { status: 403 });
      }
      const result = await dispatch(env, "manual");
      return Response.json(result, { status: result.ok ? 200 : 502 });
    }
    return Response.json({
      service: "teemobkk-live-news-trigger",
      role: "wakes the GitHub Actions collector on a cron schedule",
      repo: env.REPO || null,
      workflow: env.WORKFLOW || null,
      token_configured: Boolean(env.GH_TOKEN),
      schedule: "*/5 * * * *"
    });
  }
};
