import type { ChatSession } from "./types";

export function getStorageKey(workspaceId: string) {
  return `starfire-chat-${workspaceId}`;
}

export function loadSessions(workspaceId: string): ChatSession[] {
  try {
    const raw = localStorage.getItem(getStorageKey(workspaceId));
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export function saveSessions(workspaceId: string, sessions: ChatSession[]) {
  try {
    localStorage.setItem(getStorageKey(workspaceId), JSON.stringify(sessions));
  } catch {
    // localStorage full — silently fail
  }
}
