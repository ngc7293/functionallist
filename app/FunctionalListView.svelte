<script lang="ts">
  import { onMount } from "svelte";
  import { apiFetch } from "./api";
  import {
    FunctionalList,
    FunctionalListCheckpointItem,
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
  let newItemNameSuggestions = $state<[number, string][]>([]);
  let selectedSuggestionIndex = $state(-1);
  let editingItem = $state<number | null>(null);
  let editValue = $state("");
  let loading = $state(true);
  let error = $state<string | null>(null);
  let eventsExpanded = $state(false);

  let activeItemId = $state<number | null>(null);
  let popoverAnchor = $state<{ top: number; left: number } | null>(null);
  let isTouch = $state(false);
  let longPressTimer: ReturnType<typeof setTimeout> | null = null;
  let showTimer: ReturnType<typeof setTimeout> | null = null;
  let hideTimer: ReturnType<typeof setTimeout> | null = null;

  let activeItemEvents = $derived(
    activeItemId !== null ? listEvents.filter((ev) => ev.itemId === activeItemId) : [],
  );

  $effect(() => {
    if (activeItemId !== null && !listItems.has(activeItemId)) closePopover();
  });

  function openPopover(itemId: number, el: HTMLElement) {
    if (hideTimer) {
      clearTimeout(hideTimer);
      hideTimer = null;
    }
    if (showTimer) {
      clearTimeout(showTimer);
      showTimer = null;
    }
    const rect = el.getBoundingClientRect();
    activeItemId = itemId;
    popoverAnchor = { top: rect.top, left: rect.left };
  }

  function closePopover() {
    activeItemId = null;
    popoverAnchor = null;
  }

  function scheduleClose() {
    hideTimer = setTimeout(() => closePopover(), 150);
  }

  function cancelClose() {
    if (hideTimer) {
      clearTimeout(hideTimer);
      hideTimer = null;
    }
  }

  function cancelShow() {
    if (showTimer) {
      clearTimeout(showTimer);
      showTimer = null;
    }
  }

  function onItemPointerDown(itemId: number, e: PointerEvent) {
    if (!isTouch) return;
    e.preventDefault();
    const el = e.currentTarget as HTMLElement;
    longPressTimer = setTimeout(() => { longPressTimer = null; openPopover(itemId, el); }, 500);
  }

  function onItemPointerMove(e: PointerEvent) {
    if (!isTouch) return;
    if (longPressTimer) {
      clearTimeout(longPressTimer);
      longPressTimer = null;
      return;
    }
    if (activeItemId === null) return;
    const row = document.elementFromPoint(e.clientX, e.clientY)?.closest<HTMLElement>("[data-item-id]");
    if (row?.dataset.itemId) {
      const itemId = parseInt(row.dataset.itemId);
      if (itemId !== activeItemId) openPopover(itemId, row);
    }
  }

  function cancelLongPress() {
    if (longPressTimer) {
      clearTimeout(longPressTimer);
      longPressTimer = null;
    } else if (isTouch && activeItemId !== null) {
      closePopover();
    }
  }

  function onItemMouseEnter(itemId: number, e: MouseEvent) {
    if (isTouch) return;
    cancelClose();
    cancelShow();
    const el = e.currentTarget as HTMLElement;
    showTimer = setTimeout(() => openPopover(itemId, el), 500);
  }

  function onItemMouseLeave() {
    if (isTouch) return;
    cancelShow();
    scheduleClose();
  }

  // Merge events: latest event per display_name wins.
  function compile(items: FunctionalListCheckpointItem[], events: FunctionalListEvent[]): [Map<number, ListItem>, ListEvent[]] {
    // eslint-disable-next-line svelte/prefer-svelte-reactivity
    const compiledItems = new Map<number, ListItem>();
    const sorted = [...events].sort((a, b) => a.occuredAt - b.occuredAt);

    let compiledEvents: ListEvent[] = [];

    for (const item of items) {
      compiledItems.set(item.itemId, {
        itemId: item.itemId,
        displayName: item.displayName,
        checked: item.checked,
        last_modified: item.occuredAt,
      });
    }

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

  function formatRelativeTime(ts: number): string {
    const date = new Date(ts * 1000);
    const seconds = Math.round((ts * 1000 - Date.now()) / 1000);
    const abs = Math.abs(seconds);
    const rtf = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
    const isToday = date.toDateString() === new Date().toDateString();

    let relative: string;
    if (isToday)           relative = "today";
    else if (abs < 604800) relative = rtf.format(Math.round(seconds / 86400), "day");
    else                   relative = date.toLocaleDateString();

    const time = date.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", hour12: false });
    return `${relative}, ${time}`;
  }

  async function load() {
    error = null;
    try {
      const checkpoint = eventsExpanded ? 0 : Math.floor(Date.now() / 1000) - (7 * 86400);
      const res = await apiFetch(`v1/lists/${listId}?checkpoint=${checkpoint}`);
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);

      listData = FunctionalList.decode(await res.bytes());
      listUsers = new Map(listData.users.map((u) => [u.id, u.displayName]));
      [listItems, listEvents] = compile(listData.checkpoint?.items || [], listData.events);
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
    if (selectedSuggestionIndex >= 0 && newItemNameSuggestions[selectedSuggestionIndex]) {
      const [itemId] = newItemNameSuggestions[selectedSuggestionIndex];
      selectedSuggestionIndex = -1;
      await selectSuggestion(itemId);
      return;
    }
    const name = newItemName.trim();
    if (!name) return;
    await postEvent(undefined, name, false);
    newItemName = "";
    newItemNameSuggestions = [];
    selectedSuggestionIndex = -1;
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

  async function suggestInput() {
    selectedSuggestionIndex = -1;
    if (newItemName === "") {
      newItemNameSuggestions = [];
      return;
    }

    let starswith: [number, string][] = [];
    let includes: [number, string][] = [];

    const needle = newItemName.toLocaleLowerCase();
    for (const [_, item] of listItems) {
      const haystack = item.displayName.toLocaleLowerCase();

      if (haystack.startsWith(needle)) {
        starswith.push([item.itemId, item.displayName]);
      } else if (haystack.includes(needle)) {
        includes.push([item.itemId, item.displayName]);
      }
    }

    newItemNameSuggestions = [...starswith, ...includes];
  }

  async function selectSuggestion(itemId: number) {
    newItemName = "";
    newItemNameSuggestions = [];
    selectedSuggestionIndex = -1;
    await postEvent(itemId, undefined, false);
  }

  onMount(() => {
    isTouch = window.matchMedia("(hover: none) and (pointer: coarse)").matches;
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
      <li
        class="item-row"
        class:checked={item.checked}
        onpointerdown={(e) => onItemPointerDown(item.itemId, e)}
        data-item-id={item.itemId}
        onpointerup={cancelLongPress}
        onpointermove={onItemPointerMove}
        oncontextmenu={(e) => { if (isTouch) e.preventDefault(); }}
        onmouseenter={(e) => onItemMouseEnter(item.itemId, e)}
        onmouseleave={onItemMouseLeave}
      >
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
        <button class="delete-item" onclick={() => postEvent(item.itemId, undefined, undefined)}>✖</button>
      </li>
    {/each}
  </ul>

  {#if activeItemId !== null && popoverAnchor !== null}
    {#if isTouch}
      <div class="popover-backdrop" onclick={closePopover}></div>
    {/if}
    <div
      class="item-popover"
      role="tooltip"
      style="top: {popoverAnchor.top}px; left: {popoverAnchor.left}px;"
      onmouseenter={() => { cancelClose(); cancelShow(); }}
      onmouseleave={scheduleClose}
    >
      <div class="popover-header">{listItems.get(activeItemId)?.displayName ?? ""}</div>
      {#if activeItemEvents.length === 0}
        <div class="popover-empty">No recent events.</div>
      {:else}
        <ol class="popover-event-list">
          {#each activeItemEvents as ev (ev.eventId)}
            <li class="popover-event-row">
              <time class="popover-event-time">{formatRelativeTime(ev.occuredAt)}</time>
              <div class="popover-event-content">
                {#if ev.modification.type === "add"}
                  <span class="event-type">+</span>
                  <span>{ev.modification.displayName}</span>
                {:else if ev.modification.type === "rename"}
                  <span class="event-type">✎</span>
                  <span>{ev.modification.displayNameBefore} → {ev.modification.displayNameAfter}</span>
                {:else if ev.modification.type === "check"}
                  <span class="event-type">{ev.modification.checked ? "☑︎" : "☐"}</span>
                  <span>{ev.modification.displayName}</span>
                {:else if ev.modification.type === "remove"}
                  <span class="event-type">×</span>
                  <span>{ev.modification.displayName}</span>
                {/if}
                <span class="popover-event-user">{listUsers.get(ev.userId) ?? ""}</span>
              </div>
            </li>
          {/each}
        </ol>
      {/if}
    </div>
  {/if}

  <form
    class="add-form"
    onsubmit={(e) => {
      e.preventDefault();
      addItem();
    }}
  >
    <div class="add-input-wrapper">
      {#if newItemNameSuggestions.length !== 0}
        <ul class="suggestion-list">
          {#each newItemNameSuggestions as [itemId, displayName], i (itemId)}
            <li>
              <button
                type="button"
                class:highlighted={i === selectedSuggestionIndex}
                onmouseenter={() => {
                  selectedSuggestionIndex = i;
                }}
                onclick={() => selectSuggestion(itemId)}>{displayName}</button
              >
            </li>
          {/each}
        </ul>
      {/if}
      <input
        class="add-input"
        type="text"
        bind:value={newItemName}
        oninput={() => suggestInput()}
        onkeydown={(e) => {
          if (newItemNameSuggestions.length === 0) return;
          if (e.key === "ArrowDown") {
            e.preventDefault();
            selectedSuggestionIndex = Math.min(selectedSuggestionIndex + 1, newItemNameSuggestions.length - 1);
          } else if (e.key === "ArrowUp") {
            e.preventDefault();
            selectedSuggestionIndex = Math.max(selectedSuggestionIndex - 1, -1);
          } else if (e.key === "Escape") {
            newItemNameSuggestions = [];
            selectedSuggestionIndex = -1;
          }
        }}
        placeholder="New item…"
      />
    </div>
    <button type="submit">Add</button>
  </form>

  <details
    class="events-section"
    ontoggle={(e) => {
      eventsExpanded = (e.target as HTMLDetailsElement).open;
      load();
    }}
  >
    <summary>Events ({eventsExpanded ? listData.events.length : "more than " + listData.events.length})</summary>
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
    position: sticky;
    bottom: 0;
    background: #fff;
    border-top: 1px solid #d4d4d8;
    box-shadow: 0 -4px 12px rgba(0, 0, 0, 0.06);
    border-radius: 0 0 10px 10px;
  }
  .add-input-wrapper {
    position: relative;
    flex: 1;
  }
  .add-input {
    width: 100%;
    box-sizing: border-box;
    padding: 0.75rem;
    font-size: 1rem;
    border: 1px solid #d4d4d8;
    border-radius: 8px;
    min-height: 44px;
  }
  .suggestion-list {
    position: absolute;
    bottom: calc(100% + 4px);
    top: auto;
    left: 0;
    right: 0;
    z-index: 10;
    list-style: none;
    margin: 0;
    padding: 0.25rem 0;
    background: #fff;
    border: 1px solid #d4d4d8;
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  }
  .suggestion-list li {
    display: block;
  }
  .suggestion-list button {
    display: block;
    width: 100%;
    text-align: left;
    padding: 0.5rem 0.75rem;
    font-size: 1rem;
    background: none;
    border: none;
    border-radius: 0;
    color: #18181b;
    cursor: pointer;
    font-weight: 400;
    min-height: unset;
  }
  .suggestion-list button.highlighted {
    background: #f4f4f5;
  }
  .add-form > button {
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

  .popover-backdrop {
    position: fixed;
    inset: 0;
    z-index: 19;
  }

  .item-popover {
    position: fixed;
    z-index: 20;
    transform: translateY(-100%) translateX(32px);
    background: #fff;
    border: 1px solid #d4d4d8;
    border-radius: 8px;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
    width: 260px;
    max-height: 320px;
    overflow-y: auto;
    font-size: 0.8rem;
  }

  .popover-header {
    padding: 0.5rem 0.75rem;
    font-weight: 600;
    font-size: 0.85rem;
    color: #18181b;
    border-bottom: 1px solid #e4e4e7;
  }

  .popover-empty {
    padding: 0.5rem 0.75rem;
    color: #a1a1aa;
    font-style: italic;
  }

  .popover-event-list {
    list-style: none;
    margin: 0;
    padding: 0.25rem 0;
  }

  .popover-event-row {
    padding: 0.3rem 0.75rem;
    border-top: 1px solid #f4f4f5;
    color: #52525b;
  }
  .popover-event-row:first-child {
    border-top: none;
  }

  .popover-event-time {
    display: block;
    color: #a1a1aa;
    font-size: 0.75rem;
    margin-bottom: 0.1rem;
  }

  .popover-event-content {
    display: flex;
    align-items: baseline;
    gap: 0.4rem;
  }

  .popover-event-user {
    margin-left: auto;
    color: #a1a1aa;
    white-space: nowrap;
    font-size: 0.75rem;
  }
</style>
