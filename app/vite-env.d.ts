/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly APP_OIDC_AUTHORITY: string;
  readonly APP_OIDC_CLIENT_ID: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
