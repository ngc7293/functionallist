import { getUserManager } from "./auth";

export async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  const user = await (await getUserManager()).getUser();
  if (!user?.access_token) throw new Error("Not authenticated");

  const response = await fetch(`${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
      Authorization: `Bearer ${user.access_token}`,
    },
  });

  if (response.status == 401) {
    // This shouldn't happen. Kick the user back to login
    (await getUserManager()).removeUser();
    window.location.reload();
  }

  return response;
}
