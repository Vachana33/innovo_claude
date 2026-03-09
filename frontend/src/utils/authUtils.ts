// frontend/src/utils/authUtils.ts

export const TOKEN_STORAGE_KEY = "innovo_auth_token";
export const USER_EMAIL_KEY = "innovo_user_email";

export function decodeJWT(token: string): string | null {
  try {
    const payload = token.split(".")[1];
    if (!payload) return null;
    const decoded = JSON.parse(atob(payload));
    return decoded.email || decoded.sub || null;
  } catch {
    return null;
  }
}
