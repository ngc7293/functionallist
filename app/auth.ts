import { UserManager } from "oidc-client-ts";

let _managerPromise: Promise<UserManager> | null = null;

function createUserManager(): Promise<UserManager> {
  if (!_managerPromise) {
    _managerPromise = fetch("v1/config")
      .then((res) => {
        if (!res.ok) throw new Error(`Failed to fetch OIDC config: ${res.status}`);
        return res.json() as Promise<{ oidc_authority: string; oidc_client_id: string }>;
      })
      .then(
        (config) =>
          new UserManager({
            authority: config.oidc_authority,
            client_id: config.oidc_client_id,
            redirect_uri: `${window.location}callback`,
            scope: "openid profile email offline_access",
            automaticSilentRenew: true,
          }),
      );
  }
  return _managerPromise;
}

export const getUserManager = createUserManager;

export const login = async () => (await createUserManager()).signinRedirect();
export const logout = async () => (await createUserManager()).signoutRedirect();
