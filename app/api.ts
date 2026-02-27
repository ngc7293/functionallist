import { getUserManager } from "./auth";

export async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  const user = await (await getUserManager()).getUser();
  if (!user?.access_token) throw new Error("Not authenticated");

  return fetch(`${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
      Authorization: `Bearer ${user.access_token}`,
    },
  });
}
