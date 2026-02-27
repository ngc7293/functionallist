<script lang="ts">
  import { onMount } from "svelte";
  import { apiFetch } from "./api";
  import { FunctionalList, FunctionalListEvent, FunctionalListEventCreateRequest } from "./interface";

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
          checked: boolean;
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
        } else if (ev.checked !== undefined && ev.checked !== existing.checked) {
          compiledEvents.push({
            eventId: compiledEvents.length + 1,
            itemId: ev.itemId,
            modification: { type: "check", checked: ev.checked },
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

  async function commitRename(itemId: number, oldName: string) {
    const newName = editValue.trim();
    editingItem = null;
    if (!newName || newName === oldName) return;
    // Posts a new event under the new name; old name entry remains in event log.
    await postEvent(itemId, newName, undefined);
  }

  onMount(load);
</script>

{#if loading}
  <p>Loading…</p>
{:else if error}
  <p>Error: {error}</p>
{:else if listData}
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
              if (e.key === "Escape") {
                editingItem = null;
              }
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
          <time class="event-time">{formatDate(ev.occuredAt)}</time>
          {#if ev.modification.type === "add"}
            <span class="event-type">+</span>
            <span class="event-name">{ev.modification.displayName}</span>
          {:else if ev.modification.type === "rename"}
            <span class="event-type">✎</span>
            <span class="event-name">{ev.modification.displayNameBefore} → {ev.modification.displayNameAfter}</span>
          {:else if ev.modification.type === "check"}
            <span class="event-type">{ev.modification.checked ? "☑︎" : "☐"} </span>
            <span class="event-name">{listItems.get(ev.itemId)!.displayName}</span>
          {/if}
          <span class="event-user">{listUsers.get(ev.userId)}</span>
        </li>
      {/each}
    </ol>
  </details>
{/if}

<style>
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
    grid-template-columns: 12em 0.75em 1fr auto auto;
    gap: 0.5rem;
    align-items: baseline;
    padding: 0.4rem 1rem;
    border-top: 1px solid #f4f4f5;
    color: #52525b;
  }
  .event-time {
    color: #a1a1aa;
    white-space: nowrap;
  }
  .event-name {
    font-weight: 500;
    word-break: break-word;
  }
  .event-user {
    color: #a1a1aa;
    white-space: nowrap;
  }
</style>
