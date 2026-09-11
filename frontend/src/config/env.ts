/**
 * Application environment configuration.
 *
 * Centralizes access to environment variables, providing reliable fallbacks
 * and preventing hardcoded localhost URLs across components and services.
 */

export const ENV = {
  API_URL: (import.meta.env.VITE_BACKEND_API_URL as string) || 'http://localhost:8080',
  WS_URL: (import.meta.env.VITE_BACKEND_WS_URL as string) || 'ws://localhost:8080/api/v1/ws',
} as const;
