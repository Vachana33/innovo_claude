/**
 * API utility functions for making authenticated requests.
 */

import { debugLog } from "./debugLog";

const envApiUrl = import.meta.env.VITE_API_URL;
const isProduction = import.meta.env.PROD;

if (isProduction && !envApiUrl) {
  console.error("⚠️ VITE_API_URL is not set in production!");
}

export const API_BASE_URL = envApiUrl || "http://localhost:8000";

const TOKEN_STORAGE_KEY = "innovo_auth_token";
const USER_EMAIL_KEY = "innovo_user_email";

function getAuthToken(): string | null {
  return localStorage.getItem(TOKEN_STORAGE_KEY);
}

export async function apiRequest<T = unknown>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  // #region agent log
  debugLog("api.ts:apiRequest:ENTRY", "API request started", { endpoint, method: options.method || 'GET' }, "B");
  // #endregion
  const token = getAuthToken();

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  // #region agent log
  debugLog("api.ts:apiRequest:BEFORE_FETCH", "About to fetch", { url: `${API_BASE_URL}${endpoint}`, hasToken: !!token }, "B");
  // #endregion

  try {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers,
    });

    // #region agent log
    debugLog("api.ts:apiRequest:AFTER_FETCH", "Fetch response received", { status: response.status, statusText: response.statusText, endpoint }, "B");
    // #endregion

    // 🔴 AUTH HANDLING (NO REDIRECT HERE)
    if (response.status === 401) {
      // #region agent log
      debugLog("api.ts:apiRequest:401", "Unauthorized - clearing auth", { endpoint }, "B");
      // #endregion
      localStorage.removeItem(TOKEN_STORAGE_KEY);
      localStorage.removeItem(USER_EMAIL_KEY);
      throw new Error("AUTH_EXPIRED");
    }

    if (response.status === 204) {
      return null as T;
    }

    const contentType = response.headers.get("content-type");
    const isJson = contentType?.includes("application/json");

    let data: unknown = null;
    if (isJson) {
      const text = await response.text();
      // #region agent log
      debugLog("api.ts:apiRequest:PARSE_JSON", "Parsing JSON response", { textLength: text.length, endpoint }, "C");
      // #endregion
      try {
        data = text ? JSON.parse(text) : null;
      } catch (parseError) {
        // #region agent log
        debugLog("api.ts:apiRequest:JSON_PARSE_ERROR", "JSON parse failed", { error: String(parseError), textPreview: text.substring(0, 100), endpoint }, "C");
        // #endregion
        throw parseError;
      }
    }

    if (!response.ok) {
      const err = data as { detail?: string; message?: string };
      // #region agent log
      debugLog("api.ts:apiRequest:NOT_OK", "Response not OK", { status: response.status, error: err?.detail || err?.message || 'Request failed', endpoint }, "B");
      // #endregion
      throw new Error(err?.detail || err?.message || "Request failed");
    }

    // #region agent log
    debugLog("api.ts:apiRequest:SUCCESS", "API request succeeded", { endpoint, dataType: typeof data }, "B");
    // #endregion
    return data as T;
  } catch (error) {
    // #region agent log
    debugLog("api.ts:apiRequest:ERROR", "API request error", { error: String(error), errorType: error instanceof Error ? error.constructor.name : 'unknown', endpoint }, "B");
    // #endregion
    throw error;
  }
}

export const apiGet = <T>(endpoint: string) =>
  apiRequest<T>(endpoint, { method: "GET" });

export const apiPost = <T>(endpoint: string, body?: unknown) =>
  apiRequest<T>(endpoint, {
    method: "POST",
    body: body ? JSON.stringify(body) : undefined,
  });

export const apiPut = <T>(endpoint: string, body?: unknown) =>
  apiRequest<T>(endpoint, {
    method: "PUT",
    body: body ? JSON.stringify(body) : undefined,
  });

export const apiDelete = <T>(endpoint: string) =>
  apiRequest<T>(endpoint, { method: "DELETE" });

/**
 * Upload a file with authentication.
 * Used for audio file uploads and other file uploads.
 */
export async function apiUploadFile(
  endpoint: string,
  file: File,
  additionalData?: Record<string, string>
): Promise<Record<string, unknown>> {
  // #region agent log
  debugLog("api.ts:apiUploadFile:ENTRY", "File upload started", { endpoint, fileName: file.name, fileSize: file.size }, "F");
  // #endregion
  const token = getAuthToken();
  const formData = new FormData();
  formData.append("file", file);

  // Add additional form data if provided
  if (additionalData) {
    Object.entries(additionalData).forEach(([key, value]) => {
      formData.append(key, value);
    });
  }

  const headers: Record<string, string> = {};
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  try {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      method: "POST",
      headers,
      body: formData,
    });

    // #region agent log
    debugLog("api.ts:apiUploadFile:AFTER_FETCH", "Upload response received", { status: response.status, endpoint }, "F");
    // #endregion

    if (response.status === 401) {
      localStorage.removeItem(TOKEN_STORAGE_KEY);
      localStorage.removeItem(USER_EMAIL_KEY);
      throw new Error("AUTH_EXPIRED");
    }

    const data = await response.json();

    if (!response.ok) {
      // #region agent log
      debugLog("api.ts:apiUploadFile:ERROR", "Upload failed", { status: response.status, error: data?.detail || data?.message || 'Upload failed', endpoint }, "F");
      // #endregion
      throw new Error(data.detail || data.message || "Upload failed");
    }

    // #region agent log
    debugLog("api.ts:apiUploadFile:SUCCESS", "File upload succeeded", { endpoint }, "F");
    // #endregion
    return data;
  } catch (error) {
    // #region agent log
    debugLog("api.ts:apiUploadFile:EXCEPTION", "Upload exception", { error: String(error), errorType: error instanceof Error ? error.constructor.name : 'unknown', endpoint }, "F");
    // #endregion
    throw error;
  }
}

/**
 * Upload multiple files with authentication.
 * Used for guidelines document uploads and other multi-file uploads.
 * Sends files with field name "files" in multipart/form-data.
 */
export async function apiUploadFilePut(
  endpoint: string,
  file: File
): Promise<unknown> {
  const token = getAuthToken();
  const formData = new FormData();
  formData.append("file", file);

  const headers: Record<string, string> = {};
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  try {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      method: "PUT",
      headers,
      body: formData,
    });

    if (response.status === 401) {
      localStorage.removeItem(TOKEN_STORAGE_KEY);
      localStorage.removeItem(USER_EMAIL_KEY);
      throw new Error("AUTH_EXPIRED");
    }

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || data.message || "Upload failed");
    }

    return data;
  } catch (error) {
    throw error;
  }
}

export async function apiUploadFiles(
  endpoint: string,
  files: File[]
): Promise<unknown> {
  // #region agent log
  debugLog("api.ts:apiUploadFiles:ENTRY", "Multiple file upload started", { endpoint, fileCount: files.length }, "F");
  // #endregion
  const token = getAuthToken();
  const formData = new FormData();

  // Append all files with field name "files"
  files.forEach((file) => {
    formData.append("files", file);
  });

  const headers: Record<string, string> = {};
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  // Note: Do NOT set Content-Type header - browser will set it automatically with boundary for FormData

  try {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      method: "POST",
      headers,
      body: formData,
    });

    // #region agent log
    debugLog("api.ts:apiUploadFiles:AFTER_FETCH", "Upload response received", { status: response.status, endpoint }, "F");
    // #endregion

    if (response.status === 401) {
      localStorage.removeItem(TOKEN_STORAGE_KEY);
      localStorage.removeItem(USER_EMAIL_KEY);
      throw new Error("AUTH_EXPIRED");
    }

    const data = await response.json();

    if (!response.ok) {
      // #region agent log
      debugLog("api.ts:apiUploadFiles:ERROR", "Upload failed", { status: response.status, error: data?.detail || data?.message || 'Upload failed', endpoint }, "F");
      // #endregion
      throw new Error(data.detail || data.message || "Upload failed");
    }

    // #region agent log
    debugLog("api.ts:apiUploadFiles:SUCCESS", "Multiple file upload succeeded", { endpoint }, "F");
    // #endregion
    return data;
  } catch (error) {
    // #region agent log
    debugLog("api.ts:apiUploadFiles:EXCEPTION", "Upload exception", { error: String(error), errorType: error instanceof Error ? error.constructor.name : 'unknown', endpoint }, "F");
    // #endregion
    throw error;
  }
}

/**
 * Download a file (returns blob response).
 * Used for PDF/DOCX exports.
 */
export async function apiDownloadFile(endpoint: string): Promise<Response> {
  // #region agent log
  debugLog("api.ts:apiDownloadFile:ENTRY", "File download started", { endpoint }, "F");
  // #endregion
  const token = getAuthToken();
  const headers: Record<string, string> = {};

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  try {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      method: "GET",
      headers,
    });

    // #region agent log
    debugLog("api.ts:apiDownloadFile:AFTER_FETCH", "Download response received", { status: response.status, endpoint }, "F");
    // #endregion

    if (response.status === 401) {
      localStorage.removeItem(TOKEN_STORAGE_KEY);
      localStorage.removeItem(USER_EMAIL_KEY);
      throw new Error("AUTH_EXPIRED");
    }

    if (!response.ok) {
      const errorText = await response.text();
      let errorMessage = "Download failed";
      try {
        const errorData = JSON.parse(errorText);
        errorMessage = errorData.detail || errorData.message || errorMessage;
      } catch {
        errorMessage = errorText || errorMessage;
      }
      // #region agent log
      debugLog("api.ts:apiDownloadFile:ERROR", "Download failed", { status: response.status, error: errorMessage, endpoint }, "F");
      // #endregion
      throw new Error(errorMessage);
    }

    // #region agent log
    debugLog("api.ts:apiDownloadFile:SUCCESS", "File download succeeded", { endpoint }, "F");
    // #endregion
    return response;
  } catch (error) {
    // #region agent log
    debugLog("api.ts:apiDownloadFile:EXCEPTION", "Download exception", { error: String(error), errorType: error instanceof Error ? error.constructor.name : 'unknown', endpoint }, "F");
    // #endregion
    throw error;
  }
}
