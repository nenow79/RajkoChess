const trimTrailingSlash = (value) => value.replace(/\/+$/, "");

export const API_URL = trimTrailingSlash(import.meta.env.VITE_API_URL || "/api");
