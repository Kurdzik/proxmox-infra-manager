import { removeAuthCookie, getAuthCookie } from "@/lib/cookies";
import type { ApiResponse } from "./types";

const conf = {
  backendUrl: process.env.NEXT_PUBLIC_BACKEND_URL || "NO BACKEND URL PROVIDED",
  apiVersion: "v1",
};

const handleUnauthorized = (): void => {
  removeAuthCookie();
  window.location.href = "/";
};

const createHeaders = (secure: boolean = true): Record<string, string> => {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  if (secure) {
    const token = getAuthCookie();
    if (token) {
      headers["X-Session-Token"] = token;
    }
  }

  return headers;
};

const handleResponse = async (response: Response): Promise<ApiResponse> => {
  const data = await response.json();

  if (response.status === 401) {
    handleUnauthorized();
    throw new Error("Unauthorized - redirecting to login");
  }

  const apiResponse: ApiResponse = {
    ...data,
    status: response.status,
  };

  if (!response.ok) {
    apiResponse.detail = data.detail;
  }

  return apiResponse;
};

export async function get(endpoint: string, secure: boolean = true): Promise<ApiResponse> {
  const url = `${conf.backendUrl}/api/${conf.apiVersion}/${endpoint}`;
  return fetch(url, { method: "GET", headers: createHeaders(secure) }).then(handleResponse);
}

export async function post(
  endpoint: string,
  requestBody?: any,
  secure: boolean = true,
): Promise<ApiResponse> {
  const url = `${conf.backendUrl}/api/${conf.apiVersion}/${endpoint}`;
  return fetch(url, {
    method: "POST",
    headers: createHeaders(secure),
    body: JSON.stringify(requestBody),
  }).then(handleResponse);
}

export async function put(
  endpoint: string,
  requestBody?: any,
  secure: boolean = true,
): Promise<ApiResponse> {
  const url = `${conf.backendUrl}/api/${conf.apiVersion}/${endpoint}`;
  return fetch(url, {
    method: "PUT",
    headers: createHeaders(secure),
    body: JSON.stringify(requestBody),
  }).then(handleResponse);
}

export async function patch(
  endpoint: string,
  requestBody?: any,
  secure: boolean = true,
): Promise<ApiResponse> {
  const url = `${conf.backendUrl}/api/${conf.apiVersion}/${endpoint}`;
  return fetch(url, {
    method: "PATCH",
    headers: createHeaders(secure),
    body: JSON.stringify(requestBody),
  }).then(handleResponse);
}

export async function del(endpoint: string, secure: boolean = true): Promise<ApiResponse> {
  const url = `${conf.backendUrl}/api/${conf.apiVersion}/${endpoint}`;
  return fetch(url, { method: "DELETE", headers: createHeaders(secure) }).then(handleResponse);
}
