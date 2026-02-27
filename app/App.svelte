<script lang="ts">
  import { onMount } from "svelte";
  import { SvelteSet } from "svelte/reactivity";
  import type { User } from "oidc-client-ts";
  import { getUserManager, login, logout } from "./auth";
  import { apiFetch } from "./api";
  import FunctionalListView from "./FunctionalListView.svelte";
  import { FunctionalListCreateRequest, FunctionalListListResponse, FunctionalListMeta } from "./interface";

  let user = $state<User | null>(null);
  let loading = $state(true);
  let lists = $state<FunctionalListMeta[]>([]);
  let openLists = new SvelteSet<number>();
  let newListName = $state("");

  onMount(async () => {
    const userManager = await getUserManager();

    if (new URLSearchParams(window.location.search).has("code")) {
      await userManager.signinRedirectCallback();
      window.history.replaceState({}, "", window.location.pathname.replace(/\/callback$/, "/"));
    }
    user = await userManager.getUser();
    if (user) await loadLists();
    loading = false;
  });

  async function loadLists() {
    const res = await apiFetch("v1/lists");

    if (res.ok) {
      lists = FunctionalListListResponse.decode(await res.bytes()).lists;
    }
  }

  async function createList() {
    const name = newListName.trim();
    if (!name) return;

    const req: FunctionalListCreateRequest = {
      displayName: name,
      description: "",
    };
    const res = await apiFetch("v1/lists", {
      method: "POST",
      body: FunctionalListCreateRequest.encode(req).finish(),
    });

    if (res.ok) {
      newListName = "";
      await loadLists();
    }
  }

  function handleToggle(e: Event, id: number) {
    const open = (e.currentTarget as HTMLDetailsElement).open;
    if (open) {
      openLists.add(id);
    } else {
      openLists.delete(id);
    }
  }
</script>

{#if loading}
  <p>Loading…</p>
{:else if user}
  <div class="app">
    <header>
      <span>Signed in as {user.profile.email ?? user.profile.sub}</span>
      <button class="button-link" onclick={logout}>Sign out</button>
    </header>

    <main>
      <h2>Your lists</h2>
      <div class="lists">
        {#each lists as list (list.id)}
          <details class="list-section" ontoggle={(e) => handleToggle(e, list.id)}>
            <summary>{list.displayName}</summary>
            {#if openLists.has(list.id)}
              <FunctionalListView listId={list.id} />
            {/if}
          </details>
        {/each}
      </div>

      <form
        class="create-form"
        onsubmit={(e) => {
          e.preventDefault();
          createList();
        }}
      >
        <input type="text" bind:value={newListName} placeholder="New list name…" />
        <button type="submit">Create list</button>
      </form>
    </main>
  </div>
{:else}
  <div class="app">
    <header>
      <span>You are not signed in</span>
      <button class="button-link" onclick={login}>Sign in</button>
    </header>
  </div>
{/if}

<style>
  :global(*, *::before, *::after) {
    box-sizing: border-box;
  }
  :global(body) {
    margin: 0;
    font-family:
      system-ui,
      -apple-system,
      sans-serif;
    background: #f4f4f5;
    color: #18181b;
  }

  .app {
    max-width: 1000px;
    margin: 0 auto;
    padding: 0.75rem 1rem;
  }

  header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.75rem 0;
    border-bottom: 1px solid #d4d4d8;
    margin-bottom: 1.25rem;
    font-size: 0.9rem;
    color: #52525b;
  }

  h2 {
    margin: 0 0 0.75rem;
    font-size: 1.25rem;
  }

  .lists {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  details.list-section {
    background: #fff;
    border: 1px solid #d4d4d8;
    border-radius: 10px;
    overflow: hidden;
  }

  details.list-section > summary {
    list-style: none;
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem;
    font-size: 1rem;
    font-weight: 600;
    cursor: pointer;
    user-select: none;
    min-height: 52px;
  }
  details.list-section > summary::-webkit-details-marker {
    display: none;
  }

  details.list-section > summary::after {
    content: "›";
    font-size: 1.25rem;
    color: #a1a1aa;
    transition: transform 0.15s ease;
  }
  details.list-section[open] > summary::after {
    transform: rotate(90deg);
  }

  .create-form {
    display: flex;
    gap: 0.5rem;
    margin-top: 1.25rem;
  }
  .create-form input {
    flex: 1;
    padding: 0.75rem;
    font-size: 1rem;
    border: 1px solid #d4d4d8;
    border-radius: 8px;
    min-height: 44px;
  }
  .create-form button {
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
  button.button-link {
    background: none;
    border: none;
    padding: 0;
    font: inherit;
    color: #3b82f6;
    cursor: pointer;
  }
</style>
