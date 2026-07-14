/**
 * Playwright E2E test suite for mytodoapp04-uat
 *
 * Covers every feature exposed by the Todo app:
 *  - Page load & health
 *  - Create todo (title, description, priority, due date)
 *  - Read / list todos
 *  - Search
 *  - Filter by status (active / completed)
 *  - Filter by priority (high / medium / low)
 *  - Sort (newest, due date, priority, title)
 *  - Edit / update todo (title, description, priority, due date)
 *  - Toggle completion (done button)
 *  - Delete a single todo
 *  - Bulk complete
 *  - Bulk mark incomplete
 *  - Bulk delete
 *  - Pagination smoke test
 *  - API /health endpoint
 *  - API /api/info endpoint
 *  - API /api/todos/ CRUD via fetch
 */

import { test, expect, Page, APIRequestContext } from '@playwright/test';

// ─── Helpers ────────────────────────────────────────────────────────────────

async function clearAllTodos(request: APIRequestContext) {
  const res = await request.get('/api/todos/?page_size=100');
  const data = await res.json();
  for (const todo of data.items ?? []) {
    await request.delete(`/api/todos/${todo.id}`);
  }
}

async function createTodoViaApi(
  request: APIRequestContext,
  title: string,
  opts: { description?: string; priority?: string; due_date?: string; completed?: boolean } = {}
) {
  const res = await request.post('/api/todos/', {
    data: { title, ...opts },
  });
  expect(res.status()).toBe(201);
  return res.json();
}

async function waitForList(page: Page) {
  // Wait until the skeleton loaders disappear
  await page.waitForSelector('.todo-item, .empty', { timeout: 15_000 });
}

// ─── Health & info ───────────────────────────────────────────────────────────

test.describe('Health & API info', () => {
  test('GET /health returns 200', async ({ request }) => {
    const res = await request.get('/health');
    expect(res.status()).toBeLessThan(400);
  });

  test('GET /api/info returns app metadata and db:ok', async ({ request }) => {
    const res = await request.get('/api/info');
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body).toHaveProperty('app', 'fastapi');
    expect(body).toHaveProperty('db', 'ok');
  });
});

// ─── Page load ───────────────────────────────────────────────────────────────

test.describe('Page load', () => {
  test('Root page loads with correct title and header', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/Todo/i);
    await expect(page.locator('.app-header h1')).toBeVisible();
    await expect(page.locator('.db-badge')).toContainText('RDS PostgreSQL');
  });

  test('Add-todo form is visible', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('#new-title')).toBeVisible();
    await expect(page.locator('#new-priority')).toBeVisible();
    await expect(page.locator('#btn-add')).toBeVisible();
  });
});

// ─── Create todo ─────────────────────────────────────────────────────────────

test.describe('Create todo', () => {
  test.beforeEach(async ({ request }) => {
    await clearAllTodos(request);
  });

  test('Create a basic todo via UI', async ({ page }) => {
    await page.goto('/');
    await waitForList(page);

    await page.fill('#new-title', 'My first todo');
    await page.click('#btn-add');

    await expect(page.locator('.todo-item .todo-title').first()).toContainText('My first todo');
  });

  test('Create todo with all fields (description, priority, due date)', async ({ page }) => {
    await page.goto('/');
    await waitForList(page);

    await page.fill('#new-title', 'Full todo');
    await page.fill('#new-desc', 'This is a description');
    await page.selectOption('#new-priority', 'high');
    // Set a future due date
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    const dateStr = tomorrow.toISOString().slice(0, 10);
    await page.fill('#new-due', dateStr);
    await page.click('#btn-add');

    const item = page.locator('.todo-item').filter({ hasText: 'Full todo' }).first();
    await expect(item).toBeVisible();
    await expect(item.locator('.todo-desc')).toContainText('This is a description');
    await expect(item.locator('.badge-high')).toBeVisible();
    await expect(item.locator('.due-date')).toBeVisible();
  });

  test('Create todo with low priority', async ({ page }) => {
    await page.goto('/');
    await waitForList(page);

    await page.fill('#new-title', 'Low priority task');
    await page.selectOption('#new-priority', 'low');
    await page.click('#btn-add');

    const item = page.locator('.todo-item').filter({ hasText: 'Low priority task' }).first();
    await expect(item.locator('.badge-low')).toBeVisible();
  });

  test('Create todo with medium priority', async ({ page }) => {
    await page.goto('/');
    await waitForList(page);

    await page.fill('#new-title', 'Medium priority task');
    await page.selectOption('#new-priority', 'medium');
    await page.click('#btn-add');

    const item = page.locator('.todo-item').filter({ hasText: 'Medium priority task' }).first();
    await expect(item.locator('.badge-medium')).toBeVisible();
  });

  test('Create todo via API and verify it appears in UI', async ({ page, request }) => {
    await createTodoViaApi(request, 'API-created todo', { priority: 'high' });
    await page.goto('/');
    await waitForList(page);
    await expect(page.locator('.todo-item').filter({ hasText: 'API-created todo' })).toBeVisible();
  });
});

// ─── Read / list todos ────────────────────────────────────────────────────────

test.describe('Read / list todos', () => {
  test.beforeEach(async ({ request }) => {
    await clearAllTodos(request);
    await createTodoViaApi(request, 'Todo Alpha', { priority: 'high' });
    await createTodoViaApi(request, 'Todo Beta', { priority: 'medium' });
    await createTodoViaApi(request, 'Todo Gamma', { priority: 'low' });
  });

  test('All created todos are shown in the list', async ({ page }) => {
    await page.goto('/');
    await waitForList(page);

    await expect(page.locator('.todo-item')).toHaveCount(3);
  });

  test('Stats bar shows correct counts', async ({ page }) => {
    await page.goto('/');
    await waitForList(page);

    await expect(page.locator('#stat-total')).toContainText('3');
    await expect(page.locator('#stat-active')).toContainText('3');
    await expect(page.locator('#stat-done')).toContainText('0');
  });

  test('API GET /api/todos/ returns items', async ({ request }) => {
    const res = await request.get('/api/todos/');
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.total).toBeGreaterThanOrEqual(3);
    expect(Array.isArray(body.items)).toBeTruthy();
  });
});

// ─── Search ───────────────────────────────────────────────────────────────────

test.describe('Search', () => {
  test.beforeEach(async ({ request }) => {
    await clearAllTodos(request);
    await createTodoViaApi(request, 'Buy groceries');
    await createTodoViaApi(request, 'Call dentist');
    await createTodoViaApi(request, 'Buy flowers');
  });

  test('Search filters todos by title', async ({ page }) => {
    await page.goto('/');
    await waitForList(page);

    await page.fill('#search', 'Buy');
    await page.waitForTimeout(600); // debounce

    const items = page.locator('.todo-item');
    await expect(items).toHaveCount(2);
    await expect(items.filter({ hasText: 'Buy groceries' })).toBeVisible();
    await expect(items.filter({ hasText: 'Buy flowers' })).toBeVisible();
  });

  test('Search with no matches shows empty state', async ({ page }) => {
    await page.goto('/');
    await waitForList(page);

    await page.fill('#search', 'xyznonexistent999');
    await page.waitForTimeout(600);

    await expect(page.locator('.empty')).toBeVisible();
  });

  test('Clearing search restores all todos', async ({ page }) => {
    await page.goto('/');
    await waitForList(page);

    await page.fill('#search', 'Buy');
    await page.waitForTimeout(600);
    await page.fill('#search', '');
    await page.waitForTimeout(600);

    await expect(page.locator('.todo-item')).toHaveCount(3);
  });
});

// ─── Filter by status ─────────────────────────────────────────────────────────

test.describe('Filter by status', () => {
  test.beforeEach(async ({ request }) => {
    await clearAllTodos(request);
    await createTodoViaApi(request, 'Active todo 1');
    await createTodoViaApi(request, 'Active todo 2');
    await createTodoViaApi(request, 'Done todo', { completed: true });
  });

  test('Filter: Active shows only incomplete todos', async ({ page }) => {
    await page.goto('/');
    await waitForList(page);

    await page.selectOption('#filter-status', 'false');
    await waitForList(page);

    await expect(page.locator('.todo-item')).toHaveCount(2);
    await expect(page.locator('.todo-item').filter({ hasText: 'Active todo 1' })).toBeVisible();
  });

  test('Filter: Completed shows only completed todos', async ({ page }) => {
    await page.goto('/');
    await waitForList(page);

    await page.selectOption('#filter-status', 'true');
    await waitForList(page);

    await expect(page.locator('.todo-item')).toHaveCount(1);
    await expect(page.locator('.todo-item').filter({ hasText: 'Done todo' })).toBeVisible();
  });

  test('Filter: All status shows all todos', async ({ page }) => {
    await page.goto('/');
    await waitForList(page);

    await page.selectOption('#filter-status', 'true');
    await waitForList(page);
    await page.selectOption('#filter-status', '');
    await waitForList(page);

    await expect(page.locator('.todo-item')).toHaveCount(3);
  });
});

// ─── Filter by priority ───────────────────────────────────────────────────────

test.describe('Filter by priority', () => {
  test.beforeEach(async ({ request }) => {
    await clearAllTodos(request);
    await createTodoViaApi(request, 'High priority', { priority: 'high' });
    await createTodoViaApi(request, 'Medium priority', { priority: 'medium' });
    await createTodoViaApi(request, 'Low priority', { priority: 'low' });
  });

  test('Filter by high priority', async ({ page }) => {
    await page.goto('/');
    await waitForList(page);

    await page.selectOption('#filter-priority', 'high');
    await waitForList(page);

    await expect(page.locator('.todo-item')).toHaveCount(1);
    await expect(page.locator('.todo-item').filter({ hasText: 'High priority' })).toBeVisible();
  });

  test('Filter by medium priority', async ({ page }) => {
    await page.goto('/');
    await waitForList(page);

    await page.selectOption('#filter-priority', 'medium');
    await waitForList(page);

    await expect(page.locator('.todo-item')).toHaveCount(1);
    await expect(page.locator('.todo-item').filter({ hasText: 'Medium priority' })).toBeVisible();
  });

  test('Filter by low priority', async ({ page }) => {
    await page.goto('/');
    await waitForList(page);

    await page.selectOption('#filter-priority', 'low');
    await waitForList(page);

    await expect(page.locator('.todo-item')).toHaveCount(1);
    await expect(page.locator('.todo-item').filter({ hasText: 'Low priority' })).toBeVisible();
  });

  test('Clearing priority filter restores all todos', async ({ page }) => {
    await page.goto('/');
    await waitForList(page);

    await page.selectOption('#filter-priority', 'high');
    await waitForList(page);
    await page.selectOption('#filter-priority', '');
    await waitForList(page);

    await expect(page.locator('.todo-item')).toHaveCount(3);
  });
});

// ─── Sort ─────────────────────────────────────────────────────────────────────

test.describe('Sort', () => {
  test.beforeEach(async ({ request }) => {
    await clearAllTodos(request);
    await createTodoViaApi(request, 'Alpha Task', { priority: 'low' });
    await createTodoViaApi(request, 'Beta Task', { priority: 'high' });
    await createTodoViaApi(request, 'Gamma Task', { priority: 'medium' });
  });

  test('Sort by title shows todos in alphabetical order (API)', async ({ request }) => {
    const res = await request.get('/api/todos/?sort_by=title&order=asc');
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    const titles = body.items.map((i: any) => i.title);
    expect(titles[0]).toBe('Alpha Task');
    expect(titles[1]).toBe('Beta Task');
    expect(titles[2]).toBe('Gamma Task');
  });

  test('Sort by title in UI', async ({ page }) => {
    await page.goto('/');
    await waitForList(page);

    await page.selectOption('#sort-by', 'title');
    await waitForList(page);

    const titles = await page.locator('.todo-title').allTextContents();
    const sorted = [...titles].sort();
    expect(titles).toEqual(sorted);
  });

  test('Sort by priority via API (desc)', async ({ request }) => {
    const res = await request.get('/api/todos/?sort_by=priority&order=desc');
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.items.length).toBeGreaterThanOrEqual(3);
  });
});

// ─── Edit / update todo ───────────────────────────────────────────────────────

test.describe('Edit / update todo', () => {
  test.beforeEach(async ({ request }) => {
    await clearAllTodos(request);
  });

  test('Edit todo title via UI', async ({ page }) => {
    await page.goto('/');
    await waitForList(page);

    await page.fill('#new-title', 'Original Title');
    await page.click('#btn-add');
    await expect(page.locator('.todo-item').filter({ hasText: 'Original Title' })).toBeVisible();

    // Hover to reveal actions and click edit
    const item = page.locator('.todo-item').filter({ hasText: 'Original Title' }).first();
    await item.hover();
    await item.locator('.btn-edit').click();

    // Clear and type new title
    await item.locator('.edit-title').fill('Updated Title');
    await item.locator('.btn-save').click();

    await expect(page.locator('.todo-item').filter({ hasText: 'Updated Title' })).toBeVisible();
  });

  test('Edit todo description via UI', async ({ page }) => {
    await page.goto('/');
    await waitForList(page);

    await page.fill('#new-title', 'Todo with desc');
    await page.click('#btn-add');

    const item = page.locator('.todo-item').filter({ hasText: 'Todo with desc' }).first();
    await item.hover();
    await item.locator('.btn-edit').click();

    await item.locator('.edit-desc').fill('New description text');
    await item.locator('.btn-save').click();

    await expect(page.locator('.todo-item .todo-desc').filter({ hasText: 'New description text' })).toBeVisible();
  });

  test('Edit todo priority via UI', async ({ page }) => {
    await page.goto('/');
    await waitForList(page);

    await page.fill('#new-title', 'Priority change test');
    await page.selectOption('#new-priority', 'low');
    await page.click('#btn-add');

    const item = page.locator('.todo-item').filter({ hasText: 'Priority change test' }).first();
    await item.hover();
    await item.locator('.btn-edit').click();

    await item.locator('.edit-priority').selectOption('high');
    await item.locator('.btn-save').click();

    await expect(
      page.locator('.todo-item').filter({ hasText: 'Priority change test' }).locator('.badge-high')
    ).toBeVisible();
  });

  test('Cancel edit restores original title', async ({ page }) => {
    await page.goto('/');
    await waitForList(page);

    await page.fill('#new-title', 'Cancel edit test');
    await page.click('#btn-add');

    const item = page.locator('.todo-item').filter({ hasText: 'Cancel edit test' }).first();
    await item.hover();
    await item.locator('.btn-edit').click();

    await item.locator('.edit-title').fill('Should not be saved');
    await item.locator('.btn-cancel').click();

    await expect(page.locator('.todo-item').filter({ hasText: 'Cancel edit test' })).toBeVisible();
  });

  test('Update todo via API PUT', async ({ request }) => {
    const created = await createTodoViaApi(request, 'API update test');
    const res = await request.put(`/api/todos/${created.id}`, {
      data: { title: 'API Updated Title', priority: 'high' },
    });
    expect(res.ok()).toBeTruthy();
    const updated = await res.json();
    expect(updated.title).toBe('API Updated Title');
    expect(updated.priority).toBe('high');
  });
});

// ─── Toggle completion ────────────────────────────────────────────────────────

test.describe('Toggle completion', () => {
  test.beforeEach(async ({ request }) => {
    await clearAllTodos(request);
  });

  test('Toggle todo done via done button in UI', async ({ page }) => {
    await page.goto('/');
    await waitForList(page);

    await page.fill('#new-title', 'Toggle me');
    await page.click('#btn-add');

    const item = page.locator('.todo-item').filter({ hasText: 'Toggle me' }).first();
    await expect(item).not.toHaveClass(/completed/);

    await item.locator('.todo-done-btn').click();
    await page.waitForTimeout(500);

    await expect(
      page.locator('.todo-item').filter({ hasText: 'Toggle me' }).first()
    ).toHaveClass(/completed/);
  });

  test('Toggle todo back to incomplete', async ({ page }) => {
    await page.goto('/');
    await waitForList(page);

    await page.fill('#new-title', 'Toggle twice');
    await page.click('#btn-add');

    const item = page.locator('.todo-item').filter({ hasText: 'Toggle twice' }).first();
    await item.locator('.todo-done-btn').click();
    await page.waitForTimeout(400);
    await item.locator('.todo-done-btn').click();
    await page.waitForTimeout(400);

    await expect(
      page.locator('.todo-item').filter({ hasText: 'Toggle twice' }).first()
    ).not.toHaveClass(/completed/);
  });

  test('API PATCH /{id}/toggle toggles completion', async ({ request }) => {
    const todo = await createTodoViaApi(request, 'API toggle test');
    expect(todo.completed).toBe(false);

    const res = await request.patch(`/api/todos/${todo.id}/toggle`);
    expect(res.ok()).toBeTruthy();
    const toggled = await res.json();
    expect(toggled.completed).toBe(true);
  });
});

// ─── Delete todo ──────────────────────────────────────────────────────────────

test.describe('Delete todo', () => {
  test.beforeEach(async ({ request }) => {
    await clearAllTodos(request);
  });

  test('Delete a todo via UI delete button', async ({ page }) => {
    await page.goto('/');
    await waitForList(page);

    await page.fill('#new-title', 'Delete me');
    await page.click('#btn-add');
    await expect(page.locator('.todo-item').filter({ hasText: 'Delete me' })).toBeVisible();

    const item = page.locator('.todo-item').filter({ hasText: 'Delete me' }).first();
    await item.hover();
    await item.locator('.btn-del').click();
    await page.waitForTimeout(500);

    await expect(page.locator('.todo-item').filter({ hasText: 'Delete me' })).toHaveCount(0);
  });

  test('API DELETE /{id} removes todo', async ({ request }) => {
    const todo = await createTodoViaApi(request, 'API delete test');

    const del = await request.delete(`/api/todos/${todo.id}`);
    expect(del.status()).toBe(204);

    const get = await request.get(`/api/todos/${todo.id}`);
    expect(get.status()).toBe(404);
  });
});

// ─── Bulk operations ──────────────────────────────────────────────────────────

test.describe('Bulk complete', () => {
  test.beforeEach(async ({ request }) => {
    await clearAllTodos(request);
    await createTodoViaApi(request, 'Bulk A');
    await createTodoViaApi(request, 'Bulk B');
    await createTodoViaApi(request, 'Bulk C');
  });

  test('Select all and bulk mark complete', async ({ page }) => {
    await page.goto('/');
    await waitForList(page);

    await page.check('#select-all');
    await page.waitForTimeout(300);

    await expect(page.locator('#bulk-bar')).toBeVisible();
    await expect(page.locator('#bulk-count')).toContainText('3 selected');

    await page.click('#bulk-complete');
    await page.waitForTimeout(1000);

    // All items should now have completed class
    const items = page.locator('.todo-item');
    const count = await items.count();
    for (let i = 0; i < count; i++) {
      await expect(items.nth(i)).toHaveClass(/completed/);
    }
  });

  test('Select all and bulk mark incomplete', async ({ page }) => {
    await page.goto('/');
    await waitForList(page);

    // First complete all
    await page.check('#select-all');
    await page.click('#bulk-complete');
    await page.waitForTimeout(1000);

    // Now mark all incomplete
    await page.check('#select-all');
    await page.click('#bulk-incomplete');
    await page.waitForTimeout(1000);

    const items = page.locator('.todo-item');
    const count = await items.count();
    for (let i = 0; i < count; i++) {
      await expect(items.nth(i)).not.toHaveClass(/completed/);
    }
  });

  test('API bulk complete', async ({ request }) => {
    const [a, b, c] = await Promise.all([
      createTodoViaApi(request, 'Bulk API A'),
      createTodoViaApi(request, 'Bulk API B'),
      createTodoViaApi(request, 'Bulk API C'),
    ]);

    const res = await request.patch('/api/todos/bulk/complete', {
      data: { ids: [a.id, b.id, c.id], completed: true },
    });
    expect(res.ok()).toBeTruthy();
    const updated = await res.json();
    expect(updated.every((t: any) => t.completed === true)).toBeTruthy();
  });
});

test.describe('Bulk delete', () => {
  test.beforeEach(async ({ request }) => {
    await clearAllTodos(request);
    await createTodoViaApi(request, 'Del Bulk A');
    await createTodoViaApi(request, 'Del Bulk B');
    await createTodoViaApi(request, 'Del Bulk C');
  });

  test('Select all and bulk delete', async ({ page }) => {
    await page.goto('/');
    await waitForList(page);

    await page.check('#select-all');
    await page.waitForTimeout(300);

    await page.click('#bulk-delete');
    await page.waitForTimeout(1000);

    await expect(page.locator('.empty')).toBeVisible();
  });

  test('API bulk delete', async ({ request }) => {
    const [a, b] = await Promise.all([
      createTodoViaApi(request, 'Bulk Del API A'),
      createTodoViaApi(request, 'Bulk Del API B'),
    ]);

    const res = await request.delete('/api/todos/bulk/delete', {
      data: { ids: [a.id, b.id] },
    });
    expect(res.status()).toBe(204);

    const checkA = await request.get(`/api/todos/${a.id}`);
    expect(checkA.status()).toBe(404);
  });
});

// ─── Pagination ───────────────────────────────────────────────────────────────

test.describe('Pagination', () => {
  test.beforeEach(async ({ request }) => {
    await clearAllTodos(request);
    // Create 25 todos — more than the default page size of 20
    await Promise.all(
      Array.from({ length: 25 }, (_, i) =>
        createTodoViaApi(request, `Pagination Todo ${String(i + 1).padStart(2, '0')}`)
      )
    );
  });

  test('Pagination controls appear when > 20 todos', async ({ page }) => {
    await page.goto('/');
    await waitForList(page);

    await expect(page.locator('#pagination')).toBeVisible();
    await expect(page.locator('#page-info')).toContainText('Page 1');
  });

  test('Navigate to page 2', async ({ page }) => {
    await page.goto('/');
    await waitForList(page);

    await page.click('#page-next');
    await waitForList(page);

    await expect(page.locator('#page-info')).toContainText('Page 2');
    const items = page.locator('.todo-item');
    await expect(items).toHaveCount(5); // 25 - 20 = 5 on page 2
  });

  test('Navigate back to page 1', async ({ page }) => {
    await page.goto('/');
    await waitForList(page);

    await page.click('#page-next');
    await waitForList(page);
    await page.click('#page-prev');
    await waitForList(page);

    await expect(page.locator('#page-info')).toContainText('Page 1');
    await expect(page.locator('.todo-item')).toHaveCount(20);
  });

  test('API pagination params respected', async ({ request }) => {
    const res = await request.get('/api/todos/?page=2&page_size=10');
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.page).toBe(2);
    expect(body.items.length).toBeGreaterThanOrEqual(10);
  });
});

// ─── Due date overdue indicator ───────────────────────────────────────────────

test.describe('Due date', () => {
  test.beforeEach(async ({ request }) => {
    await clearAllTodos(request);
  });

  test('Overdue todo shows overdue indicator', async ({ page, request }) => {
    // Create a todo with a past due date via API
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    await createTodoViaApi(request, 'Overdue Task', {
      due_date: yesterday.toISOString(),
    });

    await page.goto('/');
    await waitForList(page);

    const item = page.locator('.todo-item').filter({ hasText: 'Overdue Task' }).first();
    await expect(item.locator('.due-date.overdue')).toBeVisible();
  });

  test('Future due date shows normal date indicator', async ({ page, request }) => {
    const nextWeek = new Date();
    nextWeek.setDate(nextWeek.getDate() + 7);
    await createTodoViaApi(request, 'Future Task', {
      due_date: nextWeek.toISOString(),
    });

    await page.goto('/');
    await waitForList(page);

    const item = page.locator('.todo-item').filter({ hasText: 'Future Task' }).first();
    await expect(item.locator('.due-date')).toBeVisible();
    await expect(item.locator('.due-date.overdue')).toHaveCount(0);
  });
});

// ─── API edge cases ───────────────────────────────────────────────────────────

test.describe('API edge cases', () => {
  test('GET /api/todos/{id} returns 404 for missing todo', async ({ request }) => {
    const res = await request.get('/api/todos/999999999');
    expect(res.status()).toBe(404);
  });

  test('PUT /api/todos/{id} returns 404 for missing todo', async ({ request }) => {
    const res = await request.put('/api/todos/999999999', {
      data: { title: 'Ghost' },
    });
    expect(res.status()).toBe(404);
  });

  test('PATCH /api/todos/{id}/toggle returns 404 for missing todo', async ({ request }) => {
    const res = await request.patch('/api/todos/999999999/toggle');
    expect(res.status()).toBe(404);
  });

  test('DELETE /api/todos/{id} returns 404 for missing todo', async ({ request }) => {
    const res = await request.delete('/api/todos/999999999');
    expect(res.status()).toBe(404);
  });
});
