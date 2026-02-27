<script lang="ts">
  import { onMount } from "svelte";
  import { apiFetch } from "./api";
  import {
    FunctionalList,
    FunctionalListEvent,
    FunctionalListEventCreateRequest,
    FunctionalListUpdateRequest,
  } from "./interface";

  let { listId }: { listId: number } = $props();

  interface ListItem {
    itemId: number;
    displayName: string;
    checked: boolean;
    last_modified: number;
  }

  interface ListEvent {
    eventId: number;
    itemId: number;
    modification:
      | {
          type: "add";
          displayName: string;
        }
      | {
          type: "rename";
          displayNameBefore: string;
          displayNameAfter: string;
        }
      | {
          type: "check";
          displayName: string;
          checked: boolean;
        }
      | {
          type: "remove";
          displayName: string;
        };
    occuredAt: number;
    userId: number;
  }

  let listData = $state<FunctionalList | null>(null);
  let listUsers = $state<Map<number, string>>(new Map());

  let listItems = $state<Map<number, ListItem>>(new Map());
  let listEvents = $state<ListEvent[]>([]);

  let newItemName = $state("");
  let editingItem = $state<number | null>(null);
  let editValue = $state("");
  let loading = $state(true);
  let error = $state<string | null>(null);

  // Merge events: latest event per display_name wins. Checked items sort first.
  function compile(events: FunctionalListEvent[]): [Map<number, ListItem>, ListEvent[]] {
    // eslint-disable-next-line svelte/prefer-svelte-reactivity
    const compiledItems = new Map<number, ListItem>();
    const sorted = [...events].sort((a, b) => a.occuredAt - b.occuredAt);

    let compiledEvents: ListEvent[] = [];

    for (const ev of sorted) {
      const existing = compiledItems.get(ev.itemId);

      if (existing === undefined) {
        compiledEvents.push({
          eventId: compiledEvents.length + 1,
          itemId: ev.itemId,
          modification: { type: "add", displayName: ev.displayName! },
          occuredAt: ev.occuredAt,
          userId: ev.userId,
        });

        compiledItems.set(ev.itemId, {
          itemId: ev.itemId,
          displayName: ev.displayName!,
          checked: ev.checked!,
          last_modified: ev.occuredAt,
        });
      } else {
        if (ev.displayName === undefined && ev.checked === undefined) {
          compiledEvents.push({
            eventId: compiledEvents.length + 1,
            itemId: ev.itemId,
            modification: { type: "remove", displayName: existing.displayName },
            occuredAt: ev.occuredAt,
            userId: ev.userId,
          });
          compiledItems.delete(ev.itemId);
        } else {
          if (ev.displayName && ev.displayName !== existing.displayName) {
            compiledEvents.push({
              eventId: compiledEvents.length + 1,
              itemId: ev.itemId,
              modification: {
                type: "rename",
                displayNameBefore: existing.displayName,
                displayNameAfter: ev.displayName,
              },
              occuredAt: ev.occuredAt,
              userId: ev.userId,
            });
          }
          if (ev.checked !== undefined && ev.checked !== existing.checked) {
            compiledEvents.push({
              eventId: compiledEvents.length + 1,
              itemId: ev.itemId,
              modification: { type: "check", displayName: existing.displayName, checked: ev.checked },
              occuredAt: ev.occuredAt,
              userId: ev.userId,
            });
          }

          compiledItems.set(ev.itemId, {
            itemId: ev.itemId,
            displayName: ev.displayName || existing.displayName,
            checked: ev.checked !== undefined ? ev.checked : existing.checked,
            last_modified: ev.occuredAt,
          });
        }
      }
    }

    return [compiledItems, compiledEvents.sort((a, b) => b.occuredAt - a.occuredAt)];
  }

  function sortItems(items: Map<number, ListItem>): ListItem[] {
    return Array.from(items.values()).sort((a, b) => {
      if (a.checked === b.checked) {
        if (a.checked) return b.last_modified - a.last_modified;
        else return a.displayName.localeCompare(b.displayName);
      }
      return a.checked ? 1 : -1;
    });
  }

  function formatDate(ts: number): string {
    return new Date(ts * 1000).toLocaleString();
  }

  async function load() {
    error = null;
    try {
      const res = await apiFetch(`v1/lists/${listId}`);
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);

      listData = FunctionalList.decode(await res.bytes());
      listUsers = new Map(listData.users.map((u) => [u.id, u.displayName]));
      [listItems, listEvents] = compile(listData.events);
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      loading = false;
    }
  }

  async function postEvent(itemId: number | undefined, displayName: string | undefined, checked: boolean | undefined) {
    const res = await apiFetch(`v1/lists/${listId}/events`, {
      method: "POST",
      body: FunctionalListEventCreateRequest.encode({
        itemId,
        displayName,
        checked,
      }).finish(),
    });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    await load();
  }

  async function addItem() {
    const name = newItemName.trim();
    if (!name) return;
    await postEvent(undefined, name, false);
    newItemName = "";
  }

  async function toggleItem(item: ListItem) {
    await postEvent(item.itemId, undefined, !item.checked);
  }

  function startEditing(item: ListItem) {
    editingItem = item.itemId;
    editValue = item.displayName;
  }

  function startEditingDescription() {
    editingItem = 0;
    editValue = listData?.description || "";
  }

  async function commitRename(itemId: number, oldName: string) {
    const newName = editValue.trim();
    editingItem = null;
    if (!newName || newName === oldName) return;
    // Posts a new event under the new name; old name entry remains in event log.
    await postEvent(itemId, newName, undefined);
  }

  async function commitDescription() {
    const newDescription = editValue.trim();
    editingItem = null;

    if (!newDescription || newDescription === listData?.description) return;

    const res = await apiFetch(`v1/lists/${listId}`, {
      method: "PUT",
      body: FunctionalListUpdateRequest.encode({
        id: listId,
        description: editValue.trim() || undefined,
      }).finish(),
    });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    await load();
  }

  onMount(() => {
    load();
    const refreshInterval = setInterval(load, 5000);
    return () => clearInterval(refreshInterval);
  });
</script>

{#if loading}
  <span class="description">Loading…</span>
{:else if error}
  <span class="description">Error: {error}</span>
{:else if listData}
  {#if editingItem === 0}
    <textarea
      class="edit-description"
      bind:value={editValue}
      onblur={() => commitDescription()}
      onkeydown={(e) => {
        if (e.key === "Enter" && e.shiftKey === false) commitDescription();
        if (e.key === "Escape") editingItem = null;
      }}
    ></textarea>
  {:else}
    <span
      role="button"
      tabindex="0"
      class={`description ${listData.description.length ? "" : "empty"}`}
      ondblclick={() => startEditingDescription()}
      >{listData.description.length ? listData.description : "No description provided."}</span
    >
  {/if}
  <ul class="item-list">
    {#each sortItems(listItems) as item (item.itemId)}
      <li class="item-row" class:checked={item.checked}>
        <input type="checkbox" checked={item.checked} onchange={() => toggleItem(item)} />
        {#if editingItem === item.itemId}
          <input
            class="edit-input"
            type="text"
            bind:value={editValue}
            onblur={() => commitRename(item.itemId, item.displayName)}
            onkeydown={(e) => {
              if (e.key === "Enter") commitRename(item.itemId, item.displayName);
              if (e.key === "Escape") editingItem = null;
            }}
          />
        {:else}
          <span
            class="item-name"
            role="button"
            tabindex="0"
            ondblclick={() => startEditing(item)}
            onkeydown={(e) => {
              if (e.key === "Enter") startEditing(item);
            }}>{item.displayName}</span
          >
        {/if}
        <button
          class="delete-item"
          tabindex="0"
          onclick={() => postEvent(item.itemId, undefined, undefined)}>✖</button
        >
      </li>
    {/each}
  </ul>

  <form
    class="add-form"
    onsubmit={(e) => {
      e.preventDefault();
      addItem();
    }}
  >
    <input class="add-input" type="text" bind:value={newItemName} placeholder="New item…" />
    <button type="submit">Add</button>
  </form>

  <details class="events-section">
    <summary>Events ({listData.events.length})</summary>
    <ol class="event-list">
      {#each listEvents as ev (ev.eventId)}
        <li class="event-row">
          <div class="event-row-meta">
            <time class="event-time">{formatDate(ev.occuredAt)}</time>
            <span class="event-user">{listUsers.get(ev.userId)}</span>
          </div>
          <div class="event-row-content">
            {#if ev.modification.type === "add"}
              <span class="event-type">+</span>
              <span class="event-name">{ev.modification.displayName}</span>
            {:else if ev.modification.type === "rename"}
              <span class="event-type">✎</span>
              <span class="event-name">{ev.modification.displayNameBefore} → {ev.modification.displayNameAfter}</span>
            {:else if ev.modification.type === "check"}
              <span class="event-type">{ev.modification.checked ? "☑︎" : "☐"} </span>
              <span class="event-name">{ev.modification.displayName}</span>
            {:else if ev.modification.type === "remove"}
              <span class="event-type">×</span>
              <span class="event-name">{ev.modification.displayName}</span>
            {/if}
          </div>
        </li>
      {/each}
    </ol>
  </details>
{/if}

<style>
  .description {
    display: inline-block;
    padding: 0.75rem 1rem;
    font-size: 0.95rem;
    color: #52525b;
    cursor: default;
    user-select: none;
    white-space: pre-wrap;
  }
  .description.empty {
    font-style: italic;
    color: #a1a1aa;
  }

  .edit-description {
    display: block;
    width: calc(100% - 2rem);
    margin: 0.75rem 1rem;
    padding: 0.4rem 0.5rem;
    font-size: 0.95rem;
    font-family: inherit;
    border: none;
    border-bottom: 2px solid #a1a1aa;
    resize: vertical;
    min-height: 3rem;
  }

  .item-list {
    list-style: none;
    padding: 0;
    margin: 0;
  }

  .item-row {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.75rem 1rem;
    border-bottom: 1px solid #f4f4f5;
    min-height: 52px;
    transition: opacity 0.2s;
  }
  .item-row.checked {
    opacity: 0.4;
  }

  .item-row input[type="checkbox"] {
    width: 20px;
    height: 20px;
    flex-shrink: 0;
    cursor: pointer;
    accent-color: #18181b;
  }

  .item-name {
    flex: 1;
    cursor: default;
    word-break: break-word;
  }
  .item-row.checked .item-name {
    text-decoration: line-through;
  }

  .edit-input {
    flex: 1;
    padding: 0.4rem 0.5rem;
    font-size: 1rem;
    border: 1px solid #a1a1aa;
    border-radius: 6px;
  }

  .delete-item {
    width: 20px;
    height: 20px;
    flex-shrink: 0;
    cursor: pointer;
    border: none;
    background: none;
    color: #a1a1aa;
  }

  .add-form {
    display: flex;
    gap: 0.5rem;
    padding: 0.75rem 1rem;
  }
  .add-input {
    flex: 1;
    padding: 0.75rem;
    font-size: 1rem;
    border: 1px solid #d4d4d8;
    border-radius: 8px;
    min-height: 44px;
  }
  .add-form button {
    padding: 0.75rem 1rem;
    font-size: 1rem;
    font-weight: 600;
    background: #18181b;
    color: #fff;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    min-height: 44px;
  }

  /* Events — collapsed by default, dimmed */
  .events-section {
    opacity: 0.55;
    border-top: 1px solid #e4e4e7;
  }
  .events-section > summary {
    list-style: none;
    padding: 0.75rem 1rem;
    font-size: 0.85rem;
    font-weight: 600;
    color: #71717a;
    cursor: pointer;
    user-select: none;
  }
  .events-section > summary::-webkit-details-marker {
    display: none;
  }

  .event-list {
    list-style: none;
    padding: 0;
    margin: 0;
    font-size: 0.8rem;
  }
  .event-row {
    display: grid;
    grid-template-columns: 12em 0.75em 1fr auto;
    gap: 0.5rem;
    align-items: baseline;
    padding: 0.4rem 1rem;
    border-top: 1px solid #f4f4f5;
    color: #52525b;
  }
  .event-row-meta,
  .event-row-content {
    display: contents;
  }
  /* Restore the DOM order: time(1), type(2), name(3), user(4) */
  .event-time {
    order: 1;
    color: #a1a1aa;
    white-space: nowrap;
  }
  .event-type {
    order: 2;
  }
  .event-name {
    order: 3;
    font-weight: 500;
    word-break: break-word;
  }
  .event-user {
    order: 4;
    color: #a1a1aa;
    white-space: nowrap;
  }

  @media (max-width: 511px) {
    .event-row {
      display: flex;
      flex-direction: column;
      gap: 0.15rem;
    }
    .event-row-meta {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 0.5rem;
      width: 100%;
    }
    .event-row-content {
      display: flex;
      align-items: baseline;
      gap: 0.5rem;
    }
    .event-time {
      order: unset;
    }
    .event-type {
      order: unset;
      width: 1em;
      flex-shrink: 0;
    }
    .event-name {
      order: unset;
      flex: 1;
    }
    .event-user {
      order: unset;
    }
  }
</style>
