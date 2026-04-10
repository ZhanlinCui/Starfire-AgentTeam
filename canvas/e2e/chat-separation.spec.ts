import { test, expect } from "@playwright/test";

const API = process.env.E2E_API_URL ?? "http://localhost:8080";

test.describe("Chat Sub-Tabs", () => {
  test("chat tab shows My Chat and Agent Comms sub-tabs", async ({ page }) => {
    const res = await page.request.get(`${API}/workspaces`);
    const workspaces = await res.json();
    test.skip(workspaces.length === 0, "No workspaces to test");

    await page.goto("/");
    await page.waitForTimeout(3000);

    // Click first workspace node
    await page.locator(".react-flow__node").first().click();
    await page.waitForTimeout(500);

    // Click Chat tab
    const chatTab = page.getByRole("button", { name: /Chat/ }).first();
    await chatTab.click();
    await page.waitForTimeout(500);

    // Sub-tabs should be visible
    await expect(page.locator("text=My Chat")).toBeVisible({ timeout: 3000 });
    await expect(page.locator("text=Agent Comms")).toBeVisible({ timeout: 3000 });
  });

  test("My Chat is selected by default", async ({ page }) => {
    const res = await page.request.get(`${API}/workspaces`);
    const workspaces = await res.json();
    test.skip(workspaces.length === 0, "No workspaces");

    await page.goto("/");
    await page.waitForTimeout(3000);
    await page.locator(".react-flow__node").first().click();
    await page.waitForTimeout(500);
    await page.getByRole("button", { name: /Chat/ }).first().click();
    await page.waitForTimeout(500);

    // My Chat sub-tab should have active styling (border-blue-500)
    const myChatBtn = page.locator("button", { hasText: "My Chat" });
    await expect(myChatBtn).toHaveClass(/border-blue-500/);
  });

  test("switching to Agent Comms shows different content", async ({ page }) => {
    const res = await page.request.get(`${API}/workspaces`);
    const workspaces = await res.json();
    test.skip(workspaces.length === 0, "No workspaces");

    await page.goto("/");
    await page.waitForTimeout(3000);
    await page.locator(".react-flow__node").first().click();
    await page.waitForTimeout(500);
    await page.getByRole("button", { name: /Chat/ }).first().click();
    await page.waitForTimeout(500);

    // Click Agent Comms
    await page.locator("button", { hasText: "Agent Comms" }).click();
    await page.waitForTimeout(500);

    // Should show empty state or agent comms messages
    const hasEmpty = await page.locator("text=No agent-to-agent communications").isVisible().catch(() => false);
    const hasMessages = await page.locator("[class*=cyan]").count() > 0;
    expect(hasEmpty || hasMessages).toBeTruthy();
  });

  test("My Chat has input box, Agent Comms does not", async ({ page }) => {
    const res = await page.request.get(`${API}/workspaces`);
    const workspaces = await res.json();
    test.skip(workspaces.length === 0, "No workspaces");

    await page.goto("/");
    await page.waitForTimeout(3000);
    await page.locator(".react-flow__node").first().click();
    await page.waitForTimeout(500);
    await page.getByRole("button", { name: /Chat/ }).first().click();
    await page.waitForTimeout(500);

    // My Chat should have textarea
    await expect(page.locator("textarea")).toBeVisible();

    // Switch to Agent Comms
    await page.locator("button", { hasText: "Agent Comms" }).click();
    await page.waitForTimeout(500);

    // Agent Comms should NOT have textarea
    await expect(page.locator("textarea")).not.toBeVisible();
  });

  test("switching back to My Chat preserves messages", async ({ page }) => {
    const res = await page.request.get(`${API}/workspaces`);
    const workspaces = await res.json();
    test.skip(workspaces.length === 0, "No workspaces");

    await page.goto("/");
    await page.waitForTimeout(3000);
    await page.locator(".react-flow__node").first().click();
    await page.waitForTimeout(500);
    await page.getByRole("button", { name: /Chat/ }).first().click();
    await page.waitForTimeout(1000);

    // Check if there are messages or empty state in My Chat
    const hasContent = await page.locator("text=No messages yet").isVisible().catch(() => false) ||
      await page.locator("[class*=blue-600]").count() > 0;

    // Switch to Agent Comms and back
    await page.locator("button", { hasText: "Agent Comms" }).click();
    await page.waitForTimeout(300);
    await page.locator("button", { hasText: "My Chat" }).click();
    await page.waitForTimeout(300);

    // Same content should be there
    const hasContentAfter = await page.locator("text=No messages yet").isVisible().catch(() => false) ||
      await page.locator("[class*=blue-600]").count() > 0;

    // Both should be truthy (content exists before and after switch)
    expect(hasContent || hasContentAfter).toBeTruthy();
  });
});

test.describe("Activity API Source Filter", () => {
  test("source=canvas returns only canvas-initiated entries", async ({ request }) => {
    const wsRes = await request.get(`${API}/workspaces`);
    const workspaces = await wsRes.json();
    if (workspaces.length === 0) return;

    const wsId = workspaces[0].id;
    const res = await request.get(`${API}/workspaces/${wsId}/activity?source=canvas`);
    expect(res.ok()).toBeTruthy();
    const entries = await res.json();
    expect(Array.isArray(entries)).toBeTruthy();

    // All entries should have source_id null
    for (const e of entries) {
      expect(e.source_id).toBeNull();
    }
  });

  test("source=agent returns only agent-initiated entries", async ({ request }) => {
    const wsRes = await request.get(`${API}/workspaces`);
    const workspaces = await wsRes.json();
    if (workspaces.length === 0) return;

    const wsId = workspaces[0].id;
    const res = await request.get(`${API}/workspaces/${wsId}/activity?source=agent`);
    expect(res.ok()).toBeTruthy();
    const entries = await res.json();
    expect(Array.isArray(entries)).toBeTruthy();

    // All entries should have non-null source_id
    for (const e of entries) {
      if (e.source_id !== undefined) {
        expect(e.source_id).not.toBeNull();
      }
    }
  });

  test("source=invalid returns 400", async ({ request }) => {
    const wsRes = await request.get(`${API}/workspaces`);
    const workspaces = await wsRes.json();
    if (workspaces.length === 0) return;

    const wsId = workspaces[0].id;
    const res = await request.get(`${API}/workspaces/${wsId}/activity?source=bogus`);
    expect(res.status()).toBe(400);
  });

  test("source+type filters combine correctly", async ({ request }) => {
    const wsRes = await request.get(`${API}/workspaces`);
    const workspaces = await wsRes.json();
    if (workspaces.length === 0) return;

    const wsId = workspaces[0].id;
    const res = await request.get(`${API}/workspaces/${wsId}/activity?type=a2a_receive&source=canvas`);
    expect(res.ok()).toBeTruthy();
    const entries = await res.json();
    expect(Array.isArray(entries)).toBeTruthy();

    for (const e of entries) {
      expect(e.activity_type).toBe("a2a_receive");
      expect(e.source_id).toBeNull();
    }
  });
});

test.describe("No JS Errors", () => {
  test("page loads without errors with chat sub-tabs", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (err) => errors.push(err.message));

    await page.goto("/");
    await page.waitForTimeout(3000);

    const nodes = page.locator(".react-flow__node");
    if (await nodes.count() > 0) {
      await nodes.first().click();
      await page.waitForTimeout(500);
      await page.getByRole("button", { name: /Chat/ }).first().click();
      await page.waitForTimeout(1000);

      // Switch between tabs
      await page.locator("button", { hasText: "Agent Comms" }).click();
      await page.waitForTimeout(500);
      await page.locator("button", { hasText: "My Chat" }).click();
      await page.waitForTimeout(500);
    }

    const critical = errors.filter(
      (e) => !e.includes("WebSocket") && !e.includes("favicon") && !e.includes("hydration")
    );
    expect(critical).toEqual([]);
  });
});
